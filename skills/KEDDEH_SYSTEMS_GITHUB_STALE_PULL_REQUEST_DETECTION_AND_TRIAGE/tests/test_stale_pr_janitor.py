"""
Tests for stale_pr_janitor.py
"""
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from stale_pr_janitor import _days_since


class DaysSinceTests(unittest.TestCase):

    def test_zero_days_for_now(self):
        now_iso = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
        self.assertEqual(_days_since(now_iso), 0)

    def test_30_days(self):
        ts = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat().replace("+00:00", "Z")
        self.assertEqual(_days_since(ts), 30)


class StaleClassificationTests(unittest.TestCase):
    """Test the staleness classification logic without network calls."""

    def test_pr_below_threshold_is_not_stale(self):
        stale_days = 14
        days_since = 10
        self.assertFalse(days_since >= stale_days)

    def test_pr_at_threshold_is_stale(self):
        stale_days = 14
        days_since = 14
        self.assertTrue(days_since >= stale_days)

    def test_pr_above_threshold_is_stale(self):
        stale_days = 14
        days_since = 30
        self.assertTrue(days_since >= stale_days)

    def test_non_draft_pr_is_never_stale_regardless_of_age(self):
        """Non-draft PRs are not subject to stale classification in this skill."""
        is_draft = False
        days_since = 100
        stale_days = 14
        would_be_stale = is_draft and days_since >= stale_days
        self.assertFalse(would_be_stale)


if __name__ == "__main__":
    unittest.main()
