from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_service_probes as probes


class ServiceProbeTests(unittest.TestCase):
    def test_every_declared_service_has_probe_or_explicit_unsupported_receipt(self) -> None:
        services = probes.read_json(ROOT / "config" / "service_protocols.json")["services"]
        receipts = probes.run_all_service_probes(ROOT, services)
        self.assertEqual(len(receipts), len(services))
        self.assertEqual({receipt.service_id for receipt in receipts}, {service["service_id"] for service in services})
        for receipt in receipts:
            self.assertIn(receipt.classification, probes.ALLOWED_STATES)
            self.assertTrue(receipt.receipt_written)
            self.assertTrue(receipt.readback_passed)
            self.assertTrue(receipt.handoff_written)
            self.assertTrue(Path(receipt.evidence_path).exists())
            self.assertTrue(Path(receipt.outbox_manifest).exists())

    def test_local_pass_requires_positive_and_negative_execution(self) -> None:
        services = probes.read_json(ROOT / "config" / "service_protocols.json")["services"]
        receipts = probes.run_all_service_probes(ROOT, services)
        local = [receipt for receipt in receipts if receipt.classification == probes.LOCAL_PASS]
        self.assertGreater(len(local), 0)
        for receipt in local:
            self.assertTrue(receipt.executed, receipt.service_id)
            self.assertTrue(receipt.positive_test_passed, receipt.service_id)
            self.assertTrue(receipt.negative_test_passed, receipt.service_id)
            self.assertNotEqual(receipt.probe_name, "unregistered_probe")

    def test_gated_services_are_not_reported_as_executed(self) -> None:
        services = probes.read_json(ROOT / "config" / "service_protocols.json")["services"]
        receipts = {receipt.service_id: receipt for receipt in probes.run_all_service_probes(ROOT, services)}
        for service_id in [
            "zero_heap_compiler",
            "peer_ack_verifier",
            "hyper_explicit_mesh_runtime",
            "hemos_family_of_five_runtime",
            "indefinite_network_runtime",
            "virtual_gpu_hci_dashboard",
        ]:
            self.assertFalse(receipts[service_id].executed, service_id)
            self.assertNotEqual(receipts[service_id].classification, probes.LOCAL_PASS)

    def test_static_and_secret_guards_execute_real_negative_vectors(self) -> None:
        static = probes.probe_agent_static_guard(ROOT)
        secrets = probes.probe_secret_boundary_guard(ROOT)
        self.assertEqual(static.classification, probes.LOCAL_PASS)
        self.assertTrue(static.negative_test_passed)
        self.assertEqual(secrets.classification, probes.LOCAL_PASS)
        self.assertTrue(secrets.negative_test_passed)


if __name__ == "__main__":
    unittest.main()
