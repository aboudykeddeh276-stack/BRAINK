from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from btc_consensus import build_candidate
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
    best = None
    for nonce in range(min(max_hashes, 1 << 32)):
        candidate = build_candidate(template, payout, extranonce, nonce, network_hrp=network_hrp(network))
        if best is None or candidate["hash_integer"] < best["hash_integer"]:
            best = candidate
        if candidate["target_valid"]:
            save_json(LIVE_CANDIDATE_PATH, candidate)
            submission = validate_and_submit(candidate, template)
            return {
                "state": "NETWORK_TARGET_HIT" if not submission.get("accepted") else "ACCEPTED_BY_NODE",
                "network": network,
                "hashes_tested": nonce + 1,
                "candidate": {k: candidate[k] for k in ("block_hash", "nonce", "ntime", "extranonce", "merkle_root", "coinbase_txid")},
                "submission": submission,
                "completed_at": utc_now(),
            }

    return {
        "state": "SEARCH_WINDOW_EXHAUSTED",
        "network": network,
        "hashes_tested": max_hashes,
        "best_hash": best["block_hash"] if best else None,
        "best_hash_integer": best["hash_integer"] if best else None,
        "target": best["target"] if best else None,
        "template_height": template["height"],
        "completed_at": utc_now(),
    }


if __name__ == "__main__":
    print(json.dumps(execute(), indent=2, sort_keys=True))
