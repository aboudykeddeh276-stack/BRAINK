from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.btc_consensus import build_candidate
from runtime import btc_workload_substrate as substrate

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = Path(os.environ.get("KEX_BTC_STATE_DIR", ROOT / "state" / "kex_btc")).resolve()
DATA_DIR = STATE_DIR / "data"
LEDGER_DIR = STATE_DIR / "ledgers"
VERTICAL_RECEIPT_PATH = DATA_DIR / "btc_vertical_closure_latest.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    substrate.save_json(VERTICAL_RECEIPT_PATH, receipt)
    substrate.append_jsonl(LEDGER_DIR / "btc_vertical_closure.jsonl", receipt)
    return receipt


def _required_text(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for proof-bearing BTC vertical closure")
    return value


def _network_hrp(network: str) -> str:
    if network == "mainnet":
        return "bc"
    if network in {"testnet", "signet", "regtest"}:
        return "tb" if network != "regtest" else "bcrt"
    raise RuntimeError(f"unsupported BTC_NETWORK {network!r}")


def reconstruct_candidate(template: dict[str, Any], candidate: dict[str, Any], payout_address: str,
                          network_hrp: str) -> dict[str, Any]:
    """Rebuild the candidate from retained job parameters and require byte identity.

    This is the proof-bearing boundary that prevents a target-valid header from being
    submitted unless its block body, coinbase, Merkle root and header are all the
    deterministic result of the same template + payout + extranonce + nonce + nTime.
    """
    try:
        extranonce = bytes.fromhex(str(candidate["extranonce"]))
        nonce = int(candidate["nonce"])
        ntime = int(candidate["ntime"])
    except (KeyError, TypeError, ValueError) as exc:
        return {"valid": False, "reason": f"candidate reconstruction parameters invalid: {exc}"}

    rebuilt = build_candidate(
        template=template,
        payout_address=payout_address,
        extranonce=extranonce,
        nonce=nonce,
        ntime=ntime,
        network_hrp=network_hrp,
    )

    fields = (
        "header_hex",
        "block_hex",
        "block_hash",
        "merkle_root",
        "coinbase_txid",
        "coinbase_hex",
        "witness_commitment",
        "target",
        "target_valid",
        "nonce",
        "ntime",
        "extranonce",
        "workid",
    )
    comparison = {field: candidate.get(field) == rebuilt.get(field) for field in fields}
    mismatches = [field for field, equal in comparison.items() if not equal]
    return {
        "valid": not mismatches,
        "comparison": comparison,
        "mismatches": mismatches,
        "rebuilt": {field: rebuilt.get(field) for field in fields},
    }


def _chain_ready(chain: dict[str, Any], configured_network: str) -> tuple[bool, str | None]:
    expected_chain = {
        "mainnet": "main",
        "testnet": "test",
        "signet": "signet",
        "regtest": "regtest",
    }[configured_network]
    if str(chain.get("chain")) != expected_chain:
        return False, f"Bitcoin Core chain {chain.get('chain')!r} does not match BTC_NETWORK {configured_network!r}"
    if bool(chain.get("initialblockdownload", False)):
        return False, "Bitcoin Core is still in initial block download"
    if chain.get("verificationprogress") is not None and float(chain["verificationprogress"]) < float(
        os.environ.get("BTC_MIN_VERIFICATION_PROGRESS", "0.999")
    ):
        return False, "Bitcoin Core verification progress is below the configured readiness threshold"
    return True, None


def execute_vertical_closure() -> dict[str, Any]:
    started_at = utc_now()
    config = substrate.rpc_configuration()
    payout_address = _required_text("BTC_PAYOUT_ADDRESS")
    network_hrp = _network_hrp(str(config["network"]))

    connected, chain = substrate.check_rpc()
    if not connected:
        return _save_receipt({
            "started_at": started_at,
            "completed_at": utc_now(),
            "stage": "CORE_AUTHORITY",
            "status": "FAIL",
            "chain": chain,
            "reason": "Bitcoin Core RPC authority unavailable",
        })

    ready, reason = _chain_ready(chain, str(config["network"]))
    if not ready:
        return _save_receipt({
            "started_at": started_at,
            "completed_at": utc_now(),
            "stage": "CORE_AUTHORITY",
            "status": "FAIL",
            "chain": chain,
            "reason": reason,
        })

    tip_before = str(substrate.rpc_call("getbestblockhash", [])).lower()
    template_ok, template = substrate.request_template()
    if not template_ok:
        return _save_receipt({
            "started_at": started_at,
            "completed_at": utc_now(),
            "stage": "TEMPLATE_FETCHED",
            "status": "FAIL",
            "tip_before": tip_before,
            "reason": template.get("error", "getblocktemplate failed"),
        })
    if str(template.get("previousblockhash", "")).lower() != tip_before:
        return _save_receipt({
            "started_at": started_at,
            "completed_at": utc_now(),
            "stage": "TEMPLATE_FETCHED",
            "status": "FAIL",
            "tip_before": tip_before,
            "template_previousblockhash": template.get("previousblockhash"),
            "reason": "template is not bound to the observed current tip",
        })

    substrate.save_json(substrate.LIVE_TEMPLATE_PATH, template)

    solver = substrate.run_command(
        "KEX_OWNER_SOLVER_CMD",
        substrate.LIVE_TEMPLATE_PATH,
        substrate.LIVE_CANDIDATE_PATH,
    )
    candidate = solver.get("candidate") if isinstance(solver, dict) else None
    if not isinstance(candidate, dict) and substrate.env_flag("KEX_ACCEPT_CANDIDATE_FILE", True):
        candidate = substrate.load_json(substrate.LIVE_CANDIDATE_PATH)
    if not isinstance(candidate, dict):
        return _save_receipt({
            "started_at": started_at,
            "completed_at": utc_now(),
            "stage": "CANDIDATE_ASSEMBLED",
            "status": "FAIL",
            "solver": {k: v for k, v in solver.items() if k not in {"stdout_tail", "stderr_tail", "candidate"}},
            "reason": "owner solver did not produce a candidate",
        })

    reconstruction = reconstruct_candidate(template, candidate, payout_address, network_hrp)
    if not reconstruction.get("valid"):
        return _save_receipt({
            "started_at": started_at,
            "completed_at": utc_now(),
            "stage": "CANDIDATE_RECONSTRUCTION",
            "status": "FAIL",
            "template": {k: template.get(k) for k in ("height", "previousblockhash", "bits", "workid")},
            "reconstruction": reconstruction,
            "reason": "candidate differs from deterministic reconstruction",
        })

    if not bool(candidate.get("target_valid")):
        return _save_receipt({
            "started_at": started_at,
            "completed_at": utc_now(),
            "stage": "HASH_TESTED",
            "status": "PASS_NO_NETWORK_TARGET_HIT",
            "template": {k: template.get(k) for k in ("height", "previousblockhash", "bits", "workid")},
            "candidate": {k: candidate.get(k) for k in ("block_hash", "merkle_root", "coinbase_txid", "nonce", "ntime", "extranonce")},
            "reconstruction": {"valid": True, "mismatches": []},
            "reason": "candidate is structurally closed and reproducible; no network target hit occurred",
            "next": "continue_disjoint_work",
        })

    tip_submit = str(substrate.rpc_call("getbestblockhash", [])).lower()
    if tip_submit != tip_before:
        return _save_receipt({
            "started_at": started_at,
            "completed_at": utc_now(),
            "stage": "STALE_TIP_GATE",
            "status": "FAIL_STALE",
            "tip_before": tip_before,
            "tip_submit": tip_submit,
            "reason": "chain tip changed before submission",
        })

    submission = substrate.validate_and_submit(candidate, template)
    return _save_receipt({
        "started_at": started_at,
        "completed_at": utc_now(),
        "stage": "SUBMISSION",
        "status": "ACCEPTED_BY_NODE" if submission.get("accepted") else "SUBMISSION_NOT_ACCEPTED",
        "template": {k: template.get(k) for k in ("height", "previousblockhash", "bits", "workid")},
        "candidate": {k: candidate.get(k) for k in ("block_hash", "merkle_root", "coinbase_txid", "nonce", "ntime", "extranonce")},
        "reconstruction": {"valid": True, "mismatches": []},
        "submission": submission,
    })


if __name__ == "__main__":
    print(json.dumps(execute_vertical_closure(), indent=2, sort_keys=True))
