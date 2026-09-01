#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from casepath_management import managed_dispatch
from hardening import append_jsonl_fsync, atomic_write_text, contained_path

BASE = Path(__file__).resolve().parents[2]
RUNTIME = BASE / "runtime"
ACTION_LEDGER = BASE / "reports" / "kex-wbos" / "action-ledger.jsonl"
SOURCE_ROOT = RUNTIME / "sources"
DISPATCH_ROOT = RUNTIME / "casepath-dispatch"
PROOF_ROOT = BASE / "reports" / "kex-wbos"

EXTERNAL_ACTIONS = {
    "PUBLIC_DNS": "DNS_PROVIDER_ADAPTER",
    "PUBLIC_TLS": "ACME_OR_TLS_ADAPTER",
    "ROUTER_FIREWALL": "ROUTER_ADMIN_ADAPTER",
    "BITCOIN_LIVE_SUBMISSION": "BITCOIN_RPC_ADAPTER",
    "DRIVE_WRITEBACK": "GOOGLE_DRIVE_ADAPTER",
    "LIVE_PUBLIC_DEPLOYMENT": "DEPLOYMENT_ADAPTER",
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _receipt(action_id: str, status: str, mutated: bool, target: str, *, before: str | None = None, after: str | None = None, external_readback: bool = False, details: dict[str, Any] | None = None) -> dict[str, Any]:
    receipt = {
        "status": status,
        "actionId": action_id,
        "mutated": mutated,
        "target": target,
        "receiptId": f"KEXR-{uuid.uuid4().hex[:16]}",
        "beforeHash": before,
        "afterHash": after,
        "proofLedgerRow": None,
        "externalReadback": external_readback,
        "timestamp": _now(),
        "details": details or {},
    }
    receipt["proofLedgerRow"] = append_jsonl_fsync(ACTION_LEDGER, receipt)
    return receipt


def execute_action(request: dict[str, Any]) -> dict[str, Any]:
    action_type = str(request.get("actionType", "")).upper()
    target = str(request.get("target", ""))
    action_id = f"ACT-{uuid.uuid4().hex[:12]}"
    if not request.get("authority"):
        return _receipt(action_id, "FAIL", False, target, details={"error": "authority_required"})
    if not action_type or not target:
        return _receipt(action_id, "FAIL", False, target, details={"error": "actionType_and_target_required"})
    if action_type in EXTERNAL_ACTIONS:
        adapter = request.get("controlRoute") or os.getenv(f"KEX_{EXTERNAL_ACTIONS[action_type]}")
        if not adapter:
            return _receipt(action_id, "BLOCKED", False, target, details={"requiredAdapter": EXTERNAL_ACTIONS[action_type], "claimBoundary": "External mutation is not claimed without a bound actuator and receipt."})
    if action_type == "SOURCE_INGEST":
        return ingest_source({"authority": request["authority"], "sourceText": request.get("payload", {}).get("sourceText", ""), "sourceFormat": request.get("payload", {}).get("sourceFormat", "markdown"), "target": target})
    if action_type == "CASEPATH_DISPATCH":
        payload = request.get("payload", {})
        return dispatch_casepath({
            "authority": request["authority"],
            "packetId": payload.get("packetId", action_id),
            "activeTarget": target,
            "processId": payload.get("processId", "CASEPATH-PROC-001"),
            "actionQueue": payload.get("actionQueue", []),
            "proofTarget": payload.get("proofTarget"),
        })
    if action_type == "PROOF_LEDGER_WRITE":
        return write_proof({"authority": request["authority"], "eventType": request.get("payload", {}).get("eventType", action_type), "payload": request.get("payload", {}), "targetLedger": target})
    return _receipt(action_id, "ARMED", False, target, details={"actionType": action_type, "controlRoute": request.get("controlRoute"), "claimBoundary": "Action class is resident but no local executor was selected for this request."})


def ingest_source(request: dict[str, Any]) -> dict[str, Any]:
    action_id = f"SRC-{uuid.uuid4().hex[:12]}"
    text = request.get("sourceText")
    target = str(request.get("target", "KEX_RUNTIME_MODEL"))
    if not isinstance(text, str) or not text:
        return _receipt(action_id, "FAIL", False, target, details={"error": "sourceText_required"})
    SOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    ext = {"markdown": "md", "json": "json", "html": "html", "text": "txt"}.get(request.get("sourceFormat"), "txt")
    path = contained_path(SOURCE_ROOT, SOURCE_ROOT / f"{action_id}.{ext}")
    before = _sha(path.read_bytes()) if path.exists() else None
    atomic_write_text(path, text)
    after = _sha(path.read_bytes())
    return _receipt(action_id, "MUTATED", True, target, before=before, after=after, details={"path": path.relative_to(BASE).as_posix(), "bytes": path.stat().st_size})


def dispatch_casepath(request: dict[str, Any]) -> dict[str, Any]:
    action_id = f"DSP-{uuid.uuid4().hex[:12]}"
    return managed_dispatch(
        base=BASE,
        dispatch_root=DISPATCH_ROOT,
        request=request,
        receipt=_receipt,
        now=_now,
        sha=_sha,
        action_id=action_id,
    )


def write_proof(request: dict[str, Any]) -> dict[str, Any]:
    action_id = f"PRF-{uuid.uuid4().hex[:12]}"
    event = {"ts": time.time(), "authority": request.get("authority"), "eventType": request.get("eventType"), "payload": request.get("payload", {}), "targetLedger": request.get("targetLedger", "KEX_ACTION_LEDGER")}
    path = PROOF_ROOT / "action-proof-ledger.jsonl"
    before = _sha(path.read_bytes()) if path.exists() else None
    row = append_jsonl_fsync(path, event)
    after = _sha(path.read_bytes())
    return _receipt(action_id, "MUTATED", True, str(event["targetLedger"]), before=before, after=after, details={"event": event, "proofEventRow": row})


def readback_runtime(request: dict[str, Any]) -> dict[str, Any]:
    target = str(request.get("target", ""))
    expected_text = request.get("expectedText")
    if target.startswith("http://") or target.startswith("https://"):
        try:
            with urllib.request.urlopen(target, timeout=10) as response:
                body = response.read()
                text = body.decode("utf-8", errors="replace")
                matched = response.status < 400 and (expected_text is None or expected_text in text)
                return {"status": "VERIFIED" if matched else "FAIL", "target": target, "matched": matched, "observedState": f"HTTP_{response.status}", "proofHash": _sha(body)}
        except Exception as exc:
            return {"status": "FAIL", "target": target, "matched": False, "observedState": type(exc).__name__, "proofHash": None}

    candidate = Path(target)
    if not candidate.is_absolute():
        candidate = BASE / candidate
    try:
        path = contained_path(BASE, candidate)
    except ValueError:
        return {"status": "FAIL", "target": target, "matched": False, "observedState": "PATH_OUTSIDE_RUNTIME_ROOT", "proofHash": None}
    if path.exists() and path.is_file():
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        matched = expected_text is None or expected_text in text
        return {"status": "VERIFIED" if matched else "FAIL", "target": target, "matched": matched, "observedState": "FILE_PRESENT", "proofHash": _sha(raw)}
    return {"status": "FAIL", "target": target, "matched": False, "observedState": "NOT_FOUND", "proofHash": None}


def launch_runtime(request: dict[str, Any]) -> dict[str, Any]:
    action_id = f"RUN-{uuid.uuid4().hex[:12]}"
    runtime_id = str(request.get("runtimeId", ""))
    route = str(request.get("commandRoute", ""))
    if not runtime_id or not route:
        return _receipt(action_id, "FAIL", False, runtime_id, details={"error": "runtimeId_and_commandRoute_required"})
    allowed = {
        "kex-wbos-self-test": [os.sys.executable, str(BASE / "scripts" / "kex-ci" / "test_wbos_api.py")],
    }
    command = allowed.get(route)
    if not command:
        return _receipt(action_id, "BLOCKED", False, runtime_id, details={"error": "commandRoute_not_bound", "allowedRoutes": sorted(allowed)})
    proc = subprocess.run(command, cwd=BASE, capture_output=True, text=True, timeout=120, shell=False)
    output = (proc.stdout + "\n" + proc.stderr).encode()
    return _receipt(action_id, "VERIFIED" if proc.returncode == 0 else "FAIL", False, runtime_id, after=_sha(output), details={"returnCode": proc.returncode, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:]})


def read_workbook_table(workbook_id: str, table_id: str) -> tuple[int, dict[str, Any]]:
    roots = [BASE / "workbooks", BASE / "runtime" / "workbooks"]
    candidates: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        candidates.extend(p for p in root.rglob("*.xlsx") if p.stem == workbook_id or p.name == workbook_id)
        candidates.extend(p for p in root.rglob("*.xlsm") if p.stem == workbook_id or p.name == workbook_id)
    if not candidates:
        return 404, {"error": "workbook_not_found", "workbookId": workbook_id, "tableId": table_id}
    workbook = contained_path(BASE, candidates[0])
    wb = load_workbook(workbook, data_only=False, read_only=True)
    if table_id not in wb.sheetnames:
        return 404, {"error": "table_not_found", "workbookId": workbook_id, "tableId": table_id}
    ws = wb[table_id]
    values = list(ws.iter_rows(values_only=True))
    if not values:
        rows: list[dict[str, Any]] = []
    else:
        headers = [str(v) if v is not None else f"column_{i+1}" for i, v in enumerate(values[0])]
        rows = [{headers[i]: row[i] if i < len(row) else None for i in range(len(headers))} for row in values[1:] if any(v is not None for v in row)]
    return 200, {"workbookId": workbook_id, "tableId": table_id, "rowCount": len(rows), "rows": rows}
