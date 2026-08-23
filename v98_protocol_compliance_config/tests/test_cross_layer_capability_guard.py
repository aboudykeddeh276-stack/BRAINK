from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_cross_layer_capability_guard as guard


def full_traversal(found: bool = True):
    policy = guard.load_policy(ROOT)
    rows = []
    for layer in policy["required_layers"]:
        rows.append({
            "layer_id": layer,
            "search_scope": f"repository/runtime scope for {layer}",
            "mechanics_found": [f"existing_{layer.lower()}_mechanic"] if found else [],
            "evidence_paths": [f"evidence/{layer.lower()}.json"],
            "result_state": "FOUND_REUSE" if found else "NO_MATCH_WITH_EVIDENCE",
        })
    return rows


class CrossLayerCapabilityGuardTests(unittest.TestCase):
    def test_missing_one_layer_blocks_capability_missing_claim(self):
        rows = full_traversal()[:-1]
        result = guard.evaluate(ROOT, rows, "CAPABILITY_MISSING")
        self.assertFalse(result.permitted)
        self.assertEqual(result.state, "TRAVERSAL_INCOMPLETE")

    def test_duplicate_layer_cannot_fake_complete_traversal(self):
        rows = full_traversal()
        rows[-1] = dict(rows[0])
        result = guard.evaluate(ROOT, rows, "CAPABILITY_LIMITATION")
        self.assertFalse(result.permitted)
        self.assertEqual(result.state, "TRAVERSAL_INCOMPLETE")

    def test_empty_evidence_cannot_satisfy_traversal(self):
        rows = full_traversal()
        rows[0]["evidence_paths"] = []
        result = guard.evaluate(ROOT, rows, "CAPABILITY_MISSING")
        self.assertFalse(result.permitted)
        self.assertIn("missing_evidence_paths", result.reason)

    def test_existing_mechanic_blocks_replacement_architecture(self):
        result = guard.evaluate(ROOT, full_traversal(), "SUBSTITUTE_ARCHITECTURE")
        self.assertFalse(result.permitted)
        self.assertEqual(result.state, "REUSE_REQUIRED")

    def test_existing_kex_concurrency_blocks_sequentialization(self):
        result = guard.evaluate(ROOT, full_traversal(), "SEQUENTIALIZE_CONCURRENT_MECHANIC")
        self.assertFalse(result.permitted)
        self.assertEqual(result.reason, "kex_concurrency_mechanic_exists")
        self.assertTrue(result.concurrency_preserved)

    def test_local_miss_cannot_be_global_limitation_while_other_layers_have_mechanics(self):
        rows = full_traversal()
        rows[0]["mechanics_found"] = []
        rows[0]["result_state"] = "NO_MATCH_WITH_EVIDENCE"
        result = guard.evaluate(ROOT, rows, "CAPABILITY_MISSING")
        self.assertFalse(result.permitted)
        self.assertEqual(result.state, "REUSE_REQUIRED")

    def test_all_layers_no_match_only_makes_negative_claim_eligible_not_proven(self):
        result = guard.evaluate(ROOT, full_traversal(found=False), "CAPABILITY_LIMITATION")
        self.assertTrue(result.permitted)
        self.assertEqual(result.state, "ALL_LAYERS_EXHAUSTED")
        self.assertIn("requires_independent_evidence_review", result.reason)

    def test_positive_result_without_mechanics_is_rejected(self):
        rows = full_traversal()
        rows[2]["mechanics_found"] = []
        result = guard.evaluate(ROOT, rows, "DERIVE_REPLACEMENT")
        self.assertFalse(result.permitted)
        self.assertEqual(result.state, "TRAVERSAL_INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
