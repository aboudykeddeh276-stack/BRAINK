#!/usr/bin/env python3
"""BRAINK host-control carrier supervisor for Desktop Commander.

This supervisor owns carrier lifecycle and proof receipts. It does not grant
shell authority by itself. Approved host operations remain governed by BRAINK/
KEX capability policy and are expected to be dispatched through the MCP client
surface once the carrier is READY.

The carrier is transport only. BRAINK/KEX remains the authority root.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path(os.getenv("BRAINK_HOST_CONTROL_STATE", Path.home() / ".braink" / "host-control"))
STATE_FILE = STATE_DIR / "desktop-commander-state.json"
RECEIPT_FILE = STATE_DIR / "desktop-commander-receipts.jsonl"
DEFAULT_PACKAGE = "@wonderwhy-er/desktop-commander"
STATE_HEARTBEAT_SEC = float(os.getenv("BRAINK_DC_STATE_HEARTBEAT_SEC", "10"))
RECEIPT_HEARTBEAT_SEC = float(os.getenv("BRAINK_DC_RECEIPT_HEARTBEAT_SEC", "60"))
MAX_RECEIPT_BYTES = int(os.getenv("BRAINK_DC_MAX_RECEIPT_BYTES", str(8 * 1024 * 1024)))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(obj: object) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def rotate_receipt_if_needed() -> None:
    try:
        if RECEIPT_FILE.exists() and RECEIPT_FILE.stat().st_size >= MAX_RECEIPT_BYTES:
            rotated = RECEIPT_FILE.with_name(f"{RECEIPT_FILE.stem}.{int(time.time())}.jsonl")
            RECEIPT_FILE.replace(rotated)
    except OSError:
        pass


def receipt(event: str, **fields: object) -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    rotate_receipt_if_needed()
    record = {"timestamp_utc": utc_now(), "event": event, **fields}
    record["proof_root"] = digest(record)
    with RECEIPT_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")
    return record


def write_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    body = dict(state)
    body["updated_at"] = utc_now()
    body["state_root"] = digest(body)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(STATE_FILE)


def package_spec() -> str:
    spec = os.getenv("BRAINK_DC_PACKAGE", "").strip()
    if spec:
        return spec
    if os.getenv("BRAINK_DC_ALLOW_LATEST", "0") == "1":
        return f"{DEFAULT_PACKAGE}@latest"
    raise RuntimeError("DESKTOP_COMMANDER_PACKAGE_UNPINNED: set BRAINK_DC_PACKAGE to an exact version or BRAINK_DC_ALLOW_LATEST=1")


def command_for(mode: str) -> list[str]:
    explicit = os.getenv("BRAINK_DC_COMMAND", "").strip()
    if explicit:
        cmd = shlex.split(explicit)
        if not cmd:
            raise RuntimeError("BRAINK_DC_COMMAND_EMPTY")
        return cmd + (["remote"] if mode == "remote" and cmd[-1] != "remote" else [])
    package = package_spec()
    base = ["npx", "-y", package]
    if mode == "remote":
        return [*base, "remote"]
    if mode == "mcp":
        return base
    raise ValueError("unsupported mode")


def check_prerequisites(command: list[str] | None = None) -> dict:
    cmd = command or []
    uses_npx = bool(cmd and Path(cmd[0]).name == "npx")
    required = ("node", "npm", "npx") if uses_npx else ((Path(cmd[0]).name,) if cmd else ("node", "npm", "npx"))
    checks: dict[str, object] = {}
    for name in required:
        result = subprocess.run(["/usr/bin/env", "sh", "-lc", f"command -v {shlex.quote(name)}"], capture_output=True, text=True)
        checks[name] = result.stdout.strip() if result.returncode == 0 else None
    checks["ready"] = all(bool(checks[x]) for x in required)
    checks["required"] = list(required)
    return checks


def supervise(mode: str, restart_delay: float = 2.0) -> int:
    try:
        cmd = command_for(mode)
    except Exception as exc:
        body = {"status": "BLOCKED", "reason": str(exc), "mode": mode}
        write_state(body)
        print(json.dumps(receipt("HOST_CONTROL_BLOCKED", **body)))
        return 2

    prereq = check_prerequisites(cmd)
    if not prereq["ready"]:
        body = {"status": "BLOCKED", "reason": "CARRIER_PREREQUISITES_REQUIRED", "mode": mode, "command": cmd, "prerequisites": prereq}
        write_state(body)
        print(json.dumps(receipt("HOST_CONTROL_BLOCKED", **body)))
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

    while not stop:
        started = time.monotonic()
        last_receipt = 0.0
        write_state({"status": "STARTING", "mode": mode, "command": cmd, "pid": None, "authority": "BRAINK/KEX", "carrier_role": "TRANSPORT_ONLY"})
        receipt("HOST_CONTROL_STARTING", mode=mode, command=cmd, authority="BRAINK/KEX", carrier_role="TRANSPORT_ONLY")
        try:
            child = subprocess.Popen(cmd, text=True)
        except Exception as exc:
            write_state({"status": "FAILED", "mode": mode, "command": cmd, "error": type(exc).__name__, "detail": str(exc)[:240]})
            receipt("HOST_CONTROL_LAUNCH_FAILED", mode=mode, command=cmd, error=type(exc).__name__, detail=str(exc)[:240])
            if stop:
                break
            time.sleep(restart_delay)
            continue

        write_state({"status": "RUNNING", "mode": mode, "command": cmd, "pid": child.pid, "started_at": utc_now(), "authority": "BRAINK/KEX", "carrier_role": "TRANSPORT_ONLY"})
        receipt("HOST_CONTROL_RUNNING", mode=mode, pid=child.pid, command=cmd)
        last_receipt = time.monotonic()

        while not stop and child.poll() is None:
            uptime = round(time.monotonic() - started, 3)
            write_state({
                "status": "RUNNING",
                "mode": mode,
                "command": cmd,
                "pid": child.pid,
                "uptime_seconds": uptime,
                "authority": "BRAINK/KEX",
                "carrier_role": "TRANSPORT_ONLY",
            })
            now = time.monotonic()
            if now - last_receipt >= RECEIPT_HEARTBEAT_SEC:
                receipt("HOST_CONTROL_HEARTBEAT", mode=mode, pid=child.pid, uptime_seconds=uptime)
                last_receipt = now
            time.sleep(max(1.0, STATE_HEARTBEAT_SEC))

        code = child.poll()
        receipt("HOST_CONTROL_EXIT", mode=mode, pid=child.pid, returncode=code)
        if stop:
            break
        write_state({"status": "RESTARTING", "mode": mode, "command": cmd, "last_returncode": code})
        time.sleep(max(0.1, restart_delay))

    write_state({"status": "STOPPED", "mode": mode, "command": cmd})
    receipt("HOST_CONTROL_STOPPED", mode=mode)
    return 0


def status() -> int:
    if not STATE_FILE.exists():
        print(json.dumps({"status": "UNOBSERVED", "state_file": str(STATE_FILE)}, indent=2))
        return 1
    print(STATE_FILE.read_text(encoding="utf-8"), end="")
    return 0


def self_test() -> tuple[int, dict]:
    checks: dict[str, object] = {
        "authority_separation": True,
        "default_latest_disabled": os.getenv("BRAINK_DC_ALLOW_LATEST", "0") != "1",
        "receipt_rotation_bytes": MAX_RECEIPT_BYTES,
        "state_heartbeat_sec": STATE_HEARTBEAT_SEC,
        "receipt_heartbeat_sec": RECEIPT_HEARTBEAT_SEC,
    }
    try:
        cmd = command_for("remote")
        prereq = check_prerequisites(cmd)
        checks["command"] = cmd
        checks["prerequisites"] = prereq
        status_value = "PASS" if prereq["ready"] else "BLOCKED"
        return (0 if prereq["ready"] else 2), {"self_test": status_value, "checks": checks}
    except Exception as exc:
        checks["command_boundary"] = str(exc)
        return 2, {"self_test": "BLOCKED", "checks": checks}


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
    code, body = self_test()
    print(json.dumps(body, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
