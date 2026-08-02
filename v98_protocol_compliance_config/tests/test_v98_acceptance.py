from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_v98_acceptance_harness as harness


def test_authority_map_blocks_human_and_agent_promotion() -> None:
    checks = harness.validate_authority_map(ROOT)
    assert checks["human_cannot_promote"] is True
    assert checks["agent_cannot_promote"] is True
    assert checks["acceptance_harness_can_promote"] is True


def test_all_services_implement_full_contract() -> None:
    receipts = harness.evaluate_services(ROOT)
    assert len(receipts) >= 9
    for receipt in receipts:
        assert set(receipt.stages) == set(harness.SERVICE_STAGES)
        assert all(receipt.stages.values())
        assert receipt.promotion_state == harness.LOCAL_PASS


def test_standards_catalog_contains_required_packs_and_no_certification_claim() -> None:
    catalog = harness.validate_standards_catalog(ROOT)
    assert catalog["required_missing"] == []
    assert catalog["reference_alignment_only"] is True
    assert catalog["standards_count"] >= 10


def test_acceptance_emits_receipt_ledger_and_outbox() -> None:
    final = harness.run_acceptance(ROOT, emit_receipt=True)
    assert final["status"] == "PASS_WITH_PROTOCOL_COMPLIANCE_CONFIG_AND_TARGET_HOST_DEPLOYMENT_GATES"
    assert final["authority_checks_passed"] is True
    assert final["ledger_readback"] is True
    assert final["hash_used_as_functional_proof"] is False
    assert final["certification_claimed"] is False
    outbox = Path(final["outbox_manifest"])
    assert outbox.exists()
    assert (ROOT / "evidence" / "FINAL_VERIFICATION.json").exists()
    data = json.loads((ROOT / "evidence" / "FINAL_VERIFICATION.json").read_text(encoding="utf-8"))
    assert data["services_connected"] == final["services_connected"]
