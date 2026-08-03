from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_application_applet_packager as applet_packager
import keddeh_deployment_maturity_workplan as workplan


class DeploymentMaturityWorkplanTests(unittest.TestCase):
    def setUp(self) -> None:
        # The maturity workplan requires K-APP package evidence; generate it locally first.
        applet_packager.run_application_applet_shipping(ROOT, emit_receipt=True)

    def test_workplan_assesses_all_services_plus_global_workloads(self) -> None:
        result = workplan.run_deployment_maturity_workplan(ROOT, emit_receipt=True)
        service_count = len(workplan.load_services(ROOT))
        self.assertGreaterEqual(result["receipt"]["assessed_components"], service_count + 2)
        self.assertGreater(result["receipt"]["workplan_packets_written"], 0)

    def test_workplan_identifies_target_host_and_provider_pending_work(self) -> None:
        result = workplan.run_deployment_maturity_workplan(ROOT, emit_receipt=True)
        issue_codes = {row["issue_code"] for row in result["rows"]}
        self.assertIn("TARGET_HOST_GATE_PENDING", issue_codes)
        self.assertIn("PROVIDER_GATE_PENDING", issue_codes)
        self.assertGreaterEqual(result["receipt"]["target_host_required"], 1)

    def test_workplan_is_actionable_and_not_telemetry_or_simulation_proof(self) -> None:
        result = workplan.run_deployment_maturity_workplan(ROOT, emit_receipt=True)
        self.assertFalse(result["simulation_used_as_deployment_proof"])
        self.assertFalse(result["telemetry_used_as_deployment_proof"])
        self.assertFalse(result["global_failure_from_dependency_failure"])
        for row in result["rows"]:
            self.assertTrue(row["action_command"])
            self.assertTrue(row["corrective_workflow"])
            self.assertTrue(row["required_receipts"])

    def test_receipt_matrix_work_packets_and_outbox_are_written(self) -> None:
        result = workplan.run_deployment_maturity_workplan(ROOT, emit_receipt=True)
        receipt = result["receipt"]
        self.assertTrue(Path(receipt["receipt_path"]).exists())
        self.assertTrue(Path(receipt["matrix_path"]).exists())
        self.assertTrue(Path(receipt["outbox_manifest"]).exists())
        for packet in result["workplan_packets"]:
            self.assertTrue(Path(packet).exists())
            payload = json.loads(Path(packet).read_text(encoding="utf-8"))
            self.assertIn("component_id", payload)
            self.assertIn("action_command", payload)
            self.assertIn("reentry_condition", payload)

    def test_local_packages_do_not_remove_target_host_boundaries(self) -> None:
        result = workplan.run_deployment_maturity_workplan(ROOT, emit_receipt=True)
        m3_rows = [row for row in result["rows"] if row["component_id"] == "m3_target_host_deployment"]
        self.assertEqual(len(m3_rows), 1)
        self.assertEqual(m3_rows[0]["maturity_state"], "TARGET_HOST_REQUIRED")
        self.assertEqual(m3_rows[0]["dependency_class"], "EXTERNAL_GATE")


if __name__ == "__main__":
    unittest.main()
