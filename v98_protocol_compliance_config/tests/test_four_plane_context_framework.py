from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_four_plane_context_framework as framework


class FourPlaneContextFrameworkTests(unittest.TestCase):
    def test_policy_declares_four_non_collapsible_planes(self) -> None:
        policy = framework.load_policy(ROOT)
        planes = {node["plane"] for node in policy["framework_nodes"]}
        self.assertEqual(planes, {"output_framework", "thinking_framework", "legal_perspective", "software_service"})
        self.assertEqual(policy["formula"], "S=f(I,V,O,E,X,R,L)")

    def test_each_plane_preserves_own_context_fields(self) -> None:
        policy = framework.load_policy(ROOT)
        rows = [framework.assess_plane(node, policy["required_context_fields"]) for node in policy["framework_nodes"]]
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertTrue(row.context_complete, row)
            self.assertTrue(row.evidence_contract_complete, row)
            self.assertTrue(row.non_collapsible, row)
            self.assertEqual(row.derived_state, "FRAMEWORK_NODE_BOUND")

    def test_cross_plane_inheritance_is_blocked(self) -> None:
        result = framework.run_four_plane_context_framework(ROOT, emit_receipt=True)
        self.assertFalse(result["legal_conclusion_inherited_from_software_test"])
        self.assertFalse(result["polished_output_used_as_reasoning_proof"])
        self.assertFalse(result["internal_reasoning_state_promoted_to_court_fact"])
        self.assertFalse(result["software_receipt_promoted_to_legal_determination"])
        self.assertGreaterEqual(result["receipt"]["cross_plane_guard_count"], 4)

    def test_receipt_matrix_outbox_and_ledger_are_written(self) -> None:
        result = framework.run_four_plane_context_framework(ROOT, emit_receipt=True)
        receipt = result["receipt"]
        self.assertTrue(receipt["ledger_readback"])
        self.assertEqual(receipt["valid_plane_count"], 4)
        self.assertEqual(receipt["conformance_issue_count"], 0)
        self.assertTrue(Path(receipt["receipt_path"]).exists())
        self.assertTrue(Path(receipt["matrix_path"]).exists())
        self.assertTrue(Path(receipt["outbox_manifest"]).exists())
        payload = json.loads(Path(receipt["receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(payload["formula"], "S=f(I,V,O,E,X,R,L)")


if __name__ == "__main__":
    unittest.main()
