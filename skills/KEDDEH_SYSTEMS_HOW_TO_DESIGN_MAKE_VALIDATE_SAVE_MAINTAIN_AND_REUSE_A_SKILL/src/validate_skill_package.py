#!/usr/bin/env python3
"""
Skill Package Validator
=======================
Validates a skill directory against the normative requirements defined in:

    KEDDEH_SYSTEMS_HOW_TO_DESIGN_MAKE_VALIDATE_SAVE_MAINTAIN_AND_REUSE_A_SKILL

Usage
-----
    python3 validate_skill_package.py <skill_directory> [--strict]

Arguments
---------
    skill_directory     Filesystem path to the root of the skill package.
    --strict            Treat warnings as failures (default: off).

Output (stdout)
---------------
    JSON report with schema:
    {
      "skill_directory": str,
      "verdict": "SKILL_PACKAGE_VALID" | "SKILL_PACKAGE_INVALID",
      "checks": [
        {
          "id": str,              -- machine-stable check identifier
          "name": str,            -- full semantic check name
          "result": "PASS" | "FAIL" | "WARN",
          "required": bool,       -- if true, FAIL makes the package invalid
          "finding": str          -- human-readable explanation
        }
      ],
      "summary": {
        "total": int,
        "passed": int,
        "failed": int,
        "warned": int
      }
    }

Exit codes
----------
    0   All required checks passed.
    1   One or more required checks failed, or an internal error occurred.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class Check(NamedTuple):
    id: str
    name: str
    required: bool


class CheckResult(NamedTuple):
    check: Check
    result: str   # "PASS" | "FAIL" | "WARN"
    finding: str


# ---------------------------------------------------------------------------
# Check registry
# ---------------------------------------------------------------------------

CHECKS = [
    Check(
        id="REQUIRED_FILES_ARE_PRESENT",
        name="Required files SKILL.md, manifest.json, and VERSION are present in the skill directory",
        required=True,
    ),
    Check(
        id="MANIFEST_IS_VALID_JSON",
        name="manifest.json parses as valid JSON without errors",
        required=True,
    ),
    Check(
        id="MANIFEST_CONTAINS_REQUIRED_FIELDS",
        name="manifest.json contains required fields: canonical_identifier, version, purpose, claim_boundary",
        required=True,
    ),
    Check(
        id="CANONICAL_IDENTIFIER_IS_SEMANTICALLY_STABLE",
        name="canonical_identifier contains only uppercase letters, digits, and underscores and is not empty",
        required=True,
    ),
    Check(
        id="VERSION_FILE_MATCHES_MANIFEST_VERSION",
        name="VERSION file content matches manifest.json version field after stripping whitespace",
        required=True,
    ),
    Check(
        id="SKILL_MD_CONTAINS_REQUIRED_SECTION_HEADINGS",
        name="SKILL.md contains required section headings: ## Purpose, ## Invariants, ## Assumptions",
        required=True,
    ),
    Check(
        id="CLAIM_BOUNDARY_IS_EXPLICIT_AND_BOOLEAN",
        name="claim_boundary in manifest.json is a non-empty object whose values are all boolean",
        required=True,
    ),
    Check(
        id="SRC_DIRECTORY_CONTAINS_AT_LEAST_ONE_PYTHON_FILE",
        name="src/ directory exists and contains at least one .py file",
        required=True,
    ),
    Check(
        id="TESTS_DIRECTORY_CONTAINS_AT_LEAST_ONE_TEST_FILE",
        name="tests/ directory exists and contains at least one file matching test_*.py or *_test.py",
        required=True,
    ),
    Check(
        id="MANIFEST_CANONICAL_IDENTIFIER_MATCHES_DIRECTORY_NAME",
        name="canonical_identifier in manifest.json matches the skill directory name (warning only)",
        required=False,
    ),
]


# ---------------------------------------------------------------------------
# Individual check implementations
# ---------------------------------------------------------------------------

def check_required_files_present(skill_dir: Path) -> tuple[str, str]:
    missing = [
        f for f in ("SKILL.md", "manifest.json", "VERSION")
        if not (skill_dir / f).is_file()
    ]
    if missing:
        return "FAIL", f"Missing required files: {', '.join(missing)}"
    return "PASS", "SKILL.md, manifest.json, and VERSION are all present"


def check_manifest_is_valid_json(skill_dir: Path) -> tuple[str, str]:
    manifest_path = skill_dir / "manifest.json"
    if not manifest_path.is_file():
        return "FAIL", "manifest.json not found — cannot parse"
    try:
        json.loads(manifest_path.read_text(encoding="utf-8"))
        return "PASS", "manifest.json parsed without errors"
    except json.JSONDecodeError as exc:
        return "FAIL", f"manifest.json is not valid JSON: {exc}"


def check_manifest_contains_required_fields(skill_dir: Path) -> tuple[str, str]:
    manifest_path = skill_dir / "manifest.json"
    if not manifest_path.is_file():
        return "FAIL", "manifest.json not found — cannot check fields"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "FAIL", "manifest.json is not valid JSON — cannot check fields"
    required = ("canonical_identifier", "version", "purpose", "claim_boundary")
    missing = [f for f in required if f not in manifest]
    if missing:
        return "FAIL", f"manifest.json is missing required fields: {', '.join(missing)}"
    return "PASS", "All required fields are present: " + ", ".join(required)


def check_canonical_identifier_is_semantically_stable(skill_dir: Path) -> tuple[str, str]:
    manifest_path = skill_dir / "manifest.json"
    if not manifest_path.is_file():
        return "FAIL", "manifest.json not found"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "FAIL", "manifest.json is not valid JSON"
    ident = manifest.get("canonical_identifier", "")
    if not ident:
        return "FAIL", "canonical_identifier is empty"
    if not re.fullmatch(r"[A-Z0-9_]+", ident):
        return "FAIL", (
            f"canonical_identifier '{ident}' contains characters outside A-Z, 0-9, _. "
            "Identifiers must be uppercase letters, digits, and underscores only."
        )
    return "PASS", f"canonical_identifier '{ident}' is semantically stable"


def check_version_matches_manifest(skill_dir: Path) -> tuple[str, str]:
    version_path = skill_dir / "VERSION"
    manifest_path = skill_dir / "manifest.json"
    if not version_path.is_file():
        return "FAIL", "VERSION file not found"
    if not manifest_path.is_file():
        return "FAIL", "manifest.json not found"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "FAIL", "manifest.json is not valid JSON"
    version_file = version_path.read_text(encoding="utf-8").strip()
    manifest_version = str(manifest.get("version", "")).strip()
    if not version_file:
        return "FAIL", "VERSION file is empty"
    if not manifest_version:
        return "FAIL", "manifest.json version field is empty"
    if version_file != manifest_version:
        return "FAIL", (
            f"VERSION file contains '{version_file}' "
            f"but manifest.json version is '{manifest_version}'"
        )
    return "PASS", f"VERSION and manifest.json both specify '{version_file}'"


def check_skill_md_section_headings(skill_dir: Path) -> tuple[str, str]:
    skill_path = skill_dir / "SKILL.md"
    if not skill_path.is_file():
        return "FAIL", "SKILL.md not found"
    content = skill_path.read_text(encoding="utf-8")
    required_headings = ("## Purpose", "## Invariants", "## Assumptions")
    missing = [h for h in required_headings if h not in content]
    if missing:
        return "FAIL", f"SKILL.md is missing required section headings: {', '.join(missing)}"
    return "PASS", "SKILL.md contains all required section headings"


def check_claim_boundary_is_explicit_and_boolean(skill_dir: Path) -> tuple[str, str]:
    manifest_path = skill_dir / "manifest.json"
    if not manifest_path.is_file():
        return "FAIL", "manifest.json not found"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "FAIL", "manifest.json is not valid JSON"
    cb = manifest.get("claim_boundary")
    if not isinstance(cb, dict):
        return "FAIL", "claim_boundary must be a JSON object"
    if not cb:
        return "FAIL", "claim_boundary is an empty object — at least one claim key is required"
    non_boolean = [k for k, v in cb.items() if not isinstance(v, bool)]
    if non_boolean:
        return "FAIL", (
            f"claim_boundary values must all be boolean. "
            f"Non-boolean values found for keys: {', '.join(non_boolean)}"
        )
    return "PASS", f"claim_boundary has {len(cb)} explicit boolean claim(s)"


def check_src_directory_has_python_file(skill_dir: Path) -> tuple[str, str]:
    src_dir = skill_dir / "src"
    if not src_dir.is_dir():
        return "FAIL", "src/ directory does not exist"
    python_files = list(src_dir.glob("*.py"))
    if not python_files:
        return "FAIL", "src/ directory exists but contains no .py files"
    names = [f.name for f in python_files]
    return "PASS", f"src/ contains {len(names)} Python file(s): {', '.join(names)}"


def check_tests_directory_has_test_file(skill_dir: Path) -> tuple[str, str]:
    tests_dir = skill_dir / "tests"
    if not tests_dir.is_dir():
        return "FAIL", "tests/ directory does not exist"
    test_files = list(tests_dir.glob("test_*.py")) + list(tests_dir.glob("*_test.py"))
    if not test_files:
        return "FAIL", "tests/ directory exists but contains no test_*.py or *_test.py files"
    names = [f.name for f in test_files]
    return "PASS", f"tests/ contains {len(names)} test file(s): {', '.join(names)}"


def check_identifier_matches_directory_name(skill_dir: Path) -> tuple[str, str]:
    manifest_path = skill_dir / "manifest.json"
    if not manifest_path.is_file():
        return "WARN", "manifest.json not found — cannot compare identifier to directory name"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "WARN", "manifest.json is not valid JSON — cannot compare"
    ident = manifest.get("canonical_identifier", "")
    dir_name = skill_dir.name
    if ident != dir_name:
        return "WARN", (
            f"canonical_identifier '{ident}' does not match directory name '{dir_name}'. "
            "Convention: directory name should equal canonical_identifier."
        )
    return "PASS", f"canonical_identifier matches directory name '{dir_name}'"


# ---------------------------------------------------------------------------
# Check dispatcher
# ---------------------------------------------------------------------------

_DISPATCH = {
    "REQUIRED_FILES_ARE_PRESENT": check_required_files_present,
    "MANIFEST_IS_VALID_JSON": check_manifest_is_valid_json,
    "MANIFEST_CONTAINS_REQUIRED_FIELDS": check_manifest_contains_required_fields,
    "CANONICAL_IDENTIFIER_IS_SEMANTICALLY_STABLE": check_canonical_identifier_is_semantically_stable,
    "VERSION_FILE_MATCHES_MANIFEST_VERSION": check_version_matches_manifest,
    "SKILL_MD_CONTAINS_REQUIRED_SECTION_HEADINGS": check_skill_md_section_headings,
    "CLAIM_BOUNDARY_IS_EXPLICIT_AND_BOOLEAN": check_claim_boundary_is_explicit_and_boolean,
    "SRC_DIRECTORY_CONTAINS_AT_LEAST_ONE_PYTHON_FILE": check_src_directory_has_python_file,
    "TESTS_DIRECTORY_CONTAINS_AT_LEAST_ONE_TEST_FILE": check_tests_directory_has_test_file,
    "MANIFEST_CANONICAL_IDENTIFIER_MATCHES_DIRECTORY_NAME": check_identifier_matches_directory_name,
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_validation(skill_dir: Path, strict: bool = False) -> tuple[dict, int]:
    """
    Execute all registered checks against skill_dir.

    Returns a tuple of (report_dict, exit_code).
    exit_code is 0 if SKILL_PACKAGE_VALID, 1 otherwise.
    """
    results: list[CheckResult] = []

    for check in CHECKS:
        fn = _DISPATCH.get(check.id)
        if fn is None:
            results.append(CheckResult(check, "FAIL", f"No implementation registered for check id '{check.id}'"))
            continue
        try:
            result, finding = fn(skill_dir)
        except Exception as exc:  # noqa: BLE001
            result = "FAIL"
            finding = f"Check raised an unexpected exception: {exc}"
        results.append(CheckResult(check, result, finding))

    # Determine overall verdict.
    # A required check that fails → INVALID.
    # If strict: a warning also → INVALID.
    failed_required = [
        r for r in results
        if r.check.required and r.result == "FAIL"
    ]
    warned = [r for r in results if r.result == "WARN"]

    invalid = bool(failed_required) or (strict and bool(warned))
    verdict = "SKILL_PACKAGE_INVALID" if invalid else "SKILL_PACKAGE_VALID"

    # Emit human-readable summary to stderr.
    for r in results:
        icon = {"PASS": "✓", "FAIL": "✗", "WARN": "⚠"}.get(r.result, "?")
        print(f"  {icon} [{r.result}] {r.check.name}", file=sys.stderr)
        if r.result != "PASS":
            print(f"        {r.finding}", file=sys.stderr)

    print(f"\n{verdict}", file=sys.stderr)

    report = {
        "skill_directory": str(skill_dir.resolve()),
        "verdict": verdict,
        "checks": [
            {
                "id": r.check.id,
                "name": r.check.name,
                "result": r.result,
                "required": r.check.required,
                "finding": r.finding,
            }
            for r in results
        ],
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.result == "PASS"),
            "failed": sum(1 for r in results if r.result == "FAIL"),
            "warned": sum(1 for r in results if r.result == "WARN"),
        },
    }
    exit_code = 0 if verdict == "SKILL_PACKAGE_VALID" else 1
    return report, exit_code


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a skill directory against the KEDDEH_SYSTEMS skill-making requirements.\n"
            "Exits 0 when the package is valid, 1 when it is invalid."
        )
    )
    parser.add_argument(
        "skill_directory",
        help="Path to the root directory of the skill package.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Treat warnings as failures.",
    )
    args = parser.parse_args()

    skill_dir = Path(args.skill_directory)
    if not skill_dir.is_dir():
        print(f"ERROR: '{skill_dir}' is not a directory or does not exist.", file=sys.stderr)
        sys.exit(1)

    report, exit_code = run_validation(skill_dir, strict=args.strict)
    print(json.dumps(report, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
