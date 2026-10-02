import json
import tempfile
import unittest
from pathlib import Path

from topology.kex_topology_controller import TopologyController


REGISTRY = Path(__file__).resolve().parents[1] / "topology" / "kex_topology_registry.json"


class TestTopologyController(unittest.TestCase):
    def setUp(self):
        self.controller = TopologyController(REGISTRY)

    def test_registry_preserves_76_logical_objects(self):
        self.assertEqual(len(self.controller.objects), 76)
        self.assertEqual(
            self.controller.registry["source_basis"]["p11_unique_carriers"], 95
        )

    def test_application_and_volume_are_distinct_identities(self):
        self.controller.resolve_identity("app://casepath")
        self.controller.resolve_identity("volume://casepath/v19")
        self.assertNotEqual(
            self.controller.objects["app://casepath"]["surface_class"],
            self.controller.objects["volume://casepath/v19"]["surface_class"],
        )

    def test_same_carrier_cannot_change_logical_identity(self):
        self.controller.register_carrier(
            "app://casepath", "carrier://casepath/test", "HTML", "test.html"
        )
        with self.assertRaisesRegex(ValueError, "CARRIER_ID_REBOUND"):
            self.controller.register_carrier(
                "volume://casepath/v19",
                "carrier://casepath/test",
                "HTML",
                "other.html",
            )

    def test_development_can_exist_before_execution_evidence(self):
        self.controller.register_carrier(
            "app://casepath", "carrier://casepath/test", "HTML", "test.html"
        )
        self.assertEqual(self.controller.supported_level("app://casepath"), "DECLARED")

    def test_observed_execution_changes_claimable_level(self):
        ev = self.controller.record_evidence(
            "app://casepath",
            "process_execution",
            "EXECUTED",
            "local-test",
            details={"exit_code": 0},
        )
        claim = self.controller.make_claim(
            "app://casepath", "EXECUTED", [ev.evidence_id]
        )
        self.assertEqual(claim.status, "SUPPORTED")

    def test_unobserved_execution_cannot_be_claimed(self):
        with self.assertRaisesRegex(ValueError, "EXECUTION_EVIDENCE_MUST_BE_OBSERVED"):
            self.controller.record_evidence(
                "app://casepath",
                "process_execution",
                "EXECUTED",
                "declared-only",
                observed=False,
            )

    def test_readback_has_hash(self):
        out = self.controller.readback("app://claimpath")
        self.assertEqual(out["schema"], "keddeh.kex.topology.readback.v1")
        self.assertEqual(len(out["readback_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
