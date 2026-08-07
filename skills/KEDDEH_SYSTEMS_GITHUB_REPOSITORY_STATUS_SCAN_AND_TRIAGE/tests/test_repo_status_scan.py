"""
Tests for repo_status_scan.py
"""
import sys
import json
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import repo_status_scan  # noqa: E402
from repo_status_scan import _days_since, scan  # noqa: E402


class DaysSinceTests(unittest.TestCase):

    def test_today_is_zero_days(self):
        now_iso = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
        self.assertEqual(_days_since(now_iso), 0)

    def test_yesterday_is_one_day(self):
        yesterday = (datetime.now(tz=timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
        self.assertEqual(_days_since(yesterday), 1)

    def test_fourteen_days_ago(self):
        ts = (datetime.now(tz=timezone.utc) - timedelta(days=14)).isoformat().replace("+00:00", "Z")
        self.assertEqual(_days_since(ts), 14)


class ScanClassificationTests(unittest.TestCase):

    def _pr(self, number, draft, days_old, ci="success"):
        updated = (datetime.now(tz=timezone.utc) - timedelta(days=days_old)).isoformat()
        return {
            "number": number,
            "title": f"PR {number}",
            "draft": draft,
            "updated_at": updated,
            "html_url": f"https://github.com/x/y/pull/{number}",
            "head": {"ref": f"branch-{number}"},
            "_ci": ci,
        }

    def _run_scan_with_fake_prs(self, prs, stale_days=14):
        """Invoke the real scan() with network boundary functions stubbed.

        Returns the (ready, draft, stale, failing, merge_ready) tuple derived
        from the shipped scan() report, so the actual classification logic is
        exercised rather than a reimplementation.
        """
        ci_by_branch = {pr["head"]["ref"]: pr.pop("_ci") for pr in prs}
        original_paginated = repo_status_scan._api_get_paginated
        original_ci = repo_status_scan._get_ci_conclusion
        repo_status_scan._api_get_paginated = lambda path, token, per_page=100: prs
        repo_status_scan._get_ci_conclusion = (
            lambda owner, repo, branch, token: ci_by_branch.get(branch, "unknown")
        )
        try:
            report = scan("owner", "repo", stale_days, "token")
        finally:
            repo_status_scan._api_get_paginated = original_paginated
            repo_status_scan._get_ci_conclusion = original_ci
        return (
            report["ready_for_review"],
            report["draft"],
            report["stale_draft"],
            report["ci_failing"],
            report["merge_ready"],
        )

    def test_ready_non_draft_pr_classified_correctly(self):
        prs = [self._pr(1, draft=False, days_old=1, ci="success")]
        ready, draft, stale, failing, merge_ready = self._run_scan_with_fake_prs(prs)
        self.assertEqual(len(ready), 1)
        self.assertEqual(len(draft), 0)
        self.assertEqual(len(merge_ready), 1)

    def test_draft_pr_not_stale_classified_as_draft(self):
        prs = [self._pr(2, draft=True, days_old=5, ci="success")]
        ready, draft, stale, failing, merge_ready = self._run_scan_with_fake_prs(prs)
        self.assertEqual(len(draft), 1)
        self.assertEqual(len(stale), 0)
        self.assertEqual(len(ready), 0)

    def test_draft_pr_at_threshold_classified_as_stale(self):
        prs = [self._pr(3, draft=True, days_old=14, ci="unknown")]
        ready, draft, stale, failing, merge_ready = self._run_scan_with_fake_prs(prs)
        self.assertEqual(len(stale), 1)
        self.assertEqual(len(draft), 0)

    def test_ci_failing_pr_appears_in_ci_failing(self):
        prs = [self._pr(4, draft=False, days_old=2, ci="failure")]
        ready, draft, stale, failing, merge_ready = self._run_scan_with_fake_prs(prs)
        self.assertEqual(len(failing), 1)
        self.assertEqual(len(merge_ready), 0)

    def test_draft_pr_that_is_stale_and_failing_appears_in_both(self):
        prs = [self._pr(5, draft=True, days_old=20, ci="failure")]
        ready, draft, stale, failing, merge_ready = self._run_scan_with_fake_prs(prs)
        self.assertEqual(len(stale), 1)
        self.assertEqual(len(failing), 1)


if __name__ == "__main__":
    unittest.main()
