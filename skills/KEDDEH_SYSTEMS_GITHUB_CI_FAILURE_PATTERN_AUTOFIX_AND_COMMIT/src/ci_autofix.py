#!/usr/bin/env python3
"""
CI Failure Pattern Autofix and Commit
======================================
Reads a structured JSON diagnosis produced by ci_failure_investigator.py,
selects an applicable deterministic fix handler for each failure class,
applies the fix to the repository files in-place, and produces a structured
JSON report of what was changed.

Supported fix patterns
----------------------
    MISSING_FILE_OR_DIRECTORY
        Parses the failure line to extract the missing path. Locates the
        GitHub Actions workflow file that defines the failing job. Inserts a
        `mkdir -p <path>` command into the first `run:` block of the failing
        step's parent job, as close to the start as possible without
        reordering existing commands.

    All other classes
        Reported as not_applicable with the reason that automated fixing is
        not safe for that failure class. No files are modified.

Usage
-----
    python3 ci_autofix.py --diagnosis-file DIAGNOSIS.json [--root .] [--dry-run]

Arguments
---------
    --diagnosis-file    Path to JSON diagnosis from ci_failure_investigator.
    --root              Repository root directory (default: current directory).
    --dry-run           Report what would be changed without writing any files.

Output (stdout)
---------------
    {
      "applied_at": "<ISO-8601>",
      "repository_root": str,
      "dry_run": bool,
      "fixes_applied": [
        {
          "job_name": str,
          "root_cause_class": str,
          "fix_type": str,
          "file_modified": str,
          "change_description": str,
          "applied": bool
        }
      ],
      "fixes_not_applicable": [
        {
          "job_name": str,
          "root_cause_class": str,
          "reason": str
        }
      ]
    }

Exit codes
----------
    0   Report produced. (Does not mean fixes were applied — check fixes_applied[].applied.)
    1   The diagnosis file could not be read, or an unexpected internal error occurred.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Path extraction from failure lines
# ---------------------------------------------------------------------------

def _extract_missing_path(failure_line: str) -> str | None:
    """
    Attempt to extract the missing filesystem path from a failure line.

    Handles patterns such as:
      tee: evidence/some_file.json: No such file or directory
      /usr/bin/some-cmd: cannot access 'dir/file': No such file or directory
      FileNotFoundError: [Errno 2] No such file or directory: 'path/to/file'
    """
    # Pattern: tee: PATH: No such file or directory
    m = re.search(r"tee: ([^:]+): No such file or directory", failure_line)
    if m:
        return str(Path(m.group(1)).parent)

    # Pattern: 'PATH': No such file or directory
    m = re.search(r"'([^']+)': No such file or directory", failure_line)
    if m:
        p = m.group(1)
        # If the path has an extension, return the parent directory; else the path itself.
        candidate = Path(p)
        return str(candidate.parent) if candidate.suffix else p

    # Pattern: FileNotFoundError: ... 'PATH'
    m = re.search(r"FileNotFoundError[^']*'([^']+)'", failure_line)
    if m:
        candidate = Path(m.group(1))
        return str(candidate.parent) if candidate.suffix else str(candidate)

    return None


# ---------------------------------------------------------------------------
# Workflow file location
# ---------------------------------------------------------------------------

def _find_workflow_for_job(root: Path, job_name: str) -> Path | None:
    """
    Search .github/workflows/ for a YAML file that contains the job name.

    Returns the first matching file, or None.
    """
    workflows_dir = root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return None
    for wf_file in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml")):
        content = wf_file.read_text(encoding="utf-8")
        if job_name in content:
            return wf_file
    return None


# ---------------------------------------------------------------------------
# Fix handler: MISSING_FILE_OR_DIRECTORY
# ---------------------------------------------------------------------------

def _apply_missing_directory_fix(
    root: Path,
    job_name: str,
    failure_line: str,
    dry_run: bool,
) -> tuple[bool, str, str]:
    """
    Insert a `mkdir -p <path>` command into the workflow for the failing job.

    Returns (applied: bool, file_modified: str, change_description: str).
    """
    missing_path = _extract_missing_path(failure_line)
    if not missing_path:
        return (
            False,
            "",
            f"Could not extract missing path from failure line: {failure_line!r}",
        )

    wf_file = _find_workflow_for_job(root, job_name)
    if wf_file is None:
        return (
            False,
            "",
            f"Could not locate a workflow file containing job '{job_name}' under {root}/.github/workflows/",
        )

    content = wf_file.read_text(encoding="utf-8")
    mkdir_cmd = f"mkdir -p {missing_path}"

    # Check whether mkdir for this path is already present.
    if mkdir_cmd in content or f"mkdir -p {missing_path}" in content:
        return (
            False,
            str(wf_file),
            f"`{mkdir_cmd}` already exists in {wf_file.name} — no change needed.",
        )

    # Insert the mkdir into the first `run: |` block that belongs to this job.
    # Strategy: find the job definition, then the first `run: |` line within it,
    # and prepend the mkdir command on the next line, preserving indentation.
    lines = content.splitlines(keepends=True)
    in_job = False
    insert_at: int | None = None
    run_indent = ""

    for i, line in enumerate(lines):
        stripped = line.lstrip()

        # Detect job start (e.g. "  job-name:")
        if not in_job:
            if stripped.startswith(f"{job_name}:"):
                in_job = True
            continue

        # Inside the job: find the first `run: |`
        if re.match(r"\s+run:\s+\|", line):
            run_indent = re.match(r"(\s+)", line).group(1) + "  "  # type: ignore[union-attr]
            insert_at = i + 1
            break

        # Stop if we reach the next top-level job definition.
        if re.match(r"  \S", line) and not stripped.startswith("-") and stripped.endswith(":"):
            break

    if insert_at is None:
        # Fallback: append a new step before the first step in the job.
        # This is conservative — report inability rather than corrupt the YAML.
        return (
            False,
            str(wf_file),
            (
                f"Could not locate a `run: |` block in job '{job_name}' in {wf_file.name}. "
                f"Manual fix required: add `{mkdir_cmd}` before the failing step."
            ),
        )

    # Insert the mkdir line.
    mkdir_line = f"{run_indent}{mkdir_cmd}\n"
    lines.insert(insert_at, mkdir_line)
    new_content = "".join(lines)

    if not dry_run:
        wf_file.write_text(new_content, encoding="utf-8")

    return (
        True,
        str(wf_file),
        (
            f"Inserted `{mkdir_cmd}` into job '{job_name}' in {wf_file.name} "
            f"at line {insert_at + 1}."
            + (" (dry run — file not written)" if dry_run else "")
        ),
    )


# ---------------------------------------------------------------------------
# Main apply logic
# ---------------------------------------------------------------------------

def apply_fixes(diagnosis: dict, root: Path, dry_run: bool) -> dict:
    fixes_applied: list[dict] = []
    fixes_not_applicable: list[dict] = []

    for job_info in diagnosis.get("failed_jobs", []):
        job_name = job_info.get("job_name", "")
        root_cause = job_info.get("root_cause_class", "UNKNOWN")
        failure_line = job_info.get("failure_line", "")

        if root_cause == "MISSING_FILE_OR_DIRECTORY":
            applied, file_modified, description = _apply_missing_directory_fix(
                root, job_name, failure_line, dry_run
            )
            fixes_applied.append({
                "job_name": job_name,
                "root_cause_class": root_cause,
                "fix_type": "INSERT_MKDIR_P_INTO_WORKFLOW",
                "file_modified": file_modified,
                "change_description": description,
                "applied": applied,
            })
        else:
            fixes_not_applicable.append({
                "job_name": job_name,
                "root_cause_class": root_cause,
                "reason": (
                    f"Automated fixing of '{root_cause}' is not safe and requires human review. "
                    f"Fix hint from diagnosis: {job_info.get('fix_hint', '')}"
                ),
            })

    return {
        "applied_at": datetime.now(tz=timezone.utc).isoformat(),
        "repository_root": str(root.resolve()),
        "dry_run": dry_run,
        "fixes_applied": fixes_applied,
        "fixes_not_applicable": fixes_not_applicable,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Apply deterministic fixes to known CI failure patterns "
            "based on a diagnosis produced by ci_failure_investigator.py."
        )
    )
    parser.add_argument("--diagnosis-file", required=True, help="Path to JSON diagnosis file.")
    parser.add_argument("--root", default=".", help="Repository root directory (default: .).")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Report changes without writing files.",
    )
    args = parser.parse_args()

    diagnosis_path = Path(args.diagnosis_file)
    if not diagnosis_path.is_file():
        print(f"ERROR: Diagnosis file '{diagnosis_path}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        diagnosis = json.loads(diagnosis_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: Diagnosis file is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    root = Path(args.root).resolve()
    report = apply_fixes(diagnosis, root, args.dry_run)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
