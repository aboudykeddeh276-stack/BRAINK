from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from runtime.btc_mining_lineage import MiningRun, canonical_digest, utc_now
from runtime.btc_workload_substrate import (
    DATA_DIR,
    LEDGER_DIR,
    LIVE_CANDIDATE_PATH,
    LIVE_TEMPLATE_PATH,
    append_jsonl,
    check_rpc,
    load_json,
    request_template,
    rpc_call,
    run_command,
    save_json,
    start_or_resolve_node,
    validate_and_submit,
)

VERTICAL_RECEIPT_PATH = DATA_DIR / "btc_vertical_closure_latest.json"
VERTICAL_LEDGER_PATH = LEDGER_DIR / "btc_vertical_closure.jsonl"


def _public_chain_receipt(chain: dict[str, Any]) -> dict[str, Any]:
    return {key: chain.get(key) for key in (
        "chain", "blocks", "headers", "bestblockhash", "difficulty",
        "verificationprogress", "initialblockdownload", "pruned",
    )}


def _candidate_from_existing_solver(template_path: Path) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    solver = run_command("KEX_OWNER_SOLVER_CMD", template_path, LIVE_CANDIDATE_PATH)
    candidate = solver.get("candidate") if isinstance(solver, dict) else None
    if not isinstance(candidate, dict) and os.environ.get("KEX_ACCEPT_CANDIDATE_FILE", "1").lower() not in {"0", "false", "no", "off"}:
        candidate = load_json(LIVE_CANDIDATE_PATH)
    summary = {key: value for key, value in solver.items() if key not in {"candidate", "stdout_tail", "stderr_tail"}}
    return candidate if isinstance(candidate, dict) else None, summary


def execute_vertical_closure() -> dict[str, Any]:
    """Bind the existing Core/template/solver/submission surfaces into one lineage-bearing run.

    This function intentionally does not replace btc_consensus or the configured owner solver.
    It records and verifies causal continuity between the already-present surfaces.
    """
    started_at = utc_now()
    node = start_or_resolve_node()
    connected, chain = check_rpc()
    if not connected:
        result = {
            "started_at": started_at,
            "completed_at": utc_now(),
            "stage": "CORE_AUTHORITY",
            "status": "UNOBSERVED",
            "node": node,
            "chain": chain,
        }
        save_json(VERTICAL_RECEIPT_PATH, result)
        append_jsonl(VERTICAL_LEDGER_PATH, result)
        return result

    template_received, template = request_template()
    if not template_received:
        result = {
            "started_at": started_at,
            "completed_at": utc_now(),
            "stage": "TEMPLATE",
            "status": "FAILED",
            "node": node,
            "chain": _public_chain_receipt(chain),
            "template_result": template,
        }
        save_json(VERTICAL_RECEIPT_PATH, result)
        append_jsonl(VERTICAL_LEDGER_PATH, result)
        return result

    save_json(LIVE_TEMPLATE_PATH, template)
    run = MiningRun.from_template(template)
    run.record("CORE_AUTHORITY", "PASS", canonical_digest(_public_chain_receipt(chain)), {
        "chain": _public_chain_receipt(chain),
        "rpc_bestblockhash": rpc_call("getbestblockhash", []),
    })

    engine = run_command("KEX_ENGINE_CMD", LIVE_TEMPLATE_PATH)
    candidate, solver = _candidate_from_existing_solver(LIVE_TEMPLATE_PATH)
    if candidate is None:
        result = {
            "started_at": started_at,
            "completed_at": utc_now(),
            "run_id": run.run_id,
            "stage": "CANDIDATE",
            "status": "UNOBSERVED",
            "engine": engine,
            "solver": solver,
            "evidence": run.evidence(),
        }
        save_json(VERTICAL_RECEIPT_PATH, result)
        append_jsonl(VERTICAL_LEDGER_PATH, result)
        return result

    # Existing solvers predate MiningRun. Bind their candidate to this exact template/run,
    # then verify the complete serialized object before any submission decision.
    candidate = dict(candidate)
    candidate["run_id"] = run.run_id
    candidate["template_digest"] = run.template_digest
    candidate.setdefault("lineage", {
        "previousblockhash": run.previousblockhash,
        "height": int(template["height"]),
        "workid": template.get("workid"),
    })
    verification = run.verify_candidate(candidate)
    current_tip = rpc_call("getbestblockhash", [])
    gate = run.submission_gate(candidate, current_tip)

    # Preserve the established submission implementation as the sole RPC submission path.
    submission = validate_and_submit(candidate, template) if gate["submission_ready"] else {
        "attempted": False,
        "accepted": False,
        "reason": gate["reason"],
    }
    result = {
        "started_at": started_at,
        "completed_at": utc_now(),
        "run_id": run.run_id,
        "status": "SUBMITTED" if submission.get("attempted") else "EXECUTED",
        "template": {key: template.get(key) for key in ("height", "previousblockhash", "bits", "target", "workid")},
        "engine": engine,
        "solver": solver,
        "verification": verification,
        "submission_gate": gate,
        "submission": submission,
        "evidence": run.evidence(),
    }
    save_json(VERTICAL_RECEIPT_PATH, result)
    append_jsonl(VERTICAL_LEDGER_PATH, result)
    return result


if __name__ == "__main__":
    print(json.dumps(execute_vertical_closure(), indent=2, sort_keys=True))
