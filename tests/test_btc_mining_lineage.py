from __future__ import annotations

import copy

import pytest

from runtime.btc_mining_lineage import MiningRun


# Deterministic structural fixture. It deliberately does not claim a live Core template
# or a mainnet target hit; the tests characterize lineage/reconstruction mechanics.
TEMPLATE = {
    "height": 900000,
    "previousblockhash": "11" * 32,
    "version": 0x20000000,
    "bits": "1d00ffff",
    "curtime": 1750000000,
    "coinbasevalue": 312500000,
    "transactions": [],
    "workid": "fixture-work-1",
}

# BIP173 v0 mainnet example address with valid checksum/program.
PAYOUT = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kygt080"


def test_candidate_preserves_bound_template_and_exact_header():
    run = MiningRun.from_template(copy.deepcopy(TEMPLATE))
    candidate = run.build(PAYOUT, b"\x01" * 8, nonce=7)
    verification = run.verify_candidate(candidate)
    assert candidate["run_id"] == run.run_id
    assert candidate["template_digest"] == run.template_digest
    assert bytes.fromhex(candidate["block_hex"])[:80] == bytes.fromhex(candidate["header_hex"])
    assert verification["previousblockhash"] == TEMPLATE["previousblockhash"]
    assert verification["bits"] == TEMPLATE["bits"]


def test_tampered_header_is_rejected_even_when_candidate_metadata_is_unchanged():
    run = MiningRun.from_template(copy.deepcopy(TEMPLATE))
    candidate = run.build(PAYOUT, b"\x02" * 8, nonce=9)
    raw = bytearray.fromhex(candidate["block_hex"])
    raw[10] ^= 0x01
    candidate["block_hex"] = raw.hex()
    with pytest.raises(ValueError, match="exact header bytes"):
        run.verify_candidate(candidate)


def test_candidate_from_another_run_is_rejected():
    run_a = MiningRun.from_template(copy.deepcopy(TEMPLATE))
    other = copy.deepcopy(TEMPLATE)
    other["height"] += 1
    other["previousblockhash"] = "22" * 32
    run_b = MiningRun.from_template(other)
    candidate = run_a.build(PAYOUT, b"\x03" * 8, nonce=11)
    with pytest.raises(ValueError, match="run_id"):
        run_b.verify_candidate(candidate)


def test_no_target_hit_is_normal_not_submission_ready():
    run = MiningRun.from_template(copy.deepcopy(TEMPLATE))
    candidate = run.build(PAYOUT, b"\x04" * 8, nonce=13)
    gate = run.submission_gate(candidate, TEMPLATE["previousblockhash"])
    if not candidate["target_valid"]:
        assert gate == {
            "run_id": run.run_id,
            "fresh_tip": True,
            "target_valid": False,
            "submission_ready": False,
            "reason": "network_target_not_met",
        }


def test_stale_tip_blocks_submission_independently_of_other_predicates():
    run = MiningRun.from_template(copy.deepcopy(TEMPLATE))
    candidate = run.build(PAYOUT, b"\x05" * 8, nonce=17)
    gate = run.submission_gate(candidate, "33" * 32)
    assert gate["fresh_tip"] is False
    assert gate["submission_ready"] is False
    assert gate["reason"] == "stale_tip"


def test_evidence_chain_is_append_only_and_digest_linked():
    run = MiningRun.from_template(copy.deepcopy(TEMPLATE))
    candidate = run.build(PAYOUT, b"\x06" * 8, nonce=19)
    run.submission_gate(candidate, TEMPLATE["previousblockhash"])
    evidence = run.evidence()
    assert evidence[0]["previous_receipt_digest"] is None
    for previous, current in zip(evidence, evidence[1:]):
        assert current["previous_receipt_digest"] == previous["receipt_digest"]
