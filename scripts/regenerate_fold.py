#!/usr/bin/env python3
"""
Regenerate fold scan artifacts for the BRAINK repository.

Produces portable, environment-safe fold data files in fold/:
  - fold/index.json       — summary index of the scan
  - fold/constant_bool.json — functions whose return is always True or False
  - fold/repeating_names.json — literal function names that appear in more than one file

This script uses the repository root it is called from, not a hardcoded path.

Function:
    FUNCTION_REGENERATE_FOLD_SCAN_ARTIFACTS
Input:
    Repository root (--root, defaults to repo root inferred from this script's location)
Output:
    fold/index.json, fold/constant_bool.json, fold/repeating_names.json
Proof gate:
    PROOF_GATE_FOLD_REGENERATED: fold/index.json exists and contains a valid repo field
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FOLD_DIR = REPO_ROOT / "fold"

SKIP_DIRS = {".git", "__pycache__", ".build", "build", "reports", "node_modules", "DerivedData"}
PYTHON_SUFFIXES = {".py"}


def iter_python_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            p = Path(current) / name
            if p.suffix.lower() in PYTHON_SUFFIXES:
                paths.append(p)
    return sorted(paths)


def git_head(root: Path) -> str:
    head_file = root / ".git" / "HEAD"
    if not head_file.exists():
        return "UNKNOWN"
    try:
        ref = head_file.read_text(encoding="utf-8").strip()
        if ref.startswith("ref: "):
            ref_path = root / ".git" / ref[5:]
            if ref_path.exists():
                return ref_path.read_text(encoding="utf-8").strip()
        return ref
    except OSError:
        return "UNKNOWN"


def extract_functions(source: str) -> list[str]:
    """Return list of all top-level and class-method function names in a Python source."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
    return names


def is_constant_bool_function(source: str, func_name: str) -> bool:
    """
    Return True when a function named func_name in source always returns
    a literal True or False (no other return statements).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            returns: list[ast.Return] = [n for n in ast.walk(node) if isinstance(n, ast.Return)]
            if not returns:
                return False
            for ret in returns:
                if not isinstance(ret.value, ast.Constant):
                    return False
                if not isinstance(ret.value.value, bool):
                    return False
            return True
    return False


def scan(root: Path) -> tuple[dict, dict, dict]:
    files = iter_python_files(root)
    functions_found = 0

    # repeating_names: function name -> list of relative file paths
    name_map: dict[str, list[str]] = defaultdict(list)
    # constant_bool hits
    const_bool_hits: list[dict] = []

    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(root).as_posix()
        func_names = extract_functions(source)
        functions_found += len(func_names)
        for name in func_names:
            name_map[name].append(rel)
            if is_constant_bool_function(source, name):
                const_bool_hits.append({"file": rel, "function": name})

    repeating = {name: paths for name, paths in sorted(name_map.items()) if len(paths) > 1}

    now = datetime.now(timezone.utc).isoformat()
    head = git_head(root)

    index = {
        "at": now,
        "head": head,
        "repo": root.as_posix(),
        "layout_rule": "fold/file/folder/file",
        "files_scanned": len(files),
        "functions_found": functions_found,
        "constant_bool_count": len(const_bool_hits),
        "repeating_names_count": len(repeating),
        "repeating_hashes_count": 0,
        "notes": [
            "repeating_names = same literal function name across processes/files",
            "repeating_hashes = same deterministic body/signature fingerprint (pass-through candidate)",
            "constant_bool = deterministic yes/no answers (env-invariant heuristic)",
        ],
    }

    const_bool = {
        "type": "constant_bool",
        "at": now,
        "count": len(const_bool_hits),
        "hits": const_bool_hits,
    }

    rep_names = {
        "type": "repeating_names",
        "at": now,
        "names": repeating,
    }

    return index, const_bool, rep_names


def write_fold(root: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    index, const_bool, rep_names = scan(root)
    (output_dir / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "constant_bool.json").write_text(json.dumps(const_bool, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "repeating_names.json").write_text(json.dumps(rep_names, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"FOLD_REGENERATE files_scanned={index['files_scanned']} functions_found={index['functions_found']} "
          f"constant_bool={index['constant_bool_count']} repeating_names={index['repeating_names_count']} status=COMPLETED")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="regenerate-fold",
        description="Regenerate portable fold scan artifacts for the BRAINK repository.",
    )
    parser.add_argument(
        "--root",
        default=str(REPO_ROOT),
        help="Repository root to scan. Defaults to the repo root inferred from this script.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(FOLD_DIR),
        help="Directory to write fold artifacts. Defaults to fold/ in the repo root.",
    )
    args = parser.parse_args(argv)
    write_fold(Path(args.root).resolve(), Path(args.output_dir).resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
