from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard" / "index.html"


class DashboardProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = DASHBOARD.read_text(encoding="utf-8")

    def test_dashboard_is_executable_html_not_a_static_image(self) -> None:
        self.assertIn("<script>", self.html)
        self.assertIn('id="registryFile"', self.html)
        self.assertIn('id="monitorFile"', self.html)
        self.assertIn('id="completionFile"', self.html)
        self.assertIn("addEventListener", self.html)
        self.assertIn("Download JSON projection", self.html)
        self.assertIn("Download task-lane CSV", self.html)

    def test_dashboard_preserves_all_evidence_classifications(self) -> None:
        for state in [
            "LOCAL_PASS",
            "LOCAL_FAIL",
            "TARGET_HOST_REQUIRED",
            "PROVIDER_REQUIRED",
            "EXTERNAL_CERTIFICATION_REQUIRED",
            "UNSUPPORTED_IN_THIS_RUNTIME",
        ]:
            self.assertIn(state, self.html)

    def test_dashboard_does_not_preclaim_runtime_screenshot_proof(self) -> None:
        self.assertNotIn("REAL_RUNTIME_SCREENSHOT", self.html)
        self.assertNotIn("CAPTURED_FROM_EXECUTED_HTML", self.html)
        self.assertIn("This HTML never promotes a task by itself", self.html)
        self.assertIn("No generated concept image is treated as a screenshot", self.html)

    def test_dashboard_enforces_five_task_registry_cadence(self) -> None:
        self.assertIn("Array.from({length:20},(_,i)=>(i+1)*5)", self.html)
        self.assertIn("registry milestones must be exactly 5..100 by five", self.html)


if __name__ == "__main__":
    unittest.main()
