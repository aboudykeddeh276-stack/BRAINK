from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_mirror_update_lane as mirror


class MirrorUpdateLaneTests(unittest.TestCase):
    def test_config_preserves_non_manual_promotion(self) -> None:
        cfg = mirror.read_json(ROOT / "config" / "mirror_update_lane.json")
        rules = cfg["promotion_rules"]
        self.assertFalse(rules["manual_promotion_allowed"])
        self.assertFalse(rules["agent_self_promotion_allowed"])
        self.assertTrue(rules["acceptance_harness_promotion_required"])
        self.assertFalse(rules["hash_used_as_functional_proof"])

    def test_required_documents_exist(self) -> None:
        cfg = mirror.read_json(ROOT / "config" / "mirror_update_lane.json")
        for relative in cfg["source_documents"] + cfg["required_mirror_documents"]:
            path = ROOT / relative
            self.assertTrue(path.exists(), relative)
            self.assertTrue(path.is_file(), relative)

    def test_execution_writes_readback_and_handoff(self) -> None:
        final = mirror.run_mirror_lane(ROOT, emit_receipt=True)
        receipt = final["receipt"]
        self.assertEqual(receipt["promotion_state"], "LOCAL_PASS")
        self.assertTrue(receipt["all_documents_present"])
        self.assertTrue(receipt["ledger_readback"])
        self.assertFalse(final["hash_used_as_functional_proof"])
        self.assertFalse(final["certification_claimed"])
        outbox = Path(receipt["outbox_manifest"])
        self.assertTrue(outbox.exists())
        evidence = ROOT / "evidence" / "mirror_update_lane_receipt.json"
        self.assertTrue(evidence.exists())
        payload = json.loads(evidence.read_text(encoding="utf-8"))
        self.assertEqual(payload["receipt"]["lane_id"], "mirror_update_lane")


if __name__ == "__main__":
    unittest.main()
