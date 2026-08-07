#!/usr/bin/env python3
"""
CI Failure Investigation and Root Cause Classification
=======================================================
Fetches GitHub Actions workflow run job logs for a given run_id, parses the
failure output, classifies the root cause into a deterministic failure class,
and emits a structured JSON diagnosis.

Usage
-----
    python3 ci_failure_investigator.py --owner OWNER --repo REPO --run-id RUN_ID [--token TOKEN]

Environment variables
---------------------
    GITHUB_TOKEN    GitHub personal access token (used if --token is not provided).

Output (stdout)
---------------
    {
      "run_id": int,
      "repository": "<owner>/<repo>",
      "investigated_at": "<ISO-8601>",
      "overall_conclusion": "failure" | "success" | "unknown",
      "failed_jobs": [
        {
          "job_id": int,
          "job_name": str,
          "failed_step": str,
          "failure_line": str,
          "root_cause_class": str,
          "fix_hint": str
        }
      ]
    }

Failure classes
---------------
    MISSING_FILE_OR_DIRECTORY
    SYNTAX_ERROR_IN_SOURCE
    TEST_ASSERTION_FAILED
    DEPENDENCY_NOT_INSTALLED
    PERMISSION_DENIED
    NETWORK_OR_AUTHENTICATION_ERROR
    TIMEOUT
    UNKNOWN

Exit codes
----------
    0   Diagnosis produced. (Does not mean CI passed — check overall_conclusion.)
    1   Could not retrieve run information (auth error, network, invalid run_id).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


_GITHUB_API = "https://api.github.com"


def _api_get(path: str, token: str) -> Any:
    url = f"{_GITHUB_API}{path}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if token:
        req.add_header("Authorization", f"******")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _api_get_text(url: str, token: str) -> str:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if token:
        req.add_header("Authorization", f"******")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Failure classification
# ---------------------------------------------------------------------------

# Each entry: (pattern, root_cause_class, fix_hint)
_FAILURE_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"No such file or directory|not found.*directory|cannot find.*file|FileNotFoundError",
        "MISSING_FILE_OR_DIRECTORY",
        "Ensure the required directory or file is created (e.g. mkdir -p) before the step that needs it.",
    ),
    (
        r"SyntaxError|IndentationError|unexpected indent|invalid syntax|ParseError",
        "SYNTAX_ERROR_IN_SOURCE",
        "Fix the syntax error in the indicated source file. Run python3 -m py_compile <file> locally.",
    ),
    (
        r"AssertionError|FAILED.*test|assertion.*failed|assert.*False|test.*FAILED",
        "TEST_ASSERTION_FAILED",
        "A test assertion evaluated to false. Review the test output and fix the implementation or the test oracle.",
    ),
    (
        r"ModuleNotFoundError|ImportError|No module named|command not found|not installed",
        "DEPENDENCY_NOT_INSTALLED",
        "Install the missing dependency in the workflow before running the failing step.",
    ),
    (
        r"Permission denied|EACCES|Access is denied",
        "PERMISSION_DENIED",
        "Check file and directory permissions. Ensure the workflow step has required access rights.",
    ),
    (
        r"getaddrinfo failed|Connection refused|Unable to connect|SSL.*error|401 Unauthorized|403 Forbidden|authentication.*failed",
        "NETWORK_OR_AUTHENTICATION_ERROR",
        "Verify the token or credentials are valid and the network target is reachable from the runner.",
    ),
    (
        r"timed out|timeout|ETIMEDOUT|exceeded.*time.*limit",
        "TIMEOUT",
        "Increase the timeout for the failing step, or investigate why the operation is taking longer than expected.",
    ),
]


def _classify_failure(log_text: str) -> tuple[str, str]:
    """
    Classify the root cause of a failure from log text.

    Returns (root_cause_class, fix_hint).
    """
    for pattern, cls, hint in _FAILURE_PATTERNS:
        if re.search(pattern, log_text, re.IGNORECASE):
            return cls, hint
    return "UNKNOWN", "Inspect the full log manually. No pattern matched a known failure class."


def _extract_failure_line(log_text: str) -> str:
    """
    Return the most informative failure line from the log.
    Prefers lines containing '##[error]' or 'Error:'.
    """
    lines = log_text.splitlines()
    for line in lines:
        if "##[error]" in line:
            return line.replace("##[error]", "").strip()
    for line in lines:
        if re.search(r"\bError\b|\bFAIL\b|\bfailed\b", line, re.IGNORECASE):
            stripped = line.strip()
            if stripped:
                return stripped
    return lines[-1].strip() if lines else ""


def _get_failed_step_name(job: dict) -> str:
    for step in job.get("steps", []):
        if step.get("conclusion") == "failure":
            return step.get("name", "unknown step")
    return "unknown step"


# ---------------------------------------------------------------------------
# Investigation logic
# ---------------------------------------------------------------------------

def investigate(owner: str, repo: str, run_id: int, token: str) -> dict:
    run = _api_get(f"/repos/{owner}/{repo}/actions/runs/{run_id}", token)
    overall_conclusion = run.get("conclusion", "unknown") or "unknown"

    jobs_data = _api_get(
        f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs?per_page=100", token
    )
    failed_jobs_data = [j for j in jobs_data.get("jobs", []) if j.get("conclusion") == "failure"]

    failed_jobs: list[dict] = []
    for job in failed_jobs_data:
        job_id = job["id"]
        job_name = job.get("name", "unknown")
        failed_step = _get_failed_step_name(job)

        log_text = ""
        try:
            logs_url = f"{_GITHUB_API}/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"
            log_text = _api_get_text(logs_url, token)
        except Exception:  # noqa: BLE001
            log_text = ""

        if not log_text:
            root_cause = "UNKNOWN"
            fix_hint = "Could not retrieve job logs."
            failure_line = ""
        else:
            root_cause, fix_hint = _classify_failure(log_text)
            failure_line = _extract_failure_line(log_text)

        failed_jobs.append({
            "job_id": job_id,
            "job_name": job_name,
            "failed_step": failed_step,
            "failure_line": failure_line,
            "root_cause_class": root_cause,
            "fix_hint": fix_hint,
        })

    return {
        "run_id": run_id,
        "repository": f"{owner}/{repo}",
        "investigated_at": datetime.now(tz=timezone.utc).isoformat(),
        "overall_conclusion": overall_conclusion,
        "failed_jobs": failed_jobs,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Investigate a GitHub Actions workflow run and classify failure root causes."
        )
    )
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    args = parser.parse_args()

    if not args.token:
        print("ERROR: No GitHub token. Use --token or set GITHUB_TOKEN.", file=sys.stderr)
        sys.exit(1)

    try:
        report = investigate(args.owner, args.repo, args.run_id, args.token)
    except urllib.error.HTTPError as exc:
        print(f"ERROR: GitHub API HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
