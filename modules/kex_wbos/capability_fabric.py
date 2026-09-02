#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from action_runtime import ACTION_LEDGER, BASE, execute_action
from capabilities import mint_capability
from hardening import atomic_write_text, canonical_json_bytes, sha256_bytes
from ledger_checkpoint import checkpoint_ledger
from outbox import DurableOutbox
from workbook_semantics import write_semantic_index

AUTHORITY = "A.KEDDEH / KEDDEH_SYSTEMS / BRAINK / CASEPATH"
REPORT_ROOT = BASE / "reports" / "kex-wbos" / "capability-fabric"
OUTBOX = DurableOutbox(BASE / "runtime" / "outbox" / "external-actions-v1.json")
TL2_REPORT = BASE / "reports" / "kex-wbos" / "tl2-deployment.json"


def _status(receipt: dict[str, Any]) -> str:
    return str(receipt.get("status", "UNKNOWN"))


def _make_workbook(run_id: str) -> Path:
    path = BASE / "runtime" / "workbooks" / f"CAPABILITY_FABRIC_{run_id}.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "FLOW"
    ws.append(["node", "value", "derived"])
    ws.append(["ROOT", 1, "=B2*2"])
    ws.append(["FLOW-01", 2, "=B3+B2"])
    ws.append(["FLOW-02", 3, "=B4+B3"])
    cyc = wb.create_sheet("CYCLE_PROBE")
    cyc["A1"] = "=B1"
    cyc["B1"] = "=A1"
    wb.save(path)
    return path


def _read_tl2_receipt() -> dict[str, Any]:
    if not TL2_REPORT.exists():
        return {"status": "UNOBSERVED", "promotion": None}
    try:
        data = json.loads(TL2_REPORT.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"status": "INVALID", "promotion": None}
    except Exception as exc:
        return {"status": "READ_FAILED", "promotion": None, "error": type(exc).__name__}


def exercise(*, engage_tl2: bool = False) -> dict[str, Any]:
    run_id = uuid.uuid4().hex[:12]
    started = time.time()
    secret = os.getenv("KEX_CAPABILITY_SECRET") or f"exercise-{uuid.uuid4().hex}"
    prior_require = os.getenv("KEX_REQUIRE_SCOPED_CAPABILITIES")
    prior_secret = os.getenv("KEX_CAPABILITY_SECRET")
    os.environ["KEX_REQUIRE_SCOPED_CAPABILITIES"] = "true"
    os.environ["KEX_CAPABILITY_SECRET"] = secret

    try:
        source_cap = mint_capability(secret, actions=["SOURCE_INGEST"], target_prefixes=["KEX_"], ttl_seconds=300, delegated_by="capability-fabric")
        casepath_cap = mint_capability(secret, actions=["CASEPATH_DISPATCH"], target_prefixes=["casepath"], ttl_seconds=300, delegated_by="capability-fabric")
        proof_cap = mint_capability(secret, actions=["PROOF_LEDGER_WRITE"], target_prefixes=["BRAINK_"], ttl_seconds=300, delegated_by="capability-fabric")

        source_request = {
            "authority": AUTHORITY,
            "actionType": "SOURCE_INGEST",
            "target": "KEX_RUNTIME_MODEL",
            "idempotencyKey": f"FABRIC-{run_id}-SOURCE",
            "capability": source_cap,
            "payload": {"sourceText": json.dumps({"runId": run_id, "purpose": "integrated capability exercise", "ts": started}, sort_keys=True), "sourceFormat": "json"},
        }
        source_first = execute_action(source_request)
        source_replay = execute_action(source_request)
        source_replay_exact = source_first.get("receiptHash") == source_replay.get("receiptHash")

        dispatch_request = {
            "authority": AUTHORITY,
            "actionType": "CASEPATH_DISPATCH",
            "target": "casepath.com.au",
            "idempotencyKey": f"FABRIC-{run_id}-CASEPATH",
            "capability": casepath_cap,
            "payload": {
                "packetId": f"FABRIC-{run_id}",
                "processId": "CASEPATH-PROC-001",
                "proofTarget": "BRAINK_ACTION_LEDGER",
                "actionQueue": [{"id": "FABRIC-ACTION-001", "action": "exerciseManagedDispatch", "sourceObjectId": source_first.get("details", {}).get("objectId")}],
            },
        }
        dispatch = execute_action(dispatch_request)

        workbook = _make_workbook(run_id)
        semantics = write_semantic_index(workbook)
        semantic_payload = json.loads(Path(semantics["sidecar"]).read_text(encoding="utf-8"))

        outbox_key = f"FABRIC-{run_id}-TL2"
        outbox = OUTBOX.stage(
            action_class="TL2_DEPLOY",
            target="runtime://kex/wbos",
            payload={"transport": "tlvpn://kex/tl2", "service": "service://wbos/action-server", "source": "source://github/BRAINK/modules/kex_wbos/action_server.py"},
            idempotency_key=outbox_key,
        )

        tl2_result: dict[str, Any] = {"state": "NOT_REQUESTED", "promotion": None}
        if engage_tl2:
            proc = subprocess.run(
                [sys.executable, str(BASE / "deploy" / "tl2_deploy.py"), "--daemon"],
                cwd=BASE,
                capture_output=True,
                text=True,
                timeout=90,
                shell=False,
            )
            participant = _read_tl2_receipt()
            verified_live = (
                proc.returncode == 0
                and participant.get("status") == "VERIFIED"
                and participant.get("promotion") == "TL2_LIVE"
                and participant.get("supervision", {}).get("currentGenerationOwned") is True
                and participant.get("supervision", {}).get("aliveAfterReadback") is True
            )
            tl2_result = {
                "state": "EXECUTED",
                "returnCode": proc.returncode,
                "stdout": proc.stdout[-8000:],
                "stderr": proc.stderr[-4000:],
                "promotion": "TL2_LIVE" if verified_live else None,
                "participantReceipt": participant,
                "residentAfterReadback": verified_live,
            }
            if verified_live:
                OUTBOX.mark_delivered(outbox_key, tl2_result)
            else:
                OUTBOX.mark_attempt(outbox_key, f"tl2_not_verified_resident_rc_{proc.returncode}")

        proof_request = {
            "authority": AUTHORITY,
            "actionType": "PROOF_LEDGER_WRITE",
            "target": "BRAINK_CAPABILITY_FABRIC_LEDGER",
            "idempotencyKey": f"FABRIC-{run_id}-PROOF",
            "capability": proof_cap,
            "payload": {
                "eventType": "CAPABILITY_FABRIC_EXERCISE",
                "runId": run_id,
                "sourceReceiptHash": source_first.get("receiptHash"),
                "dispatchReceiptHash": dispatch.get("receiptHash"),
                "workbookGraphHash": semantics.get("graphHash"),
                "cycleCount": semantics.get("cycleCount"),
                "outboxId": outbox.get("item", {}).get("outboxId"),
                "tl2Promotion": tl2_result.get("promotion"),
            },
        }
        proof = execute_action(proof_request)
        checkpoint = checkpoint_ledger(ACTION_LEDGER, BASE / "runtime" / "checkpoints")

        checks = {
            "sourceMutated": _status(source_first) == "MUTATED",
            "idempotentReplayExact": source_replay_exact,
            "casepathManagedDispatchMutated": _status(dispatch) == "MUTATED",
            "contentAddressPresent": bool(source_first.get("details", {}).get("objectId")),
            "workbookGraphProduced": bool(semantics.get("graphHash")),
            "workbookCycleDetected": int(semantics.get("cycleCount", 0)) >= 1,
            "externalIntentDurablyStaged": outbox.get("state") in {"PENDING", "DELIVERED"},
            "proofWritten": _status(proof) == "MUTATED",
            "ledgerCheckpointRetained": bool(checkpoint.get("checkpointHash")),
        }
        local_clean = all(checks.values())

        REPORT_ROOT.mkdir(parents=True, exist_ok=True)
        report_path = REPORT_ROOT / f"{run_id}.json"
        report = {
            "recordId": "KEX_CAPABILITY_FABRIC_EXERCISE_R2",
            "runId": run_id,
            "status": "LOCAL_CAPABILITY_FABRIC_VERIFIED" if local_clean else "LOCAL_CAPABILITY_FABRIC_DEFECT",
            "startedAt": started,
            "finishedAt": time.time(),
            "reportPath": report_path.relative_to(BASE).as_posix(),
            "checks": checks,
            "receipts": {"source": source_first, "sourceReplay": source_replay, "casepathDispatch": dispatch, "proof": proof},
            "workbook": {"path": workbook.relative_to(BASE).as_posix(), "semanticIndex": semantics, "cycleComponents": semantic_payload.get("cycles", [])},
            "outbox": outbox,
            "tl2": tl2_result,
            "ledgerCheckpoint": checkpoint,
            "capabilitiesExercised": ["scoped signed authority", "idempotent command replay", "content-addressed source identity", "managed Casepath dispatch", "workbook formula dependency graph", "dependency cycle detection", "durable external action outbox", "proof-ledger mutation", "retained ledger-head checkpoint", "resident TL2 generation verification"],
            "claimBoundaries": ["local fabric verification is not TL2_LIVE", "pending outbox intent is not external execution", "formula graph analysis is not workbook formula or macro execution", "idempotency suppresses duplicate local commands but is not distributed exactly-once execution", "TL2 delivery requires a resident current-generation participant receipt"],
        }
        unsigned = dict(report)
        report["reportHash"] = sha256_bytes(canonical_json_bytes(unsigned))
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        persisted = json.loads(report_path.read_text(encoding="utf-8"))
        if persisted != report:
            raise RuntimeError("capability fabric report persistence divergence")
        return persisted
    finally:
        if prior_require is None:
            os.environ.pop("KEX_REQUIRE_SCOPED_CAPABILITIES", None)
        else:
            os.environ["KEX_REQUIRE_SCOPED_CAPABILITIES"] = prior_require
        if prior_secret is None:
            os.environ.pop("KEX_CAPABILITY_SECRET", None)
        else:
            os.environ["KEX_CAPABILITY_SECRET"] = prior_secret
