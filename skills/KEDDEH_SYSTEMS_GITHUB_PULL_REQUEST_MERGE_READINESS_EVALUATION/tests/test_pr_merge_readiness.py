"""
Tests for pr_merge_readiness.py

These tests exercise the real evaluate() function with the two network
boundary functions (_api_get, _get_ci_conclusion) deterministically stubbed,
so verdict logic is validated against the shipped implementation.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import pr_merge_readiness
from pr_merge_readiness import evaluate


def _fake_pr(draft=False, mergeable_state="clean", reviewers=None, teams=None):
    return {
        "number": 1,
        "title": "Test PR",
        "draft": draft,
        "head": {"ref": "test-branch"},
        "html_url": "https://github.com/x/y/pull/1",
        "mergeable_state": mergeable_state,
        "requested_reviewers": reviewers or [],
        "requested_teams": teams or [],
    }


class EvaluateMergeReadinessTests(unittest.TestCase):

    def _run_evaluate(self, pr_data, ci_conclusion="success"):
        """Invoke the real evaluate() with network calls deterministically stubbed."""
        original_api_get = pr_merge_readiness._api_get
        original_ci = pr_merge_readiness._get_ci_conclusion
        pr_merge_readiness._api_get = lambda path, token: pr_data
        pr_merge_readiness._get_ci_conclusion = (
            lambda owner, repo, branch, token: ci_conclusion
        )
        try:
            return evaluate("owner", "repo", pr_data["number"], "token")
        finally:
            pr_merge_readiness._api_get = original_api_get
            pr_merge_readiness._get_ci_conclusion = original_ci

    def test_clean_non_draft_pr_with_ci_success_is_merge_ready(self):
        report, exit_code = self._run_evaluate(_fake_pr(), ci_conclusion="success")
        self.assertEqual(report["verdict"], "MERGE_READY")
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["blocking_reasons"], [])

    def test_draft_pr_is_blocked(self):
        report, exit_code = self._run_evaluate(_fake_pr(draft=True), ci_conclusion="success")
        self.assertEqual(report["verdict"], "BLOCKED_BY_DRAFT")
        self.assertEqual(exit_code, 2)

    def test_ci_failure_blocks_merge(self):
        report, exit_code = self._run_evaluate(_fake_pr(), ci_conclusion="failure")
        self.assertEqual(report["verdict"], "BLOCKED_BY_CI")
        self.assertEqual(exit_code, 2)

    def test_dirty_mergeable_state_blocks(self):
        report, exit_code = self._run_evaluate(
            _fake_pr(mergeable_state="dirty"), ci_conclusion="success"
        )
        self.assertEqual(report["verdict"], "BLOCKED_BY_CONFLICT")
        self.assertEqual(exit_code, 2)

    def test_pending_ci_blocks_merge(self):
        report, exit_code = self._run_evaluate(_fake_pr(), ci_conclusion="pending")
        self.assertEqual(report["verdict"], "BLOCKED_BY_CI")
        self.assertEqual(exit_code, 2)

    def test_outstanding_review_request_blocks_merge(self):
        report, exit_code = self._run_evaluate(
            _fake_pr(reviewers=[{"login": "octocat"}]), ci_conclusion="success"
        )
        self.assertEqual(report["verdict"], "BLOCKED_BY_REVIEW")
        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
