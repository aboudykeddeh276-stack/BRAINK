import json
import unittest
from observer2_runtime.kex_symbolic_bridge import (
    BinaryBoundaryAdapter,
    ILLLMSemanticDictionary,
    SemanticEntry,
    bind_symbol,
    from_linguistic_projection,
    project_html,
)


def dictionary():
    return ILLLMSemanticDictionary((
        SemanticEntry("illlm:op:activate", "activate", "operation", "verb", "promote an armed mechanism into activation"),
        SemanticEntry("illlm:noun:router", "router", "runtime-object", "noun", "a routing runtime object"),
    ))


class KEXSymbolicBridgeTests(unittest.TestCase):
    def test_dictionary_redefinition_fails_closed(self):
        d = dictionary()
        with self.assertRaisesRegex(ValueError, "ILLLM_SYMBOL_REDEFINITION_REJECTED"):
            d.register(SemanticEntry("illlm:op:activate", "start", "operation", "verb", "different meaning"))

    def test_symbolic_envelope_is_deterministic(self):
        d = dictionary()
        a = bind_symbol(d, concept_id="concept:cpu.activate", symbol_id="illlm:op:activate", attributes={"target":"runtime://cpu/core"})
        b = bind_symbol(d, concept_id="concept:cpu.activate", symbol_id="illlm:op:activate", attributes={"target":"runtime://cpu/core"})
        self.assertEqual(a.semantic_root, b.semantic_root)
        self.assertEqual(a.envelope_root, b.envelope_root)
        self.assertEqual(a.ab_tokens, b.ab_tokens)

    def test_html_projection_stays_symbolic(self):
        e = bind_symbol(dictionary(), concept_id="concept:cpu.activate", symbol_id="illlm:op:activate")
        html = project_html(e)
        self.assertIn('data-kex-ab="', html)
        self.assertIn('data-illlm-symbol-id="illlm:op:activate"', html)
        self.assertIn('>activate</span>', html)
        self.assertNotIn("KAB1", html)

    def test_binary_boundary_roundtrip_restores_semantics(self):
        e = bind_symbol(dictionary(), concept_id="concept:router", symbol_id="illlm:noun:router", attributes={"route":"mesh0"})
        wire = BinaryBoundaryAdapter.emit(e)
        self.assertTrue(wire.startswith(b"KAB1"))
        payload, tokens = BinaryBoundaryAdapter.restore_symbolic_payload(wire)
        self.assertEqual(payload["semantic_root"], e.semantic_root)
        self.assertEqual(payload["dictionary_root"], e.dictionary_root)
        self.assertEqual(tokens, e.ab_tokens)

    def test_binary_tamper_fails_root_check(self):
        e = bind_symbol(dictionary(), concept_id="concept:router", symbol_id="illlm:noun:router")
        wire = bytearray(BinaryBoundaryAdapter.emit(e))
        wire[-1] ^= 0x01
        with self.assertRaises(ValueError):
            BinaryBoundaryAdapter.restore_symbolic_payload(bytes(wire))

    def test_linguistic_projection_binding_preserves_source_root(self):
        projection = {
            "anchor":{"atomic_number":8,"symbol":"O","name":"Oxygen"},
            "relation":{"property_id":"reactive","policy_version":"PROPERTY_POLICY_V1"},
            "projection":{"language":"en","text":"strong reactive Oxygen"},
            "truth_boundary":{"projection_mutates_source":False},
            "semantic_root":"abc123",
        }
        e = from_linguistic_projection(dictionary(), projection, concept_id="concept:oxygen.activate", symbol_id="illlm:op:activate")
        self.assertEqual(e.source_projection_root, "abc123")
        self.assertEqual(e.attributes["anchor"]["symbol"], "O")

    def test_linguistic_projection_source_mutation_is_rejected(self):
        projection = {"semantic_root":"abc", "truth_boundary":{"projection_mutates_source":True}}
        with self.assertRaisesRegex(ValueError, "ILLLM_SOURCE_MUTATION_BOUNDARY_INVALID"):
            from_linguistic_projection(dictionary(), projection, concept_id="c", symbol_id="illlm:op:activate")


if __name__ == "__main__": unittest.main()
