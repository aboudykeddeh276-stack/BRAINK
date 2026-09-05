#!/usr/bin/env python3
"""Read-only capability scanner for the authenticated KEX/BRAINK repository estate.

The scanner turns the repository estate into machine-readable evidence. It never
mutates repositories. Authentication is supplied by GITHUB_TOKEN/GH_TOKEN.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import PurePosixPath

API = os.environ.get("GITHUB_API", "https://api.github.com")
OWNER = os.environ.get("GITHUB_OWNER", "aboudykeddeh276-stack")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
MAX_TREE = int(os.environ.get("KEX_MAX_TREE", "5000"))

ENTRYPOINTS = {
    "package.json": "node_manifest",
    "pyproject.toml": "python_manifest",
    "requirements.txt": "python_dependencies",
    "Cargo.toml": "rust_manifest",
    "go.mod": "go_manifest",
    "Dockerfile": "container",
    "docker-compose.yml": "compose",
    "docker-compose.yaml": "compose",
    "Makefile": "build_automation",
}
TEST_PATTERNS = ("test", "tests", "spec", "__tests__")


def request(path: str) -> object:
    req = urllib.request.Request(API.rstrip("/") + path)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def paginate(path: str) -> list[dict]:
    page = 1
    out: list[dict] = []
    while True:
        sep = "&" if "?" in path else "?"
        rows = request(f"{path}{sep}per_page=100&page={page}")
        if not isinstance(rows, list):
            raise RuntimeError(f"unexpected GitHub response for {path}")
        out.extend(rows)
        if len(rows) < 100:
            return out
        page += 1


def classify_tree(tree: list[dict]) -> dict:
    paths = [x.get("path", "") for x in tree if x.get("type") == "blob"]
    names = {PurePosixPath(p).name for p in paths}
    manifest_hits = sorted(ENTRYPOINTS[name] for name in names if name in ENTRYPOINTS)
    tests = sorted({part for p in paths for part in PurePosixPath(p).parts if part.lower() in TEST_PATTERNS})
    workflow_count = sum(p.startswith(".github/workflows/") for p in paths)
    source_count = sum(bool(re.search(r"\.(py|js|mjs|ts|tsx|go|rs|java|swift|sh)$", p, re.I)) for p in paths)
    docs_count = sum(bool(re.search(r"\.(md|rst|txt)$", p, re.I)) for p in paths)
    return {
        "file_count": len(paths),
        "source_file_count": source_count,
        "documentation_file_count": docs_count,
        "manifest_or_entrypoint_signals": manifest_hits,
        "test_surface": bool(tests),
        "test_directories": tests,
        "workflow_count": workflow_count,
        "sample_paths": sorted(paths)[:80],
    }


def main() -> int:
    if not TOKEN:
        print("FAIL: GITHUB_TOKEN or GH_TOKEN is required", file=sys.stderr)
        return 10

    repos = paginate(f"/users/{OWNER}/repos?type=owner")
    observations = []
    for repo in repos:
        name = repo["name"]
        default_branch = repo.get("default_branch") or "main"
        try:
            tree_obj = request(f"/repos/{OWNER}/{name}/git/trees/{default_branch}?recursive=1")
            tree = tree_obj.get("tree", []) if isinstance(tree_obj, dict) else []
            truncated = bool(tree_obj.get("truncated")) if isinstance(tree_obj, dict) else True
            cap = classify_tree(tree[:MAX_TREE])
            cap["tree_truncated"] = truncated or len(tree) > MAX_TREE
            error = None
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as exc:
            cap = {"file_count": None, "source_file_count": None, "documentation_file_count": None,
                   "manifest_or_entrypoint_signals": [], "test_surface": False, "test_directories": [],
                   "workflow_count": None, "sample_paths": [], "tree_truncated": None}
            error = str(exc)
        observations.append({
            "name": name,
            "default_branch": default_branch,
            "archived": bool(repo.get("archived")),
            "fork": bool(repo.get("fork")),
            "updated_at": repo.get("updated_at"),
            "size_kb": repo.get("size"),
            "description_present": bool(repo.get("description")),
            "capability": cap,
            "error": error,
        })

    manifest_counter = Counter()
    for row in observations:
        manifest_counter.update(row["capability"]["manifest_or_entrypoint_signals"])
    report = {
        "schema": "kex.braink.repository-capability-observation.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "authority": {"source": "authenticated GitHub API", "owner": OWNER, "mode": "read-only"},
        "repository_count": len(observations),
        "estate_summary": {
            "archived": sum(r["archived"] for r in observations),
            "forks": sum(r["fork"] for r in observations),
            "repositories_with_tests": sum(r["capability"]["test_surface"] for r in observations),
            "repositories_with_workflows": sum((r["capability"]["workflow_count"] or 0) > 0 for r in observations),
            "manifest_signal_frequency": dict(manifest_counter),
        },
        "observations": observations,
        "claim_boundary": [
            "This is structural repository evidence, not proof that a capability works.",
            "Tree presence does not prove execution, deployment, or production authority.",
            "The scanner is read-only and never mutates repositories.",
        ],
    }
    output = os.environ.get("KEX_OUTPUT", "repository-capability-observation.json")
    with open(output, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"PASS: scanned {len(observations)} repositories; wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
