#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("BRAINK_ROOT") or Path(__file__).resolve().parents[1]).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.runtime_registry import RuntimeRegistry
from runtime.signal_node.node import Signal, SignalKind, SignalNode

DATA_DIR = Path(os.environ.get("BRAINK_DATA_DIR", ROOT / ".kex" / "state" / "direct-saas" / "saas-data")).resolve()
SAAS_DB = DATA_DIR / "saas_node.sqlite3"
RUNTIME_DB = Path(os.environ.get("BRAINK_RUNTIME_DB", ROOT / ".kex" / "state" / "host_fabric" / "runtimes.sqlite")).resolve()
WORKER_ID = os.environ.get("BRAINK_SAAS_WORKER_ID", f"saas-worker:{socket.gethostname()}:{os.getpid()}")
AUTHORITY = os.environ.get("BRAINK_SAAS_PROVISION_AUTHORITY", "kex://authority/saas-provisioning")
POLL_SEC = float(os.environ.get("BRAINK_SAAS_PROVISION_POLL_SEC", "1.0"))
HEALTH_TIMEOUT = float(os.environ.get("BRAINK_SAAS_HEALTH_TIMEOUT_SEC", "10"))
ALLOWED_ROOTS = [
    Path(x).expanduser().resolve()
    for x in os.environ.get("BRAINK_EXEC_ALLOWED_ROOTS", f"{ROOT}:/opt/keddeh:/usr/local/libexec").split(":")
    if x.strip()
]


def canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def sha(value: Any) -> str:
    return hashlib.sha256(canon(value)).hexdigest()


def db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(SAAS_DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    return con


def init_db() -> None:
    with db() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS provisioning_transitions (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                intent_id TEXT NOT NULL,
                from_status TEXT,
                to_status TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                receipt_hash TEXT,
                detail_json TEXT NOT NULL,
                created_ns INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_provisioning_transitions_intent
              ON provisioning_transitions(intent_id, seq);
            """
        )


def transition(intent_id: str, from_status: str | None, to_status: str, detail: dict[str, Any], receipt_hash: str | None = None) -> None:
    with db() as con:
        if from_status is not None:
            cur = con.execute(
                "UPDATE provisioning_intents SET status=? WHERE intent_id=? AND status=?",
                (to_status, intent_id, from_status),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"PROVISION_STATUS_CONFLICT:{intent_id}:{from_status}->{to_status}")
        else:
            con.execute("UPDATE provisioning_intents SET status=? WHERE intent_id=?", (to_status, intent_id))
        con.execute(
            """INSERT INTO provisioning_transitions(intent_id,from_status,to_status,worker_id,receipt_hash,detail_json,created_ns)
               VALUES(?,?,?,?,?,?,?)""",
            (intent_id, from_status, to_status, WORKER_ID, receipt_hash, json.dumps(detail, sort_keys=True), time.time_ns()),
        )


def claim_next() -> dict[str, Any] | None:
    con = db()
    try:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT * FROM provisioning_intents WHERE status='PENDING_ACTUATION' ORDER BY created_at, intent_id LIMIT 1"
        ).fetchone()
        if not row:
            con.commit()
            return None
        cur = con.execute(
            "UPDATE provisioning_intents SET status='ACTUATING' WHERE intent_id=? AND status='PENDING_ACTUATION'",
            (row["intent_id"],),
        )
        if cur.rowcount != 1:
            con.rollback()
            return None
        detail = {"worker_id": WORKER_ID, "claimed_ns": time.time_ns()}
        con.execute(
            """INSERT INTO provisioning_transitions(intent_id,from_status,to_status,worker_id,receipt_hash,detail_json,created_ns)
               VALUES(?,?,?,?,?,?,?)""",
            (row["intent_id"], "PENDING_ACTUATION", "ACTUATING", WORKER_ID, None, json.dumps(detail, sort_keys=True), time.time_ns()),
        )
        con.commit()
        out = dict(row)
        out["status"] = "ACTUATING"
        out["payload"] = json.loads(out["payload_json"])
        return out
    finally:
        con.close()


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def allowed_command(path: Path) -> bool:
    resolved = path.expanduser().resolve()
    return any(resolved == root or root in resolved.parents for root in ALLOWED_ROOTS)


def health_readback(endpoint: str | None, pid: int) -> dict[str, Any]:
    if not endpoint:
        time.sleep(0.25)
        return {
            "status": "STARTED_UNVERIFIED" if pid_alive(pid) else "FAILED",
            "reason": "HEALTH_ENDPOINT_UNBOUND" if pid_alive(pid) else "PROCESS_EXITED",
            "pid": pid,
        }
    deadline = time.time() + HEALTH_TIMEOUT
    last_error = "UNOBSERVED"
    while time.time() < deadline:
        if not pid_alive(pid):
            return {"status": "FAILED", "reason": "PROCESS_EXITED", "pid": pid}
        try:
            with urllib.request.urlopen(endpoint, timeout=2) as response:
                raw = response.read(65536)
                if 200 <= response.status < 300:
                    return {
                        "status": "VERIFIED",
                        "pid": pid,
                        "health_endpoint": endpoint,
                        "http_status": response.status,
                        "body_hash": hashlib.sha256(raw).hexdigest(),
                    }
                last_error = f"HTTP_{response.status}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}:{exc}"
        time.sleep(0.2)
    return {"status": "FAILED", "reason": "HEALTH_READBACK_TIMEOUT", "last_error": last_error, "pid": pid}


def runtime_actuator(registry: RuntimeRegistry, runtime_id: str):
    def actuate(signal: Signal) -> dict[str, Any]:
        row = registry.get(runtime_id)
        if not row:
            return {"status": "BLOCKED", "reason": "RUNTIME_NOT_REGISTERED", "runtime_id": runtime_id}
        spec = registry.inflate(row)
        current_pid = spec.get("pid")
        if pid_alive(current_pid):
            readback = health_readback(spec.get("health_endpoint"), int(current_pid))
            registry.observe(runtime_id, desired_state="RUNNING", observed_state="RUNNING" if readback["status"] == "VERIFIED" else "STARTED_UNVERIFIED", last_readback=readback)
            return {"status": readback["status"], "runtime_id": runtime_id, "idempotent": True, "readback": readback}

        command = Path(str(spec.get("command_route") or ""))
        argv = spec.get("argv") or []
        if not command.is_file() or not allowed_command(command):
            return {"status": "BLOCKED", "reason": "COMMAND_ROUTE_NOT_ALLOWED", "runtime_id": runtime_id, "command_route": str(command)}
        if not isinstance(argv, list) or any(not isinstance(v, (str, int, float)) for v in argv):
            return {"status": "BLOCKED", "reason": "ARGV_INVALID", "runtime_id": runtime_id}

        proc = subprocess.Popen(
            [str(command), *[str(v) for v in argv]],
            cwd=str(ROOT),
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        readback = health_readback(spec.get("health_endpoint"), proc.pid)
        observed_state = "RUNNING" if readback["status"] == "VERIFIED" else ("STARTED_UNVERIFIED" if readback["status"] == "STARTED_UNVERIFIED" else "FAILED")
        registry.observe(
            runtime_id,
            pid=proc.pid if pid_alive(proc.pid) else None,
            desired_state="RUNNING",
            observed_state=observed_state,
            last_readback=readback,
            last_failure=None if observed_state != "FAILED" else json.dumps(readback, sort_keys=True),
        )
        return {"status": readback["status"], "runtime_id": runtime_id, "pid": proc.pid, "readback": readback}
    return actuate


def process_intent(intent: dict[str, Any]) -> dict[str, Any]:
    payload = intent["payload"]
    route = payload.get("route") or {}
    runtime_id = str(route.get("runtime_uri") or "").strip()
    if not runtime_id:
        detail = {"status": "BLOCKED", "reason": "RUNTIME_URI_UNBOUND"}
        transition(intent["intent_id"], "ACTUATING", "BLOCKED", detail)
        return detail

    registry = RuntimeRegistry(RUNTIME_DB)
    node = SignalNode(authority_check=lambda s: s.authority == AUTHORITY)
    node.register(runtime_id, runtime_actuator(registry, runtime_id))
    signal = Signal(
        kind=SignalKind.TRIGGER,
        target=runtime_id,
        opcode="PROVISION",
        payload={
            "intent_id": intent["intent_id"],
            "tenant_id": intent["tenant_id"],
            "system_id": intent["system_id"],
            "service_id": intent["service_id"],
            "plan": intent["plan"],
        },
        authority=AUTHORITY,
        correlation_id=intent["intent_id"],
    )
    receipt = node.dispatch(signal)
    receipt_body = {
        "signal_id": receipt.signal_id,
        "target": receipt.target,
        "kind": receipt.kind,
        "opcode": receipt.opcode,
        "status": receipt.status,
        "observed": dict(receipt.observed),
        "previous_receipt_hash": receipt.previous_receipt_hash,
        "timestamp_ns": receipt.timestamp_ns,
        "receipt_hash": receipt.receipt_hash,
    }
    observed_status = str(receipt.observed.get("status") or "")
    if receipt.status != "EXECUTED":
        final = "BLOCKED"
    elif observed_status == "VERIFIED":
        final = "VERIFIED"
    elif observed_status == "STARTED_UNVERIFIED":
        final = "ACTUATED_UNVERIFIED"
    else:
        final = "BLOCKED"
    transition(intent["intent_id"], "ACTUATING", final, receipt_body, receipt.receipt_hash)
    return {"intent_id": intent["intent_id"], "status": final, "receipt": receipt_body}


def run_once() -> dict[str, Any]:
    init_db()
    intent = claim_next()
    if not intent:
        return {"status": "IDLE", "worker_id": WORKER_ID}
    try:
        return process_intent(intent)
    except Exception as exc:
        detail = {"status": "BLOCKED", "reason": f"{type(exc).__name__}:{exc}"}
        try:
            transition(intent["intent_id"], "ACTUATING", "BLOCKED", detail)
        except Exception:
            pass
        return {"intent_id": intent["intent_id"], **detail}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.once:
        print(json.dumps(run_once(), sort_keys=True, indent=2))
        return 0
    init_db()
    while True:
        result = run_once()
        if result.get("status") != "IDLE":
            print(json.dumps(result, sort_keys=True), flush=True)
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
