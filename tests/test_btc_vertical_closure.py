from __future__ import annotations

import copy

from runtime import btc_vertical_closure as closure


def _fixture_candidate():
    template = {
        "height": 840000,
        "coinbasevalue": 312500000,
        "version": 536870912,
        "previousblockhash": "00" * 32,
        "bits": "207fffff",
        "curtime": 1710000000,
        "transactions": [],
        "workid": "fixture-work",
    }
    # Known-valid mainnet v0 P2WPKH address used only for deterministic construction.
    payout = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
    candidate = closure.build_candidate(
        template=template,
        payout_address=payout,
        extranonce=bytes.fromhex("0102030405060708"),
        nonce=7,
        ntime=1710000000,
        network_hrp="bc",
    )
    return template, payout, candidate


def test_exact_candidate_reconstruction_passes():
    template, payout, candidate = _fixture_candidate()
    result = closure.reconstruct_candidate(template, candidate, payout, "bc")
    assert result["valid"] is True
    assert result["mismatches"] == []


def test_header_mutation_fails_reconstruction():
    template, payout, candidate = _fixture_candidate()
    mutated = copy.deepcopy(candidate)
    mutated["header_hex"] = ("00" if candidate["header_hex"][:2] != "00" else "01") + candidate["header_hex"][2:]
    result = closure.reconstruct_candidate(template, mutated, payout, "bc")
    assert result["valid"] is False
    assert "header_hex" in result["mismatches"]


def test_block_body_mutation_fails_reconstruction():
    template, payout, candidate = _fixture_candidate()
    mutated = copy.deepcopy(candidate)
    mutated["block_hex"] = candidate["block_hex"][:-2] + ("00" if candidate["block_hex"][-2:] != "00" else "01")
    result = closure.reconstruct_candidate(template, mutated, payout, "bc")
    assert result["valid"] is False
    assert "block_hex" in result["mismatches"]


def test_coinbase_identity_mutation_fails_reconstruction():
    template, payout, candidate = _fixture_candidate()
    mutated = copy.deepcopy(candidate)
    mutated["coinbase_txid"] = "00" * 32
    result = closure.reconstruct_candidate(template, mutated, payout, "bc")
    assert result["valid"] is False
    assert "coinbase_txid" in result["mismatches"]


def test_extranonce_mutation_fails_reconstruction():
    template, payout, candidate = _fixture_candidate()
    mutated = copy.deepcopy(candidate)
    mutated["extranonce"] = "0807060504030201"
    result = closure.reconstruct_candidate(template, mutated, payout, "bc")
    assert result["valid"] is False
    assert result["mismatches"]


def test_chain_ready_rejects_ibd():
    ready, reason = closure._chain_ready(
        {"chain": "main", "initialblockdownload": True, "verificationprogress": 1.0},
        "mainnet",
    )
    assert ready is False
    assert "initial block download" in reason


def test_chain_ready_rejects_network_mismatch():
    ready, reason = closure._chain_ready(
        {"chain": "test", "initialblockdownload": False, "verificationprogress": 1.0},
        "mainnet",
    )
    assert ready is False
    assert "does not match" in reason
