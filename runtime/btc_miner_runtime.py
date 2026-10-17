from __future__ import annotations

import json
import os
import struct
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


def network_hrp(network: str) -> str:
    return "bc" if network == "mainnet" else "tb" if network in {"testnet", "signet"} else "bcrt"


def prepare_nonce_work(
    template: dict[str, Any],
    payout_address: str,
    extranonce: bytes,
    *,
    network_hrp_value: str,
) -> dict[str, Any]:
    """Construct every nonce-invariant part of one Bitcoin block workload once.

    Coinbase serialization, witness commitment, transaction Merkle construction,
    block template transactions and the first 76 bytes of the block header do not
    change while traversing the 32-bit nonce field.  Keeping those values stable
    prevents the reference worker from rebuilding a complete block for every hash.
    """
    payout_script = segwit_scriptpubkey(payout_address, network_hrp_value)
    transactions = list(template.get("transactions") or [])
    coinbase = build_coinbase(template, payout_script, extranonce)
    merkle = transaction_merkle_root(coinbase.txid_internal, transactions)
    header = bytearray(serialize_header(template, merkle, 0))
    if len(header) != 80:
        raise AssertionError("prepared Bitcoin header must be 80 bytes")
    return {
        "template": template,
        "transactions": transactions,
        "coinbase": coinbase,
        "merkle": merkle,
        "header": header,
        "target": compact_target(str(template["bits"])),
        "workid": template.get("workid"),
        "extranonce": extranonce,
    }


def candidate_from_prepared_work(work: dict[str, Any], nonce: int) -> dict[str, Any]:
    if not 0 <= nonce <= 0xFFFFFFFF:
        raise ValueError("nonce outside uint32")
    header = bytearray(work["header"])
    struct.pack_into("<I", header, 76, nonce)
    header_bytes = bytes(header)
    digest = dsha256(header_bytes)
    hash_integer = int.from_bytes(digest, "little")
    coinbase = work["coinbase"]
    merkle = work["merkle"]
    template = work["template"]
    block = assemble_block(header_bytes, coinbase, work["transactions"])
    return {
        "block_hex": block.hex(),
        "header_hex": header_bytes.hex(),
        "block_hash": digest[::-1].hex(),
        "hash_integer": hash_integer,
        "target": work["target"],
        "target_valid": hash_integer <= work["target"],
        "merkle_root": merkle[::-1].hex(),
        "coinbase_txid": coinbase.txid_internal[::-1].hex(),
        "coinbase_hex": coinbase.full.hex(),
        "witness_commitment": coinbase.witness_commitment.hex() if coinbase.witness_commitment else None,
        "nonce": nonce,
        "ntime": int(template.get("curtime")),
        "extranonce": work["extranonce"].hex(),
        "workid": work["workid"],
    }


def search_prepared_nonce_work(work: dict[str, Any], max_hashes: int) -> dict[str, Any]:
    """Hash only the mutable 80-byte header during nonce traversal.

    The complete serialized block is assembled only when a target-valid nonce is
    found.  This keeps protocol semantics identical while removing repeated
    coinbase/Merkle/full-block construction from the inner hash loop.
    """
    limit = min(max(1, max_hashes), 1 << 32)
    header = bytearray(work["header"])
    target = int(work["target"])
    best_hash_integer: int | None = None
    best_hash: str | None = None
    for nonce in range(limit):
        struct.pack_into("<I", header, 76, nonce)
        digest = dsha256(header)
        hash_integer = int.from_bytes(digest, "little")
        if best_hash_integer is None or hash_integer < best_hash_integer:
            best_hash_integer = hash_integer
            best_hash = digest[::-1].hex()
        if hash_integer <= target:
            return {
                "solved": True,
                "hashes_tested": nonce + 1,
                "candidate": candidate_from_prepared_work(work, nonce),
                "best_hash": best_hash,
                "best_hash_integer": best_hash_integer,
            }
    return {
        "solved": False,
        "hashes_tested": limit,
        "candidate": None,
        "best_hash": best_hash,
        "best_hash_integer": best_hash_integer,
        "target": target,
    }


def execute() -> dict:
    network = os.environ.get("BTC_NETWORK", "mainnet").strip().lower()
    payout = os.environ.get("BTC_PAYOUT_ADDRESS", "").strip()
    if not payout:
        return {"state": "CONFIGURATION_BLOCKED", "reason": "BTC_PAYOUT_ADDRESS is required", "network": network}

    connected, chain = check_rpc()
    if not connected:
        return {"state": "QUIESCED", "reason": "Bitcoin Core RPC unavailable; synthetic mainnet work is forbidden", "network": network, "rpc": chain}
    if str(chain.get("chain", "")) != network and not (network == "mainnet" and chain.get("chain") == "main"):
        return {"state": "QUIESCED", "reason": "configured network does not match Bitcoin Core chain", "network": network, "chain": chain.get("chain")}
    if chain.get("initialblockdownload") is True:
        return {"state": "QUIESCED", "reason": "Bitcoin Core is in initial block download", "network": network}
    verification = float(chain.get("verificationprogress", 0.0))
    if verification < float(os.environ.get("BTC_MIN_VERIFICATION_PROGRESS", "0.999")):
        return {"state": "QUIESCED", "reason": "Bitcoin Core verification progress below mining gate", "verificationprogress": verification}

    ok, template = request_template()
    if not ok:
        return {"state": "QUIESCED", "reason": "getblocktemplate failed", "template_result": template}
    required = ("version", "previousblockhash", "bits", "curtime", "height", "coinbasevalue", "transactions")
    missing = [key for key in required if key not in template]
    if missing:
        return {"state": "TEMPLATE_REJECTED", "reason": "missing required getblocktemplate fields", "missing": missing}
    save_json(LIVE_TEMPLATE_PATH, template)

    max_hashes = max(1, int(os.environ.get("KEX_MAX_HASHES_PER_JOB", "100000")))
    extranonce_counter = int(os.environ.get("KEX_EXTRANONCE", "0"), 0)
    extranonce = extranonce_counter.to_bytes(8, "little", signed=False)
    work = prepare_nonce_work(template, payout, extranonce, network_hrp_value=network_hrp(network))
    search = search_prepared_nonce_work(work, max_hashes)
    candidate = search.get("candidate")
    if isinstance(candidate, dict):
        save_json(LIVE_CANDIDATE_PATH, candidate)
        submission = validate_and_submit(candidate, template)
        return {
            "state": "NETWORK_TARGET_HIT" if not submission.get("accepted") else "ACCEPTED_BY_NODE",
            "network": network,
            "hashes_tested": search["hashes_tested"],
            "candidate": {k: candidate[k] for k in ("block_hash", "nonce", "ntime", "extranonce", "merkle_root", "coinbase_txid")},
            "submission": submission,
            "worker_mode": "cached_block_bound_header_search",
            "completed_at": utc_now(),
        }

    return {
        "state": "SEARCH_WINDOW_EXHAUSTED",
        "network": network,
        "hashes_tested": search["hashes_tested"],
        "best_hash": search["best_hash"],
        "best_hash_integer": search["best_hash_integer"],
        "target": search["target"],
        "template_height": template["height"],
        "worker_mode": "cached_block_bound_header_search",
        "completed_at": utc_now(),
    }


if __name__ == "__main__":
    print(json.dumps(execute(), indent=2, sort_keys=True))
