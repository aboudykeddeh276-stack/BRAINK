from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_v98_acceptance_harness as harness


class V98AcceptanceTests(unittest.TestCase):
    def test_authority_map_blocks_human_and_agent_promotion(self) -> None:
        checks = harness.validate_authority_map(ROOT)
        self.assertTrue(checks["human_cannot_promote"])
        self.assertTrue(checks["agent_cannot_promote"])
        self.assertTrue(checks["acceptance_harness_can_promote"])

    def test_all_services_implement_full_contract(self) -> None:
        receipts = harness.evaluate_services(ROOT)
        self.assertGreaterEqual(len(receipts), 9)
        for receipt in receipts:
            self.assertEqual(set(receipt.stages), set(harness.SERVICE_STAGES))
            self.assertTrue(all(receipt.stages.values()))
            self.assertEqual(receipt.promotion_state, harness.LOCAL_PASS)

    def test_standards_catalog_contains_required_packs_and_no_certification_claim(self) -> None:
        catalog = harness.validate_standards_catalog(ROOT)
        self.assertEqual(catalog["required_missing"], [])
        self.assertTrue(catalog["reference_alignment_only"])
        self.assertGreaterEqual(catalog["standards_count"], 10)

    def test_acceptance_emits_receipt_ledger_and_outbox(self) -> None:
        final = harness.run_acceptance(ROOT, emit_receipt=True)
        self.assertEqual(
            final["status"],
            "PASS_WITH_PROTOCOL_COMPLIANCE_CONFIG_AND_TARGET_HOST_DEPLOYMENT_GATES",
        )
        self.assertTrue(final["authority_checks_passed"])
        self.assertTrue(final["ledger_readback"])
        self.assertFalse(final["hash_used_as_functional_proof"])
        self.assertFalse(final["certification_claimed"])
        outbox = Path(final["outbox_manifest"])
        self.assertTrue(outbox.exists())
        verification = ROOT / "evidence" / "FINAL_VERIFICATION.json"
        self.assertTrue(verification.exists())
        data = json.loads(verification.read_text(encoding="utf-8"))
        self.assertEqual(data["services_connected"], final["services_connected"])


if __name__ == "__main__":
    unittest.main()
