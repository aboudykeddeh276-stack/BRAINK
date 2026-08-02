from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_agent_registry as registry


class AgentRegistryTests(unittest.TestCase):
    def test_contains_required_fields_and_abstractions(self) -> None:
        data = registry.load_registry(ROOT)
        self.assertEqual(data["registry_id"], "keddeh_agent_registry")
        self.assertIn("identity_registry", data["real_world_abstractions"])
        self.assertIn("service_discovery", data["real_world_abstractions"])
        self.assertIn("observability_instrumentation", data["real_world_abstractions"])
        self.assertIn("finite_state_machine", data["real_world_abstractions"])
        self.assertGreaterEqual(len(data["required_agent_fields"]), 10)

    def test_only_acceptance_harness_has_promotion_authority(self) -> None:
        rows = registry.evaluate_registry(ROOT)
        promotable = [row.agent_id for row in rows if row.promotion_authority]
        self.assertEqual(promotable, ["acceptance_harness_agent"])
        self.assertTrue(all(row.valid for row in rows))

    def test_virtual_gpu_and_telemetry_do_not_promote_correctness(self) -> None:
        data = registry.load_registry(ROOT)
        rules = data["promotion_rules"]
        self.assertTrue(rules["telemetry_may_observe_not_promote"])
        self.assertTrue(rules["virtual_gpu_may_render_not_promote"])
        gpu = next(
            agent
            for agent in data["agent_types"]
            if agent["agent_id"] == "virtual_gpu_projection_agent"
        )
        self.assertFalse(gpu["promotion_authority"])
        self.assertIn("substitute_ui_for_test_evidence", gpu["denied_actions"])

    def test_execution_writes_receipt_readback_and_handoff(self) -> None:
        final = registry.run_agent_registry(ROOT, emit_receipt=True)
        self.assertEqual(final["status"], "LOCAL_PASS")
        self.assertTrue(final["ledger_readback"])
        self.assertFalse(final["hash_used_as_functional_proof"])
        self.assertFalse(final["telemetry_promotes_correctness"])
        self.assertFalse(final["virtual_gpu_promotes_correctness"])
        outbox = Path(final["outbox_manifest"])
        self.assertTrue(outbox.exists())
        evidence = ROOT / "evidence" / "agent_registry_receipt.json"
        self.assertTrue(evidence.exists())
        payload = json.loads(evidence.read_text(encoding="utf-8"))
        self.assertEqual(payload["registry_id"], "keddeh_agent_registry")


if __name__ == "__main__":
    unittest.main()
