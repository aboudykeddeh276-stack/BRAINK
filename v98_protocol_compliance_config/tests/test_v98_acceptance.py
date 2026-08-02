from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_v98_acceptance_harness as harness


class V98AcceptanceTests(unittest.TestCase):
    def test_authority_map_blocks_human_and_agent_promotion(self) -> None:
        checks = harness.validate_authority_map(ROOT)
        self.assertTrue(checks["human_cannot_promote"])
        self.assertTrue(checks["agent_cannot_promote"])
        self.assertTrue(checks["acceptance_harness_can_promote"])

    def test_services_are_classified_by_executable_probes(self) -> None:
        receipts = harness.evaluate_services(ROOT)
        self.assertGreaterEqual(len(receipts), 14)
        by_id = {receipt.service_id: receipt for receipt in receipts}

        self.assertEqual(by_id["agent_static_guard"].promotion_state, harness.LOCAL_PASS)
        self.assertEqual(by_id["secret_boundary_guard"].promotion_state, harness.LOCAL_PASS)
        self.assertEqual(by_id["safe_asset_receipt_pipeline"].promotion_state, harness.LOCAL_PASS)
        self.assertEqual(by_id["vfs_volume_custody"].promotion_state, harness.LOCAL_PASS)
        self.assertEqual(by_id["mirror_update_lane"].promotion_state, harness.LOCAL_PASS)
        self.assertEqual(by_id["agent_registry_service"].promotion_state, harness.LOCAL_PASS)
        self.assertEqual(by_id["agent_runtime_service"].promotion_state, harness.LOCAL_PASS)

        self.assertEqual(
            by_id["zero_heap_compiler"].promotion_state,
            harness.UNSUPPORTED_IN_THIS_RUNTIME,
        )
        self.assertEqual(
            by_id["hyper_explicit_mesh_runtime"].promotion_state,
            harness.UNSUPPORTED_IN_THIS_RUNTIME,
        )
        self.assertEqual(
            by_id["virtual_gpu_hci_dashboard"].promotion_state,
            harness.TARGET_HOST_REQUIRED,
        )
        self.assertEqual(
            by_id["peer_ack_verifier"].promotion_state,
            harness.PROVIDER_REQUIRED,
        )

        for receipt in receipts:
            self.assertEqual(set(receipt.stages), set(harness.SERVICE_STAGES))
            self.assertTrue(receipt.stages["recognize"])
            self.assertTrue(receipt.stages["write_receipt"])
            self.assertTrue(receipt.stages["readback"])
            self.assertTrue(receipt.stages["handoff"])
            if receipt.promotion_state == harness.LOCAL_PASS:
                self.assertTrue(receipt.stages["execute"])
                self.assertTrue(receipt.stages["verify"])

    def test_manifest_flags_do_not_promote_unimplemented_services(self) -> None:
        protocols = harness.load_service_protocols(ROOT)
        declared = {service["service_id"]: service for service in protocols}
        self.assertTrue(all(declared["hyper_explicit_mesh_runtime"]["stages"].values()))
        receipts = {receipt.service_id: receipt for receipt in harness.evaluate_services(ROOT)}
        self.assertNotEqual(
            receipts["hyper_explicit_mesh_runtime"].promotion_state,
            harness.LOCAL_PASS,
        )
        self.assertFalse(receipts["hyper_explicit_mesh_runtime"].executed)

    def test_standards_catalog_contains_required_packs_and_no_certification_claim(self) -> None:
        catalog = harness.validate_standards_catalog(ROOT)
        self.assertEqual(catalog["required_missing"], [])
        self.assertTrue(catalog["reference_alignment_only"])
        self.assertGreaterEqual(catalog["standards_count"], 10)

    def test_local_pass_target_gates_reference_executable_evidence(self) -> None:
        services = harness.evaluate_services(ROOT)
        gates = {gate.gate_id: gate for gate in harness.evaluate_target_gates(ROOT, services)}
        for gate_id in ("TG-03", "TG-08"):
            gate = gates[gate_id]
            self.assertEqual(gate.promotion_state, harness.LOCAL_PASS)
            self.assertTrue(gate.executed)
            self.assertTrue(gate.evidence_path)
            self.assertTrue(Path(gate.evidence_path).exists())

    def test_local_target_gates_fail_closed_without_execution_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "config"
            config.mkdir(parents=True)
            (config / "deployment_profile_macos_m3.json").write_text(
                json.dumps(
                    {
                        "target_gates": [
                            {
                                "gate_id": "TG-03",
                                "gate_type": "local_ledger_write_readback",
                                "promotion_state": "LOCAL_PASS",
                                "receipt_required": "ledger readback",
                            },
                            {
                                "gate_id": "TG-08",
                                "gate_type": "virtual_cpu",
                                "promotion_state": "LOCAL_PASS",
                                "receipt_required": "service receipt",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            gates = harness.evaluate_target_gates(root, [])
            self.assertTrue(all(gate.promotion_state == harness.LOCAL_FAIL for gate in gates))
            self.assertTrue(all(not gate.executed for gate in gates))
            self.assertTrue(all(not gate.evidence_path for gate in gates))

    def test_acceptance_emits_probe_receipts_ledger_and_outbox(self) -> None:
        final = harness.run_acceptance(ROOT, emit_receipt=True)
        self.assertEqual(
            final["status"],
            "PASS_WITH_EXECUTABLE_SERVICE_PROBES_AND_TARGET_HOST_DEPLOYMENT_GATES",
        )
        self.assertTrue(final["authority_checks_passed"])
        self.assertTrue(final["ledger_readback"])
        self.assertEqual(final["service_probe_failures"], [])
        self.assertGreater(final["service_classification_counts"][harness.LOCAL_PASS], 0)
        self.assertGreater(
            final["service_classification_counts"][harness.UNSUPPORTED_IN_THIS_RUNTIME],
            0,
        )
        local_gates = [
            gate
            for gate in final["target_gate_receipts"]
            if gate["promotion_state"] == harness.LOCAL_PASS
        ]
        self.assertGreater(len(local_gates), 0)
        self.assertTrue(all(gate["executed"] for gate in local_gates))
        self.assertTrue(all(gate["evidence_path"] for gate in local_gates))
        self.assertFalse(final["hash_used_as_functional_proof"])
        self.assertFalse(final["manifest_used_as_functional_proof"])
        self.assertFalse(final["telemetry_used_as_functional_proof"])
        self.assertFalse(final["certification_claimed"])
        outbox = Path(final["outbox_manifest"])
        self.assertTrue(outbox.exists())
        verification = ROOT / "evidence" / "FINAL_VERIFICATION.json"
        self.assertTrue(verification.exists())
        data = json.loads(verification.read_text(encoding="utf-8"))
        self.assertEqual(data["services_connected"], final["services_connected"])


if __name__ == "__main__":
    unittest.main()
