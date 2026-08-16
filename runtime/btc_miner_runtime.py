from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from btc_consensus import (
    assemble_block,
    build_coinbase,
    compact_target,
    dsha256,
    segwit_scriptpubkey,
    serialize_header,
    transaction_merkle_root,
)
from btc_workload_substrate import (
    LIVE_CANDIDATE_PATH,
    LIVE_TEMPLATE_PATH,
    check_rpc,
    request_template,
    save_json,
    utc_now,
    validate_and_submit,
)

SUPPORTED_NETWORKS = {"mainnet", "testnet", "signet", "regtest"}
CORE_CHAIN_NAMES = {
    "mainnet": "main",
    "testnet": "test",
    "signet": "signet",
    "regtest": "regtest",
}
NETWORK_HRPS = {
    "mainnet": "bc",
    "testnet": "tb",
    "signet": "tb",
    "regtest": "bcrt",
}


def core_chain_name(network: str) -> str:
    try:
        return CORE_CHAIN_NAMES[network]
    except KeyError as exc:
        raise ValueError(f"unsupported Bitcoin network: {network!r}") from exc


def network_hrp(network: str) -> str:
    try:
        return NETWORK_HRPS[network]
    except KeyError as exc:
        raise ValueError(f"unsupported Bitcoin network: {network!r}") from exc


def prepare_work(template: dict[str, Any], payout_address: str, extranonce: bytes, network: str) -> dict[str, Any]:
    """Build the nonce-invariant portion of a Bitcoin mining job exactly once."""
    transactions = list(template.get("transactions") or [])
    payout_script = segwit_scriptpubkey(payout_address, network_hrp(network))
    coinbase = build_coinbase(template, payout_script, extranonce)
    merkle_internal = transaction_merkle_root(coinbase.txid_internal, transactions)
    target = compact_target(str(template["bits"]))
    return {
        "transactions": transactions,
        "coinbase": coinbase,
        "merkle_internal": merkle_internal,
        "target": target,
        "ntime": int(template["curtime"]),
        "extranonce": extranonce,
    }


def candidate_from_hit(
    template: dict[str, Any], prepared: dict[str, Any], header: bytes, digest: bytes, nonce: int
) -> dict[str, Any]:
    """Assemble the expensive full block only after the 80-byte header satisfies target."""
    coinbase = prepared["coinbase"]
    block = assemble_block(header, coinbase, prepared["transactions"])
    return {
        "block_hex": block.hex(),
        "header_hex": header.hex(),
        "block_hash": digest[::-1].hex(),
        "hash_integer": int.from_bytes(digest, "little"),
        "target": prepared["target"],
        "target_valid": True,
        "merkle_root": prepared["merkle_internal"][::-1].hex(),
        "coinbase_txid": coinbase.txid_internal[::-1].hex(),
        "coinbase_hex": coinbase.full.hex(),
        "witness_commitment": coinbase.witness_commitment.hex() if coinbase.witness_commitment else None,
        "nonce": nonce,
        "ntime": prepared["ntime"],
        "extranonce": prepared["extranonce"].hex(),
        "workid": template.get("workid"),
        "construction_mode": "PREPARED_INVARIANTS_HEADER_SCAN_ASSEMBLE_ON_HIT",
    }


def scan_prepared_work(
    template: dict[str, Any], prepared: dict[str, Any], max_hashes: int
) -> tuple[dict[str, Any] | None, dict[str, Any], int]:
    """Hash only candidate headers in the hot loop and retain the best observed hash."""
    best: dict[str, Any] | None = None
    limit = min(max(1, max_hashes), 1 << 32)
    for nonce in range(limit):
        header = serialize_header(
            template,
            prepared["merkle_internal"],
            nonce,
            prepared["ntime"],
        )
        digest = dsha256(header)
        hash_integer = int.from_bytes(digest, "little")
        block_hash = digest[::-1].hex()
        if best is None or hash_integer < best["hash_integer"]:
            best = {
                "block_hash": block_hash,
                "hash_integer": hash_integer,
                "nonce": nonce,
            }
        if hash_integer <= prepared["target"]:
            return candidate_from_hit(template, prepared, header, digest, nonce), best, nonce + 1
    return None, best or {}, limit


def execute() -> dict[str, Any]:
    network = os.environ.get("BTC_NETWORK", "mainnet").strip().lower()
    if network not in SUPPORTED_NETWORKS:
        return {
            "state": "CONFIGURATION_BLOCKED",
            "reason": "BTC_NETWORK is unsupported",
            "network": network,
            "supported_networks": sorted(SUPPORTED_NETWORKS),
        }

    payout = os.environ.get("BTC_PAYOUT_ADDRESS", "").strip()
    if not payout:
        return {
            "state": "CONFIGURATION_BLOCKED",
            "reason": "BTC_PAYOUT_ADDRESS is required",
            "network": network,
        }

    connected, chain = check_rpc()
    if not connected:
        return {
            "state": "QUIESCED",
            "reason": "Bitcoin Core RPC unavailable; synthetic mainnet work is forbidden",
            "network": network,
            "rpc": chain,
        }

    observed_chain = str(chain.get("chain", ""))
    expected_chain = core_chain_name(network)
    if observed_chain != expected_chain:
        return {
            "state": "QUIESCED",
            "reason": "configured network does not match Bitcoin Core chain",
            "network": network,
            "expected_core_chain": expected_chain,
            "chain": observed_chain,
        }
    if chain.get("initialblockdownload") is True:
        return {
            "state": "QUIESCED",
            "reason": "Bitcoin Core is in initial block download",
            "network": network,
        }
    verification = float(chain.get("verificationprogress", 0.0))
    if verification < float(os.environ.get("BTC_MIN_VERIFICATION_PROGRESS", "0.999")):
        return {
            "state": "QUIESCED",
            "reason": "Bitcoin Core verification progress below mining gate",
            "verificationprogress": verification,
        }

    ok, template = request_template()
    if not ok:
        return {
            "state": "QUIESCED",
            "reason": "getblocktemplate failed",
            "template_result": template,
        }
    required = (
        "version",
        "previousblockhash",
        "bits",
        "curtime",
        "height",
        "coinbasevalue",
        "transactions",
    )
    missing = [key for key in required if key not in template]
    if missing:
        return {
            "state": "TEMPLATE_REJECTED",
            "reason": "missing required getblocktemplate fields",
            "missing": missing,
        }
    save_json(LIVE_TEMPLATE_PATH, template)

    max_hashes = max(1, int(os.environ.get("KEX_MAX_HASHES_PER_JOB", "100000")))
    extranonce_counter = int(os.environ.get("KEX_EXTRANONCE", "0"), 0)
    if not 0 <= extranonce_counter < 1 << 64:
        return {
            "state": "CONFIGURATION_BLOCKED",
            "reason": "KEX_EXTRANONCE must fit in an unsigned 64-bit field",
            "network": network,
        }
    extranonce = extranonce_counter.to_bytes(8, "little", signed=False)

    try:
        prepared = prepare_work(template, payout, extranonce, network)
        candidate, best, hashes_tested = scan_prepared_work(template, prepared, max_hashes)
    except (KeyError, TypeError, ValueError) as exc:
        return {
            "state": "TEMPLATE_REJECTED",
            "reason": str(exc),
            "network": network,
            "template_height": template.get("height"),
        }

    if candidate is not None:
        save_json(LIVE_CANDIDATE_PATH, candidate)
        submission = validate_and_submit(candidate, template)
        return {
            "state": "NETWORK_TARGET_HIT" if not submission.get("accepted") else "ACCEPTED_BY_NODE",
            "network": network,
            "hashes_tested": hashes_tested,
            "construction_mode": candidate["construction_mode"],
            "candidate": {
                key: candidate[key]
                for key in (
                    "block_hash",
                    "nonce",
                    "ntime",
                    "extranonce",
                    "merkle_root",
                    "coinbase_txid",
                )
            },
            "submission": submission,
            "completed_at": utc_now(),
        }

    return {
        "state": "SEARCH_WINDOW_EXHAUSTED",
        "network": network,
        "hashes_tested": hashes_tested,
        "construction_mode": "PREPARED_INVARIANTS_HEADER_SCAN_ASSEMBLE_ON_HIT",
        "best_hash": best.get("block_hash"),
        "best_hash_integer": best.get("hash_integer"),
        "best_nonce": best.get("nonce"),
        "target": prepared["target"],
        "template_height": template["height"],
        "merkle_root": prepared["merkle_internal"][::-1].hex(),
        "coinbase_txid": prepared["coinbase"].txid_internal[::-1].hex(),
        "completed_at": utc_now(),
    }


if __name__ == "__main__":
    print(json.dumps(execute(), indent=2, sort_keys=True))
