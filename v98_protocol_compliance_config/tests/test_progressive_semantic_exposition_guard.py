from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_progressive_semantic_exposition_guard as guard


def grounded_example():
    return {
        "TECHNICAL_TERM": "runtime carrier",
        "PLAIN_ENGLISH_MEANING": "the thing that stores and starts executable code",
        "FAMILIAR_ANALOGY": "a workshop that contains a machine and gives it somewhere to run",
        "SIMPLER_PROCESS_OR_PHYSICAL_ANALOGY": "a box holds parts, a person opens the box, places the parts on a bench, and starts using them",
        "PRIMITIVE_OPERATION": "bytes are stored, read into memory, instructions are loaded, and execution begins",
        "SYSTEM_SPECIFIC_BINDING": "in BRAINK, the runtime carrier is the concrete HTML, Linux, volume, or host layer that stores the bytes and starts the intended executable path"
    }


class ProgressiveSemanticExpositionGuardTests(unittest.TestCase):
    def test_full_progression_is_accepted(self):
        result = guard.evaluate(ROOT, grounded_example())
        self.assertTrue(result.valid)
        self.assertEqual(result.state, "CONTEXTUALLY_GROUNDED")

    def test_missing_primitive_is_rejected(self):
        item = grounded_example()
        item["PRIMITIVE_OPERATION"] = ""
        result = guard.evaluate(ROOT, item)
        self.assertFalse(result.valid)
        self.assertIn("PRIMITIVE_OPERATION", result.missing_stages)

    def test_jargon_repetition_is_rejected(self):
        item = grounded_example()
        item["PLAIN_ENGLISH_MEANING"] = item["TECHNICAL_TERM"]
        result = guard.evaluate(ROOT, item)
        self.assertFalse(result.valid)
        self.assertEqual(result.state, "JARGON_RECURSION")

    def test_analogy_without_explicit_primitive_is_rejected(self):
        item = grounded_example()
        item["PRIMITIVE_OPERATION"] = "bytes move"
        result = guard.evaluate(ROOT, item)
        self.assertFalse(result.valid)
        self.assertEqual(result.state, "ANALOGY_WITHOUT_PRIMITIVE")

    def test_system_binding_must_return_to_grounded_concept(self):
        item = grounded_example()
        item["SYSTEM_SPECIFIC_BINDING"] = "this sentence discusses an unrelated object"
        result = guard.evaluate(ROOT, item)
        self.assertFalse(result.valid)
        self.assertEqual(result.state, "PRIMITIVE_NOT_BOUND_TO_SYSTEM")


if __name__ == "__main__":
    unittest.main()
