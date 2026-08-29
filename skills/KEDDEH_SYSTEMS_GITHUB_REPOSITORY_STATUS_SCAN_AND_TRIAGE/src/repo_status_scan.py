#!/usr/bin/env python3
"""
Repository Status Scan and Triage
==================================
Queries the GitHub REST API for all open pull requests in a repository,
fetches the latest CI workflow run conclusion per branch, and produces a
structured JSON triage report categorising each PR.

This is an executable skill module in the Keddeh Systems repo-steward skill set.

Usage
-----
    python3 repo_status_scan.py --owner OWNER --repo REPO [--stale-days N] [--token TOKEN]

Environment variables
---------------------
    GITHUB_TOKEN    GitHub personal access token (used if --token is not provided).

Arguments
---------
    --owner         GitHub repository owner (user or organisation name).
    --repo          GitHub repository name.
    --stale-days    Number of days without update to classify a draft PR as stale (default: 14).
    --token         GitHub personal access token. Falls back to GITHUB_TOKEN env var.

Output (stdout)
---------------
    JSON report with schema:

    {
      "scan_timestamp": "<ISO-8601>",
      "repository": "<owner>/<repo>",
      "stale_threshold_days": int,
      "ready_for_review": [<PR entry>, ...],
      "draft": [<PR entry>, ...],
      "stale_draft": [<PR entry>, ...],
      "ci_failing": [<PR entry>, ...],
      "merge_ready": [<PR entry>, ...]
    }

    PR entry schema:

    {
      "number": int,
      "title": str,
      "branch": str,
      "is_draft": bool,
      "ci_conclusion": "success" | "failure" | "pending" | "unknown",
      "days_since_update": int,
      "html_url": str
    }

    PR entries may appear in more than one category (e.g. a non-draft PR can
    appear in both ready_for_review and ci_failing).

Exit codes
----------
    0   Report produced successfully.
    1   A required argument is missing, authentication failed, or the API
        returned an unexpected error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

_GITHUB_API = "https://api.github.com"


def _api_get(path: str, token: str) -> Any:
    """
    Perform a GET request to the GitHub REST API.

    Raises urllib.error.HTTPError on 4xx/5xx.
    Returns the parsed JSON body.
    """
    url = f"{_GITHUB_API}{path}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _api_get_paginated(path: str, token: str, per_page: int = 100) -> list[Any]:
    """Fetch all pages of a paginated GitHub API endpoint."""
    results: list[Any] = []
    page = 1
    while True:
        sep = "&" if "?" in path else "?"
        page_path = f"{path}{sep}per_page={per_page}&page={page}"
        data = _api_get(page_path, token)
        if isinstance(data, list):
            results.extend(data)
            if len(data) < per_page:
                break
        else:
            results.append(data)
            break
        page += 1
    return results


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _days_since(iso_timestamp: str) -> int:
    """Return the number of whole days between an ISO-8601 timestamp and now."""
    updated = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    delta = datetime.now(tz=timezone.utc) - updated
    return delta.days


def _get_ci_conclusion(owner: str, repo: str, branch: str, token: str) -> str:
    """
    Return the conclusion of the most recent completed workflow run on a branch.

    Returns one of: "success", "failure", "pending", "unknown".
    """
    try:
        path = f"/repos/{owner}/{repo}/actions/runs?branch={branch}&per_page=10"
        data = _api_get(path, token)
        runs = data.get("workflow_runs", [])
        completed = [r for r in runs if r.get("status") == "completed"]
        if not completed:
            in_progress = [r for r in runs if r.get("status") in ("in_progress", "queued")]
            return "pending" if in_progress else "unknown"
        most_recent = completed[0]
        conclusion = most_recent.get("conclusion", "unknown")
        if conclusion in ("success", "failure"):
            return conclusion
        if conclusion in ("cancelled", "skipped"):
            return "unknown"
        return "unknown"
    except urllib.error.HTTPError:
        return "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def scan(owner: str, repo: str, stale_days: int, token: str) -> dict:
    """
    Scan all open pull requests and classify them.

    Returns the full triage report as a dict.
    """
    prs = _api_get_paginated(f"/repos/{owner}/{repo}/pulls?state=open", token)

    ready_for_review: list[dict] = []
    draft: list[dict] = []
    stale_draft: list[dict] = []
    ci_failing: list[dict] = []
    merge_ready: list[dict] = []

    for pr in prs:
        number = pr["number"]
        title = pr["title"]
        branch = pr["head"]["ref"]
        is_draft = bool(pr.get("draft", False))
        updated_at = pr["updated_at"]
        html_url = pr["html_url"]
        days_since = _days_since(updated_at)

        ci = _get_ci_conclusion(owner, repo, branch, token)

        entry: dict = {
            "number": number,
            "title": title,
            "branch": branch,
            "is_draft": is_draft,
            "ci_conclusion": ci,
            "days_since_update": days_since,
            "html_url": html_url,
        }

        if is_draft:
            if days_since >= stale_days:
                stale_draft.append(entry)
            else:
                draft.append(entry)
        else:
            ready_for_review.append(entry)

        if ci == "failure":
            ci_failing.append(entry)

        if (not is_draft) and ci == "success":
            merge_ready.append(entry)

    return {
        "scan_timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "repository": f"{owner}/{repo}",
        "stale_threshold_days": stale_days,
        "ready_for_review": ready_for_review,
        "draft": draft,
        "stale_draft": stale_draft,
        "ci_failing": ci_failing,
        "merge_ready": merge_ready,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Scan all open pull requests in a GitHub repository and produce a "
            "structured JSON triage report."
        )
    )
    parser.add_argument("--owner", required=True, help="GitHub repository owner.")
    parser.add_argument("--repo", required=True, help="GitHub repository name.")
    parser.add_argument(
        "--stale-days",
        type=int,
        default=14,
        help="Days without update before a draft PR is classified as stale (default: 14).",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN", ""),
        help="GitHub personal access token (falls back to GITHUB_TOKEN env var).",
    )
    args = parser.parse_args()

    if not args.token:
        print(
            "ERROR: No GitHub token provided. Use --token or set GITHUB_TOKEN.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        report = scan(args.owner, args.repo, args.stale_days, args.token)
    except urllib.error.HTTPError as exc:
        print(f"ERROR: GitHub API returned HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
