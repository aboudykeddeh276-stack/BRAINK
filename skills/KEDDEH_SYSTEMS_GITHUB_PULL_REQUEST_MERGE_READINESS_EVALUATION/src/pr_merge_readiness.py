#!/usr/bin/env python3
"""
Pull Request Merge Readiness Evaluation
=========================================
Evaluates a single pull request against deterministic merge-readiness criteria
and emits a structured JSON verdict.

Criteria evaluated (all must pass for MERGE_READY)
---------------------------------------------------
    1. PR is not a draft.
    2. Most recent CI workflow run on the PR branch concluded with "success".
    3. PR has no merge conflicts (mergeable state is "clean" or "has_hooks").
    4. PR has no outstanding review requests.

Usage
-----
    python3 pr_merge_readiness.py --owner OWNER --repo REPO --pr PR_NUMBER [--token TOKEN]

Environment variables
---------------------
    GITHUB_TOKEN    GitHub personal access token.

Output (stdout)
---------------
    {
      "evaluated_at": "<ISO-8601>",
      "repository": "<owner>/<repo>",
      "pull_request": int,
      "verdict": "MERGE_READY" | "BLOCKED_BY_CI" | "BLOCKED_BY_DRAFT"
                 | "BLOCKED_BY_CONFLICT" | "BLOCKED_BY_REVIEW" | "UNKNOWN",
      "checks": {
        "is_draft": bool,
        "ci_conclusion": "success" | "failure" | "pending" | "unknown",
        "mergeable_state": str | null,
        "has_review_requests": bool
      },
      "blocking_reasons": [str]
    }

Exit codes
----------
    0   Evaluation completed and verdict is MERGE_READY.
    2   Evaluation completed and PR is blocked.
    1   Could not evaluate (API error, missing token, invalid PR number).
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
        req.add_header("Authorization", f"******")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_ci_conclusion(owner: str, repo: str, branch: str, token: str) -> str:
    try:
        data = _api_get(
            f"/repos/{owner}/{repo}/actions/runs?branch={branch}&per_page=10", token
        )
        runs = data.get("workflow_runs", [])
        completed = [r for r in runs if r.get("status") == "completed"]
        if not completed:
            in_progress = [r for r in runs if r.get("status") in ("in_progress", "queued")]
            return "pending" if in_progress else "unknown"
        conclusion = completed[0].get("conclusion", "unknown")
        if conclusion in ("success", "failure"):
            return conclusion
        return "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def evaluate(owner: str, repo: str, pr_number: int, token: str) -> tuple[dict, int]:
    pr = _api_get(f"/repos/{owner}/{repo}/pulls/{pr_number}", token)

    is_draft = bool(pr.get("draft", False))
    branch = pr["head"]["ref"]
    mergeable_state = pr.get("mergeable_state")
    requested_reviewers = pr.get("requested_reviewers", [])
    requested_teams = pr.get("requested_teams", [])
    has_review_requests = bool(requested_reviewers or requested_teams)

    ci_conclusion = _get_ci_conclusion(owner, repo, branch, token)

    # Determine verdict in priority order.
    blocking_reasons: list[str] = []

    if is_draft:
        blocking_reasons.append("Pull request is a draft.")

    if ci_conclusion == "failure":
        blocking_reasons.append("CI workflow concluded with failure.")
    elif ci_conclusion == "pending":
        blocking_reasons.append("CI workflow is still in progress.")
    elif ci_conclusion == "unknown":
        blocking_reasons.append("CI status is unknown — no completed workflow run found.")

    if mergeable_state not in (None, "clean", "has_hooks", "unstable"):
        blocking_reasons.append(
            f"Pull request cannot be merged: mergeable_state is '{mergeable_state}'."
        )

    if has_review_requests:
        reviewers = [r.get("login", "?") for r in requested_reviewers]
        teams = [t.get("slug", "?") for t in requested_teams]
        all_reviewers = reviewers + [f"team:{t}" for t in teams]
        blocking_reasons.append(
            f"Outstanding review request(s): {', '.join(all_reviewers)}."
        )

    if not blocking_reasons:
        verdict = "MERGE_READY"
        exit_code = 0
    elif is_draft:
        verdict = "BLOCKED_BY_DRAFT"
        exit_code = 2
    elif ci_conclusion in ("failure", "pending", "unknown"):
        verdict = "BLOCKED_BY_CI"
        exit_code = 2
    elif mergeable_state not in (None, "clean", "has_hooks", "unstable"):
        verdict = "BLOCKED_BY_CONFLICT"
        exit_code = 2
    elif has_review_requests:
        verdict = "BLOCKED_BY_REVIEW"
        exit_code = 2
    else:
        verdict = "UNKNOWN"
        exit_code = 2

    report = {
        "evaluated_at": datetime.now(tz=timezone.utc).isoformat(),
        "repository": f"{owner}/{repo}",
        "pull_request": pr_number,
        "verdict": verdict,
        "checks": {
            "is_draft": is_draft,
            "ci_conclusion": ci_conclusion,
            "mergeable_state": mergeable_state,
            "has_review_requests": has_review_requests,
        },
        "blocking_reasons": blocking_reasons,
    }
    return report, exit_code


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate whether a pull request is ready to merge."
    )
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    args = parser.parse_args()

    if not args.token:
        print("ERROR: No GitHub token. Use --token or set GITHUB_TOKEN.", file=sys.stderr)
        sys.exit(1)

    try:
        report, exit_code = evaluate(args.owner, args.repo, args.pr, args.token)
    except urllib.error.HTTPError as exc:
        print(f"ERROR: GitHub API HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(report, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
