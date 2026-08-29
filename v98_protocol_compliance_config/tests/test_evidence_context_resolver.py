from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_evidence_context_resolver as resolver


class EvidenceContextResolverTests(unittest.TestCase):
    def test_policy_formula_terms_and_invariants_are_present(self) -> None:
        policy = resolver.load_policy(ROOT)
        self.assertEqual(policy["formula"], "S=f(I,V,O,E,X,R,L)")
        self.assertEqual(set(policy["terms"].keys()), {"I", "V", "O", "E", "X", "R", "L"})
        for invariant in ["identity", "observer", "environment", "execution_plane", "lineage", "impact_radius"]:
            self.assertIn(invariant, policy["invariants"])

    def test_single_signal_findings_do_not_become_terminal_judgements(self) -> None:
        result = resolver.run_evidence_context_resolution(ROOT, emit_receipt=True)
        forbidden = {"FAKE", "IMPOSSIBLE", "FAILED", "GLOBAL_STOP"}
        for row in result["resolutions"]:
            self.assertNotIn(row["derived_state"], forbidden, row)
        self.assertFalse(result["single_signal_used_as_terminal_judgement"])
        self.assertFalse(result["global_stop_from_single_signal"])

    def test_valid_contextual_states_are_derived(self) -> None:
        result = resolver.run_evidence_context_resolution(ROOT, emit_receipt=True)
        states = {row["derived_state"] for row in result["resolutions"]}
        self.assertIn("CONTEXT_RESOLUTION_REQUIRED", states)
        self.assertIn("EVIDENCE_CORRELATION_REQUIRED", states)
        self.assertIn("DECLARED_TARGET", states)
        self.assertIn("PROJECTION_ACTIVE", states)
        self.assertIn("DECLARED_VARIANT", states)

    def test_bounded_stop_requires_proven_invariant_violation(self) -> None:
        item = {
            "finding": "manifest mismatch",
            "character_capability": "integrity_readback",
            "purpose": "detect package tamper",
            "observer": "unit_test",
            "environment": "local",
            "execution_plane": "local_execution",
            "evidence_class": "receipt",
            "freshness": "current",
            "lineage": "test",
            "proven_invariant_violation": True,
        }
        resolution = resolver.resolve_item(item)
        self.assertEqual(resolution.derived_state, "BOUNDED_STOP")
        self.assertTrue(resolution.bounded_stop)
        self.assertFalse(resolution.global_safety_stop)

    def test_global_safety_stop_requires_global_violation(self) -> None:
        item = {
            "finding": "semantic unsafe continuation",
            "character_capability": "global_integrity_guard",
            "purpose": "prevent unsafe continuation",
            "observer": "unit_test",
            "environment": "local",
            "execution_plane": "local_execution",
            "evidence_class": "receipt",
            "freshness": "current",
            "lineage": "test",
            "proven_global_integrity_violation": True,
        }
        resolution = resolver.resolve_item(item)
        self.assertEqual(resolution.derived_state, "GLOBAL_SAFETY_STOP")
        self.assertFalse(resolution.bounded_stop)
        self.assertTrue(resolution.global_safety_stop)

    def test_receipt_matrix_outbox_and_work_packets_are_written(self) -> None:
        result = resolver.run_evidence_context_resolution(ROOT, emit_receipt=True)
        receipt = result["receipt"]
        self.assertTrue(receipt["ledger_readback"])
        self.assertEqual(receipt["forbidden_direct_terminal_judgement_count"], 0)
        self.assertTrue(Path(receipt["receipt_path"]).exists())
        self.assertTrue(Path(receipt["matrix_path"]).exists())
        self.assertTrue(Path(receipt["outbox_manifest"]).exists())
        self.assertGreaterEqual(len(result["work_packets"]), 1)
        payload = json.loads(Path(receipt["receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(payload["formula"], "S=f(I,V,O,E,X,R,L)")


if __name__ == "__main__":
    unittest.main()
