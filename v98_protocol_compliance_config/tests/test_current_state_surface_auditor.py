from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_current_state_surface_auditor as auditor


class CurrentStateSurfaceAuditorTests(unittest.TestCase):
    def test_uploaded_action_history_is_not_treated_as_proof(self) -> None:
        result = auditor.run_current_state_surface_audit(ROOT, emit_receipt=True)
        self.assertFalse(result["source_history_treated_as_proof"])
        self.assertFalse(result["simulation_or_fake_telemetry_promoted"])

    def test_google_tpu_rack_and_telemetry_claims_are_rejected_without_receipts(self) -> None:
        result = auditor.run_current_state_surface_audit(ROOT, emit_receipt=True)
        rows = {row["surface_id"]: row for row in result["rows"]}
        self.assertEqual(rows["google_tpu_server_rack"]["evidence_state"], "CLAIM_OR_SIMULATION_REJECTED_AS_PROOF")
        self.assertEqual(rows["simulated_agent_telemetry"]["evidence_state"], "CLAIM_OR_SIMULATION_REJECTED_AS_PROOF")
        self.assertIn("local CPU fallback", rows["google_tpu_server_rack"]["next_action"])

    def test_provision_agent_requires_worker_context_and_receipts(self) -> None:
        result = auditor.run_current_state_surface_audit(ROOT, emit_receipt=True)
        rows = {row["surface_id"]: row for row in result["rows"]}
        provision = rows["provision_agent"]
        self.assertEqual(provision["evidence_state"], "WORKER_CONTEXT_AND_RECEIPT_REQUIRED")
        self.assertIn("VFS namespace", provision["next_action"])
        self.assertIn("agent runtime work-order receipt", provision["required_receipts"])

    def test_linux_microvm_requires_boot_asset_readback(self) -> None:
        result = auditor.run_current_state_surface_audit(ROOT, emit_receipt=True)
        rows = {row["surface_id"]: row for row in result["rows"]}
        microvm = rows["linux_microvm_v86"]
        self.assertEqual(microvm["evidence_state"], "BOOT_ASSET_AND_SERIAL_READBACK_REQUIRED")
        self.assertIn("serial output receipt", microvm["required_receipts"])

    def test_receipt_matrix_outbox_and_work_packets_are_written(self) -> None:
        result = auditor.run_current_state_surface_audit(ROOT, emit_receipt=True)
        receipt = result["receipt"]
        self.assertTrue(receipt["ledger_readback"])
        self.assertTrue(Path(receipt["receipt_path"]).exists())
        self.assertTrue(Path(receipt["matrix_path"]).exists())
        self.assertTrue(Path(receipt["outbox_manifest"]).exists())
        for packet in result["work_packets"]:
            self.assertTrue(Path(packet).exists())


if __name__ == "__main__":
    unittest.main()
