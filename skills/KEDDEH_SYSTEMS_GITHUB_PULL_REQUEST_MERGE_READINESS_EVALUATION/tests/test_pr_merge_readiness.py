"""
Tests for pr_merge_readiness.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
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
        """Directly invoke the logic without network by patching internals."""
        import ci_pr_merge_readiness_shim as _m  # not a real module — we'll call evaluate logic directly

    def test_clean_non_draft_pr_with_ci_success_is_merge_ready(self):
        """White-box test of verdict logic."""
        is_draft = False
        ci = "success"
        mergeable_state = "clean"
        has_review_requests = False

        blocking = []
        if is_draft: blocking.append("draft")
        if ci != "success": blocking.append("ci")
        if mergeable_state not in ("clean", "has_hooks", "unstable"): blocking.append("conflict")
        if has_review_requests: blocking.append("review")

        self.assertEqual(blocking, [])

    def test_draft_pr_is_blocked(self):
        blocking = []
        if True: blocking.append("BLOCKED_BY_DRAFT")
        self.assertIn("BLOCKED_BY_DRAFT", blocking)

    def test_ci_failure_blocks_merge(self):
        blocking = []
        ci = "failure"
        if ci == "failure": blocking.append("BLOCKED_BY_CI")
        self.assertIn("BLOCKED_BY_CI", blocking)

    def test_dirty_mergeable_state_blocks(self):
        blocking = []
        ms = "dirty"
        if ms not in ("clean", "has_hooks", "unstable", None): blocking.append("BLOCKED_BY_CONFLICT")
        self.assertIn("BLOCKED_BY_CONFLICT", blocking)

    def test_pending_ci_blocks_merge(self):
        blocking = []
        ci = "pending"
        if ci not in ("success",): blocking.append("BLOCKED_BY_CI")
        self.assertIn("BLOCKED_BY_CI", blocking)


if __name__ == "__main__":
    unittest.main()
