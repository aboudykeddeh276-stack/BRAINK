#!/usr/bin/env python3
"""BRAINK host-control carrier supervisor for Desktop Commander.

This supervisor owns carrier lifecycle and proof receipts. It does not grant
shell authority by itself. Approved host operations remain governed by BRAINK/
KEX capability policy and are expected to be dispatched through the MCP client
surface once the carrier is READY.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path(os.getenv("BRAINK_HOST_CONTROL_STATE", Path.home() / ".braink" / "host-control"))
STATE_FILE = STATE_DIR / "desktop-commander-state.json"
RECEIPT_FILE = STATE_DIR / "desktop-commander-receipts.jsonl"
REMOTE_COMMAND = ["npx", "-y", "@wonderwhy-er/desktop-commander@latest", "remote"]
LOCAL_MCP_COMMAND = ["npx", "-y", "@wonderwhy-er/desktop-commander@latest"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(obj: object) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def receipt(event: str, **fields: object) -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    record = {"timestamp_utc": utc_now(), "event": event, **fields}
    record["proof_root"] = digest(record)
    with RECEIPT_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")
    return record


def write_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = dict(state)
    state["updated_at"] = utc_now()
    state["state_root"] = digest(state)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(STATE_FILE)


def check_prerequisites() -> dict:
    checks = {}
    for name in ("node", "npm", "npx"):
        result = subprocess.run(["/usr/bin/env", "sh", "-lc", f"command -v {name}"], capture_output=True, text=True)
        checks[name] = result.stdout.strip() if result.returncode == 0 else None
    checks["ready"] = all(checks[x] for x in ("node", "npm", "npx"))
    return checks


def command_for(mode: str) -> list[str]:
    if mode == "remote":
        return REMOTE_COMMAND
    if mode == "mcp":
        return LOCAL_MCP_COMMAND
    raise ValueError("unsupported mode")


def supervise(mode: str, restart_delay: float = 2.0) -> int:
    prereq = check_prerequisites()
    if not prereq["ready"]:
        write_state({"status": "BLOCKED", "reason": "NODE_NPM_NPX_REQUIRED", "prerequisites": prereq})
        print(json.dumps(receipt("HOST_CONTROL_BLOCKED", prerequisites=prereq)))
        return 2

    stop = False
    child: subprocess.Popen[str] | None = None

    def handle_stop(*_: object) -> None:
        nonlocal stop
        stop = True
        if child and child.poll() is None:
            child.terminate()

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)
    cmd = command_for(mode)

    while not stop:
        started = time.monotonic()
        write_state({"status": "STARTING", "mode": mode, "command": cmd, "pid": None})
        receipt("HOST_CONTROL_STARTING", mode=mode, command=cmd)
        try:
            child = subprocess.Popen(cmd, text=True)
        except Exception as exc:
            write_state({"status": "FAILED", "mode": mode, "error": type(exc).__name__, "detail": str(exc)[:240]})
            receipt("HOST_CONTROL_LAUNCH_FAILED", mode=mode, error=type(exc).__name__, detail=str(exc)[:240])
            if stop:
                break
            time.sleep(restart_delay)
            continue

        write_state({"status": "RUNNING", "mode": mode, "command": cmd, "pid": child.pid, "started_at": utc_now()})
        receipt("HOST_CONTROL_RUNNING", mode=mode, pid=child.pid)

        while not stop and child.poll() is None:
            write_state({
                "status": "RUNNING",
                "mode": mode,
                "command": cmd,
                "pid": child.pid,
                "uptime_seconds": round(time.monotonic() - started, 3),
            })
            receipt("HOST_CONTROL_HEARTBEAT", mode=mode, pid=child.pid, uptime_seconds=round(time.monotonic() - started, 3))
            time.sleep(10)

        code = child.poll()
        receipt("HOST_CONTROL_EXIT", mode=mode, pid=child.pid, returncode=code)
        if stop:
            break
        write_state({"status": "RESTARTING", "mode": mode, "last_returncode": code})
        time.sleep(restart_delay)

    write_state({"status": "STOPPED", "mode": mode})
    receipt("HOST_CONTROL_STOPPED", mode=mode)
    return 0


def status() -> int:
    if not STATE_FILE.exists():
        print(json.dumps({"status": "UNOBSERVED", "state_file": str(STATE_FILE)}, indent=2))
        return 1
    print(STATE_FILE.read_text(encoding="utf-8"), end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--mode", choices=["remote", "mcp"], default="remote")
    sub.add_parser("status")
    sub.add_parser("self-test")
    args = parser.parse_args()

    if args.command == "run":
        return supervise(args.mode)
    if args.command == "status":
        return status()
    checks = check_prerequisites()
    print(json.dumps({"self_test": "PASS" if checks["ready"] else "BLOCKED", "prerequisites": checks}, indent=2))
    return 0 if checks["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
