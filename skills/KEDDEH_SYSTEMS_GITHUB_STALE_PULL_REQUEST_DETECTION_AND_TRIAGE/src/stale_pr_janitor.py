#!/usr/bin/env python3
"""
Stale Pull Request Detection and Triage
=======================================
Identifies draft pull requests that have had no activity for longer than a
configurable threshold, classifies them as stale, and emits a structured JSON
report. Optionally posts a triage comment to each stale PR.

Usage
-----
    python3 stale_pr_janitor.py --owner OWNER --repo REPO [--stale-days N] [--comment] [--token TOKEN]

Environment variables
---------------------
    GITHUB_TOKEN    GitHub personal access token.

Arguments
---------
    --owner         GitHub repository owner.
    --repo          GitHub repository name.
    --stale-days    Days without update threshold (default: 14).
    --comment       If set, post a triage comment to each stale PR.
    --token         GitHub token (falls back to GITHUB_TOKEN).

Output (stdout)
---------------
    {
      "scan_timestamp": "<ISO-8601>",
      "repository": "<owner>/<repo>",
      "stale_threshold_days": int,
      "stale_prs": [
        {
          "number": int,
          "title": str,
          "branch": str,
          "last_updated": "<ISO-8601>",
          "days_stale": int,
          "html_url": str,
          "comment_posted": bool
        }
      ]
    }

Exit codes
----------
    0   Report produced successfully.
    1   A required argument is missing or the API returned an error.
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


_GITHUB_API = "https://api.github.com"


def _api_get(path: str, token: str) -> Any:
    url = f"{_GITHUB_API}{path}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _api_post(path: str, body: dict, token: str) -> Any:
    url = f"{_GITHUB_API}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _days_since(iso_timestamp: str) -> int:
    updated = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    return (datetime.now(tz=timezone.utc) - updated).days


_STALE_COMMENT = (
    "**Automated triage notice (Keddeh Systems stale-PR janitor)**\n\n"
    "This draft pull request has had no activity for {days} day(s) "
    "and has been classified as **stale**.\n\n"
    "Please update this PR, mark it ready for review, or close it if it is no "
    "longer needed. No action will be taken automatically."
)


def detect_stale(owner: str, repo: str, stale_days: int, post_comment: bool, token: str) -> dict:
    page = 1
    prs: list[Any] = []
    while True:
        batch = _api_get(
            f"/repos/{owner}/{repo}/pulls?state=open&per_page=100&page={page}", token
        )
        prs.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    stale_prs: list[dict] = []
    for pr in prs:
        if not pr.get("draft", False):
            continue
        days = _days_since(pr["updated_at"])
        if days < stale_days:
            continue

        comment_posted = False
        if post_comment:
            try:
                _api_post(
                    f"/repos/{owner}/{repo}/issues/{pr['number']}/comments",
                    {"body": _STALE_COMMENT.format(days=days)},
                    token,
                )
                comment_posted = True
            except urllib.error.HTTPError as exc:
                print(
                    f"WARN: Could not post comment to PR #{pr['number']}: HTTP {exc.code}",
                    file=sys.stderr,
                )

        stale_prs.append({
            "number": pr["number"],
            "title": pr["title"],
            "branch": pr["head"]["ref"],
            "last_updated": pr["updated_at"],
            "days_stale": days,
            "html_url": pr["html_url"],
            "comment_posted": comment_posted,
        })

    return {
        "scan_timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "repository": f"{owner}/{repo}",
        "stale_threshold_days": stale_days,
        "stale_prs": stale_prs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect stale draft pull requests in a GitHub repository."
    )
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--stale-days", type=int, default=14)
    parser.add_argument(
        "--comment",
        action="store_true",
        default=False,
        help="Post a triage comment to each stale PR.",
    )
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    args = parser.parse_args()

    if not args.token:
        print("ERROR: No GitHub token. Use --token or set GITHUB_TOKEN.", file=sys.stderr)
        sys.exit(1)

    try:
        report = detect_stale(args.owner, args.repo, args.stale_days, args.comment, args.token)
    except urllib.error.HTTPError as exc:
        print(f"ERROR: GitHub API HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
