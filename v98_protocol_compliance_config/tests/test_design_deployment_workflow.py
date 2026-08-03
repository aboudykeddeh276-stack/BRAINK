from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_design_deployment_workflow as workflow


class DesignDeploymentWorkflowTests(unittest.TestCase):
    def test_phase_order_and_required_fields_are_valid(self) -> None:
        rows = workflow.validate_workflow(ROOT)
        self.assertEqual(len(rows), 11)
        self.assertTrue(all(row.valid for row in rows), [row.reason for row in rows])

    def test_forbidden_solo_proofs_are_blocked(self) -> None:
        config = workflow.load_config(ROOT)
        self.assertTrue(workflow.FORBIDDEN_SOLO_PROOF.issubset(set(config["not_completion_by_itself"])))

    def test_completion_rule_requires_executable_evidence(self) -> None:
        config = workflow.load_config(ROOT)
        for required in [
            "source_code_exists",
            "executable_command_exists",
            "tests_executed",
            "receipt_written",
            "ledger_readback_verified",
            "outbox_handoff_written",
        ]:
            self.assertIn(required, config["completion_rule"])

    def test_run_workflow_writes_receipt_matrix_and_outbox(self) -> None:
        result = workflow.run_design_deployment_workflow(ROOT, emit_receipt=True)
        receipt = result["receipt"]
        self.assertEqual(receipt["promotion_state"], "LOCAL_PASS")
        self.assertTrue(receipt["ledger_readback"])
        self.assertFalse(result["hash_used_as_functional_proof"])
        self.assertFalse(result["telemetry_used_as_functional_proof"])
        self.assertTrue((ROOT / "evidence" / "software_design_deployment_workflow_receipt.json").exists())
        self.assertTrue((ROOT / "exports" / "software_design_deployment_workflow_matrix.csv").exists())
        self.assertTrue(Path(receipt["outbox_manifest"]).exists())
        payload = json.loads((ROOT / "evidence" / "software_design_deployment_workflow_receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["receipt"]["workflow_id"], "software_design_deployment_workflow")


if __name__ == "__main__":
    unittest.main()
