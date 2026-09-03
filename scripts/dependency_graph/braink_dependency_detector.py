from __future__ import annotations

"""BRAINK/KEX build-time dependency detector.

Produces two outputs from one source-of-truth edge declaration:

1. GitHub Dependency Submission snapshot
   A standards-compatible supply-chain representation tied to the exact commit/ref.
2. BRAINK semantic dependency graph
   Preserves architectural edge classes that package-manager graphs cannot express.

The detector also discovers ordinary intra-repository Python imports and merges them
with explicitly declared cross-repository/runtime-authority edges.
"""

import argparse
import ast
import datetime as dt
import json
import os
import platform
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "dependency-graph" / "braink-runtime-dependencies.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text("utf-8"))


def _git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def _sha() -> str:
    return os.environ.get("GITHUB_SHA") or _git("rev-parse", "HEAD")


def _ref() -> str:
    return os.environ.get("GITHUB_REF") or f"refs/heads/{_git('branch', '--show-current')}"


def _module_name(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    return ".".join(rel.parts)


def _index_python_modules(scan_roots: list[str]) -> dict[str, str]:
    index: dict[str, str] = {}
    for root_name in scan_roots:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            name = _module_name(path)
            index[name] = rel
            if path.name == "__init__.py":
                index[name.removesuffix(".__init__")] = rel
    return index


def _discover_import_edges(scan_roots: list[str]) -> list[dict[str, Any]]:
    index = _index_python_modules(scan_roots)
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for source_name, source_rel in sorted(index.items()):
        source = ROOT / source_rel
        if source.name == "__init__.py" or not source.exists():
            continue
        try:
            tree = ast.parse(source.read_text("utf-8"), filename=source_rel)
        except SyntaxError:
            continue
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)

        for imported in imports:
            candidates = [imported]
            parts = imported.split(".")
            candidates.extend(".".join(parts[:i]) for i in range(len(parts) - 1, 0, -1))
            target_rel = next((index[c] for c in candidates if c in index), None)
            if not target_rel or target_rel == source_rel:
                continue
            key = (source_rel, target_rel)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "source": source_rel,
                    "target": target_rel,
                    "class": "MODULE_DEPENDENCY",
                    "relationship": "direct",
                    "scope": "runtime",
                    "interface": f"python import {imported}",
                    "authority": "BRAINK",
                    "detected": True,
                }
            )
    return edges


def _target_exists(target: str) -> bool:
    if "://" in target:
        return True
    return (ROOT / target).exists()


def _repo_sha(path: Path) -> str | None:
    try:
        return _git("rev-parse", "HEAD", cwd=path)
    except Exception:
        return None


def _purl_for_target(target: str, commit_sha: str) -> str:
    """Return a stable PURL for GitHub's snapshot representation.

    Architectural/runtime nodes use pkg:generic because they are not package-manager
    artifacts. Repository dependencies use pkg:github. The richer BRAINK graph retains
    exact class/interface/authority metadata.
    """
    if target.startswith("repository://"):
        repo = target.removeprefix("repository://")
        checkout = ROOT / "dependencies" / repo.split("/")[-1]
        version = _repo_sha(checkout) or "unresolved"
        owner, name = repo.split("/", 1)
        return f"pkg:github/{owner}/{name}@{version}"

    if target.startswith("runtime://"):
        ident = target.removeprefix("runtime://")
        name = urllib.parse.quote(ident, safe="/-._")
        runtime_version = platform.python_version() if ident.startswith("python/") else platform.system().lower()
        return f"pkg:generic/keddeh-runtime/{name}@{runtime_version}"

    rel = target.replace("\\", "/")
    name = urllib.parse.quote(rel, safe="/-._")
    return f"pkg:generic/keddeh-systems/braink-module@{commit_sha}#{name}"


def _dedupe_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in edges:
        key = (edge["source"], edge["target"], edge["class"])
        if key not in merged:
            merged[key] = dict(edge)
        elif not edge.get("detected"):
            # Explicit declarations override discovered metadata.
            merged[key].update(edge)
    return sorted(merged.values(), key=lambda e: (e["source"], e["class"], e["target"]))


def build(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    commit_sha = _sha()
    ref = _ref()
    declared = list(config.get("declared_edges", []))
    discovered = _discover_import_edges(config.get("scan_roots", []))
    edges = _dedupe_edges(discovered + declared)

    missing = [e for e in edges if not _target_exists(e["target"])]
    if missing:
        missing_text = "\n".join(f"{e['source']} -> {e['target']}" for e in missing)
        raise SystemExit(f"UNRESOLVED_DEPENDENCY_TARGETS:\n{missing_text}")

    scanned = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    detector = config["detector"]

    semantic = {
        "schema": "kex.braink.semantic-dependency-graph.v1",
        "sha": commit_sha,
        "ref": ref,
        "scanned": scanned,
        "detector": detector,
        "edge_classes": [
            "PACKAGE_DEPENDENCY",
            "MODULE_DEPENDENCY",
            "REPOSITORY_DEPENDENCY",
            "RUNTIME_AUTHORITY_DEPENDENCY",
        ],
        "edges": edges,
        "summary": {
            "edges": len(edges),
            "declared": sum(not e.get("detected", False) for e in edges),
            "detected": sum(bool(e.get("detected")) for e in edges),
            "by_class": {
                cls: sum(e["class"] == cls for e in edges)
                for cls in sorted({e["class"] for e in edges})
            },
        },
    }

    by_source: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        by_source.setdefault(edge["source"], []).append(edge)

    manifests: dict[str, Any] = {}
    for source, source_edges in sorted(by_source.items()):
        resolved: dict[str, Any] = {}
        for edge in source_edges:
            purl = _purl_for_target(edge["target"], commit_sha)
            resolved_key = f"{edge['class']}::{edge['target']}"
            resolved[resolved_key] = {
                "package_url": purl,
                "relationship": edge.get("relationship", "direct"),
                "scope": edge.get("scope", "runtime"),
                "dependencies": [],
                "metadata": {
                    "edge_class": edge["class"],
                    "authority": edge.get("authority", "UNKNOWN"),
                    "interface": edge.get("interface", "unspecified")[:200],
                    "target": edge["target"][:200],
                },
            }
        manifest: dict[str, Any] = {
            "name": source,
            "metadata": {
                "source_class": "BRAINK_RUNTIME_COMPONENT",
                "detector": detector["name"],
            },
            "resolved": resolved,
        }
        if "://" not in source and (ROOT / source).exists():
            manifest["file"] = {"source_location": source}
        manifests[source] = manifest

    job_id = os.environ.get("GITHUB_RUN_ID", "local")
    workflow = os.environ.get("GITHUB_WORKFLOW", "braink-dependency-graph")
    job_name = os.environ.get("GITHUB_JOB", "dependency-graph")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repository = os.environ.get("GITHUB_REPOSITORY", "aboudykeddeh276-stack/BRAINK")

    snapshot = {
        "version": 0,
        "job": {
            "id": job_id,
            "correlator": f"{workflow}:{job_name}",
            "html_url": f"{server_url}/{repository}/actions/runs/{job_id}" if job_id != "local" else server_url,
        },
        "sha": commit_sha,
        "ref": ref,
        "detector": {
            "name": detector["name"],
            "version": detector["version"],
            "url": f"{server_url}/{repository}/blob/{commit_sha}/scripts/dependency_graph/braink_dependency_detector.py",
            "metadata": {
                "semantic_graph": "braink-semantic-dependency-graph.json",
                "edge_count": len(edges),
            },
        },
        "scanned": scanned,
        "manifests": manifests,
    }
    return semantic, snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--semantic-output", type=Path, default=ROOT / "build" / "braink-semantic-dependency-graph.json")
    parser.add_argument("--snapshot-output", type=Path, default=ROOT / "build" / "github-dependency-snapshot.json")
    args = parser.parse_args()

    config = _read_json(args.config)
    semantic, snapshot = build(config)
    args.semantic_output.parent.mkdir(parents=True, exist_ok=True)
    args.snapshot_output.parent.mkdir(parents=True, exist_ok=True)
    args.semantic_output.write_text(json.dumps(semantic, indent=2, sort_keys=True) + "\n", "utf-8")
    args.snapshot_output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", "utf-8")
    print(json.dumps(semantic["summary"], sort_keys=True))
    print(f"semantic_graph={args.semantic_output}")
    print(f"github_snapshot={args.snapshot_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
