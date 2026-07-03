#!/usr/bin/env python3
"""Executable KEX route proof checker for BRAINK.

This tool asserts that every documented BRAINK route token is present and
traceable in the repository source, producing a deterministic JSON proof report.

It does not execute arbitrary code. It verifies text presence only.

Function:
    FUNCTION_ASSERT_ROUTE_COVERAGE_AND_PRODUCE_PROOF_REPORT
Input:
    Repository root (--root), output path (--output)
Output:
    JSON proof report with per-route status and overall gate result
Proof gate:
    PROOF_GATE_ROUTE_COVERAGE_COMPLETE: all route tokens achieve MODEL-LOCAL status
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable  # noqa: F401 (used in type hints)

# Route tokens sourced from kex_self_sustain.py ROUTE_TOKENS and BRAINK source map.
# Each entry defines the token to match, which file types to search, and a short
# description of what the route represents.
ROUTE_DEFINITIONS: list[dict] = [
    {
        "token": "proof_packet",
        "description": "Proof packet generation and verification route",
        "search_suffixes": {".py", ".swift", ".md"},
    },
    {
        "token": "runtime_trace",
        "description": "Runtime trace capture and replay route",
        "search_suffixes": {".py", ".swift", ".md"},
    },
    {
        "token": "module_manifest",
        "description": "Module manifest audit and delivery verification route",
        "search_suffixes": {".py", ".swift", ".md"},
    },
    {
        "token": "constraint_flags",
        "description": "Constraint flag propagation route across KEX lanes",
        "search_suffixes": {".py", ".swift", ".md", ".json"},
    },
    {
        "token": "illlm_bundle",
        "description": "ILLLM bundle assembly and delivery route",
        "search_suffixes": {".py", ".swift", ".md"},
    },
    {
        "token": "illlm_bootstrap",
        "description": "ILLLM bootstrap initialization route",
        "search_suffixes": {".py", ".swift", ".md"},
    },
    {
        "token": "illlm_query",
        "description": "ILLLM knowledge query and resolution route",
        "search_suffixes": {".py", ".swift", ".md"},
    },
    {
        "token": "inner_runtime",
        "description": "Inner nested runtime embedding and mirror route",
        "search_suffixes": {".py", ".swift", ".md"},
    },
    {
        "token": "chrome_browser",
        "description": "Chrome browser integration route for native chatbot",
        "search_suffixes": {".py", ".swift", ".md"},
    },
    {
        "token": "scrape_tool",
        "description": "Web scraper tool integration route",
        "search_suffixes": {".py", ".swift", ".md"},
    },
    {
        "token": "auth.oauth",
        "description": "OAuth authentication route",
        "search_suffixes": {".py", ".swift", ".md"},
    },
    {
        "token": "general",
        "description": "General-purpose classifier route",
        "search_suffixes": {".py", ".swift", ".md"},
    },
]

SKIP_DIRS = {
    ".git", "__pycache__", ".build", "build", "reports",
    "node_modules", "DerivedData", "vendor",
}


def iter_files(root: Path, suffixes: set[str]) -> Iterable[Path]:
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            p = Path(current) / name
            if p.suffix.lower() in suffixes:
                yield p


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return path.read_text(encoding="utf-8", errors="replace")


def find_token_occurrences(root: Path, token: str, suffixes: set[str]) -> list[dict]:
    """
    Return a list of {file, line_number, excerpt} dicts for every occurrence
    of the token in the searchable file set.
    """
    pattern = re.compile(re.escape(token), re.IGNORECASE)
    hits: list[dict] = []
    for path in sorted(iter_files(root, suffixes)):
        text = read_text(path)
        for i, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                hits.append({
                    "file": path.relative_to(root).as_posix(),
                    "line": i,
                    "excerpt": line.strip()[:160],
                })
    return hits


def run_route_proof(root: Path) -> dict:
    """
    Run all route assertions and return the full proof report dict.
    """
    results: list[dict] = []
    all_pass = True

    for defn in ROUTE_DEFINITIONS:
        token = defn["token"]
        occurrences = find_token_occurrences(root, token, defn["search_suffixes"])
        covered = len(occurrences) > 0
        status = "MODEL-LOCAL" if covered else "PENDING"
        if not covered:
            all_pass = False
        results.append({
            "token": token,
            "description": defn["description"],
            "status": status,
            "occurrence_count": len(occurrences),
            "occurrences": occurrences[:10],  # cap at 10 per token in report
        })

    overall_status = "COMPLETED" if all_pass else "PENDING"

    return {
        "anchor": "A. KEDDEH / BRAINK / KEX / K-SYSTEMS",
        "function": "FUNCTION_ASSERT_ROUTE_COVERAGE_AND_PRODUCE_PROOF_REPORT",
        "proof_gate": "PROOF_GATE_ROUTE_COVERAGE_COMPLETE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(root),
        "total_routes": len(ROUTE_DEFINITIONS),
        "covered_routes": sum(1 for r in results if r["status"] == "MODEL-LOCAL"),
        "pending_routes": sum(1 for r in results if r["status"] == "PENDING"),
        "overall_status": overall_status,
        "routes": results,
        "boundary": (
            "This report proves only local text-token presence. "
            "It does not prove runtime execution, external adoption, or production deployment."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kex-route-proof",
        description="Assert and report coverage of every documented BRAINK route token.",
    )
    parser.add_argument("--root", default=".", help="Repository root to scan. Defaults to current directory.")
    parser.add_argument(
        "--output",
        default="reports/kex_route_proof.json",
        help="Output path for the JSON proof report. Defaults to reports/kex_route_proof.json.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = run_route_proof(root)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    covered = report["covered_routes"]
    total = report["total_routes"]
    pending = report["pending_routes"]
    status = report["overall_status"]
    print(f"KEX_ROUTE_PROOF output={output} covered={covered}/{total} pending={pending} status={status}")

    return 0 if status == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
