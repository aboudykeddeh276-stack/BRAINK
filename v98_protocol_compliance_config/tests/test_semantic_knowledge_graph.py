from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_semantic_knowledge_graph as graph


class SemanticKnowledgeGraphTests(unittest.TestCase):
    def test_policy_declares_executable_encyclopedia_model(self) -> None:
        policy = graph.load_policy(ROOT)
        self.assertEqual(policy["canonical_statement"], "The codebase is an executable encyclopedia of contextual state transitions.")
        self.assertIn("source_word", policy["core_pipeline"])
        self.assertIn("updated_story_state", policy["core_pipeline"])

    def test_every_word_has_addressable_definition_and_backlinks(self) -> None:
        policy = graph.load_policy(ROOT)
        words = graph.build_word_pages(policy)
        ids = {word.canonical_id for word in words}
        self.assertIn("word://run", ids)
        self.assertIn("word://health", ids)
        for word in words:
            self.assertTrue(word.canonical_id.startswith("word://"))
            self.assertTrue(word.source_definitions)
            self.assertTrue(word.invariants)
            self.assertTrue(word.prohibited_conflations)

    def test_expression_composition_preserves_source_words(self) -> None:
        policy = graph.load_policy(ROOT)
        expressions = graph.build_expression_pages(policy)
        for expression in expressions:
            source_words = {word["canonical"] for word in expression.words}
            self.assertTrue(source_words)
            self.assertTrue(set(expression.source_meaning.values()).issubset(source_words))
            self.assertTrue(expression.composed_definition)
            self.assertTrue(expression.not_allowed)

    def test_services_are_semantically_bound_to_expressions(self) -> None:
        result = graph.run_semantic_knowledge_graph(ROOT, emit_receipt=True)
        bindings = result["bindings"]
        self.assertGreater(len(bindings), 10)
        self.assertTrue(any(row["semantic_expression"] == "expression://observe-node-health" for row in bindings))
        self.assertTrue(any(row["semantic_expression"] == "expression://instantiate-governed-agent-worker" for row in bindings))

    def test_receipt_matrices_ledger_and_outbox_are_written(self) -> None:
        result = graph.run_semantic_knowledge_graph(ROOT, emit_receipt=True)
        receipt = result["receipt"]
        self.assertTrue(receipt["ledger_readback"])
        self.assertTrue(Path(receipt["receipt_path"]).exists())
        self.assertTrue(Path(receipt["edge_matrix_path"]).exists())
        self.assertTrue(Path(receipt["binding_matrix_path"]).exists())
        self.assertTrue(Path(receipt["outbox_manifest"]).exists())
        payload = json.loads(Path(receipt["receipt_path"]).read_text(encoding="utf-8"))
        self.assertTrue(payload["execution_explainability_enabled"])
        self.assertTrue(payload["isolated_file_model_rejected"])

    def test_semantic_conformance_detects_missing_meaning_without_terminal_stop(self) -> None:
        result = graph.run_semantic_knowledge_graph(ROOT, emit_receipt=True)
        self.assertIn("issues", result)
        self.assertFalse(result["single_file_claim"])
        for issue in result["issues"]:
            self.assertIn("corrective_action", issue)


if __name__ == "__main__":
    unittest.main()
