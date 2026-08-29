from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from keddeh_agent_runtime_service import AgentRuntimeService


class AgentRuntimeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = AgentRuntimeService(ROOT)

    def test_acceptance_harness_can_write_receipt_and_readback(self) -> None:
        receipt = self.service.execute_work_order(
            "acceptance_harness_agent",
            "write_receipt",
            "agent_registry_service",
            {"test": "acceptance"},
        )
        self.assertTrue(receipt.authorized)
        self.assertTrue(receipt.executed)
        self.assertTrue(Path(receipt.receipt_path).exists())
        self.assertTrue(Path(receipt.outbox_manifest).exists())

    def test_codex_cannot_self_promote_local_pass(self) -> None:
        receipt = self.service.execute_work_order(
            "codex_implementation_agent",
            "promote_local_pass",
            "agent_static_guard",
            {"attempt": "self_promote"},
        )
        self.assertFalse(receipt.authorized)
        self.assertFalse(receipt.executed)
        self.assertIn(
            receipt.reason,
            {
                "action_explicitly_denied",
                "action_not_allowed",
                "promotion_reserved_for_acceptance_harness",
            },
        )

    def test_virtual_gpu_cannot_render_as_proof(self) -> None:
        receipt = self.service.execute_work_order(
            "virtual_gpu_projection_agent",
            "promote_local_pass",
            "virtual_gpu_hci_dashboard",
            {"attempt": "render_as_proof"},
        )
        self.assertFalse(receipt.authorized)
        self.assertFalse(receipt.executed)

    def test_virtual_cpu_can_execute_bound_service_contract(self) -> None:
        receipt = self.service.execute_work_order(
            "virtual_cpu_executor",
            "execute_service_contract",
            "hyper_explicit_mesh_runtime",
            {"path": "unit"},
        )
        self.assertTrue(receipt.authorized)
        self.assertTrue(receipt.executed)
        self.assertTrue(receipt.result["service_known"])

    def test_unknown_agent_fails_closed(self) -> None:
        receipt = self.service.execute_work_order(
            "unknown_agent",
            "write_receipt",
            "agent_registry_service",
            {},
        )
        self.assertFalse(receipt.authorized)
        self.assertFalse(receipt.executed)
        self.assertIn("unknown agent_id", receipt.reason)


if __name__ == "__main__":
    unittest.main()
