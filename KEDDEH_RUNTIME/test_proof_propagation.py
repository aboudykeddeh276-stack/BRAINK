import unittest

from theorem_graph import MasterTheoremGraphRegistry, GraphValidationError
from proof_propagation import (
    RuntimeProofPropagationEngine,
    ProofStateTransitionError,
)


class TestRuntimeProofPropagation(unittest.TestCase):
    def make_graph(self):
        registry = MasterTheoremGraphRegistry()
        registry.register("ROOT", {"tensor_min": 7.0}, parent_operators=["OP_ROOT"])
        registry.register("CHILD", {"tensor_min": 8.0}, parent_ids=["ROOT"])
        registry.register("GRANDCHILD", {"tensor_min": 9.0}, parent_ids=["CHILD"])
        registry.register("UNRELATED", {"tensor_min": 7.0}, parent_operators=["OP_OTHER"])
        return registry

    def test_unknown_theorem_fails_loudly(self):
        engine = RuntimeProofPropagationEngine(self.make_graph())
        with self.assertRaises(GraphValidationError):
            engine.state("DOES_NOT_EXIST")

    def test_proven_transition_requires_receipt_and_evidence(self):
        engine = RuntimeProofPropagationEngine(self.make_graph())
        with self.assertRaises(ProofStateTransitionError):
            engine.mark_proven("ROOT", receipt_id="", evidence_hash="abc")
        with self.assertRaises(ProofStateTransitionError):
            engine.mark_proven("ROOT", receipt_id="R-1", evidence_hash="")

    def test_proven_state_allows_continuation(self):
        engine = RuntimeProofPropagationEngine(self.make_graph())
        state = engine.mark_proven("ROOT", receipt_id="R-ROOT-1", evidence_hash="evidence-root")
        self.assertEqual(state.status, "PROVEN")
        self.assertTrue(engine.can_continue("ROOT"))

    def test_parent_falsification_cascades_to_descendants(self):
        engine = RuntimeProofPropagationEngine(self.make_graph())
        engine.mark_proven("ROOT", receipt_id="R-ROOT-1", evidence_hash="evidence-root")
        engine.mark_proven("CHILD", receipt_id="R-CHILD-1", evidence_hash="evidence-child")
        engine.mark_proven("GRANDCHILD", receipt_id="R-GRAND-1", evidence_hash="evidence-grand")

        receipt = engine.invalidate("ROOT", reason="counterexample", receipt_id="F-ROOT-1")

        self.assertEqual(engine.state("ROOT").status, "FALSIFIED")
        self.assertEqual(engine.state("CHILD").status, "DOWNSTREAM_REVIEW_REQUIRED")
        self.assertEqual(engine.state("GRANDCHILD").status, "DOWNSTREAM_REVIEW_REQUIRED")
        self.assertFalse(engine.can_continue("CHILD"))
        self.assertIn("CHILD", receipt["affected"])
        self.assertIn("GRANDCHILD", receipt["affected"])

    def test_existing_falsification_is_not_weakened_by_parent_invalidation(self):
        engine = RuntimeProofPropagationEngine(self.make_graph())
        engine.invalidate("CHILD", reason="direct falsifier", receipt_id="F-CHILD-1")
        engine.invalidate("ROOT", reason="upstream falsifier", receipt_id="F-ROOT-1")
        self.assertEqual(engine.state("CHILD").status, "FALSIFIED")

    def test_unrelated_theorem_is_unchanged(self):
        engine = RuntimeProofPropagationEngine(self.make_graph())
        engine.mark_proven("UNRELATED", receipt_id="R-U-1", evidence_hash="evidence-u")
        engine.invalidate("ROOT", reason="counterexample", receipt_id="F-ROOT-1")
        self.assertEqual(engine.state("UNRELATED").status, "PROVEN")

    def test_propagation_receipt_is_deterministic(self):
        e1 = RuntimeProofPropagationEngine(self.make_graph())
        e2 = RuntimeProofPropagationEngine(self.make_graph())
        r1 = e1.invalidate("ROOT", reason="counterexample", receipt_id="F-ROOT-1")
        r2 = e2.invalidate("ROOT", reason="counterexample", receipt_id="F-ROOT-1")
        self.assertEqual(r1["propagation_receipt"], r2["propagation_receipt"])


if __name__ == "__main__":
    unittest.main()
