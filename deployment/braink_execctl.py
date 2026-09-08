#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise.orchestration.resident_execution_fabric import ResidentExecutionFabric


def key_from_env() -> bytes:
    raw = os.environ.get("BRAINK_EXECUTION_HMAC_KEY_HEX", "").strip()
    if not raw:
        raise SystemExit("BRAINK_EXECUTION_HMAC_KEY_HEX is required for signed dispatch")
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise SystemExit("BRAINK_EXECUTION_HMAC_KEY_HEX must be hexadecimal") from exc
    if len(key) < 32:
        raise SystemExit("execution key must be at least 32 bytes")
    return key


def call(socket_path: str, payload: dict) -> dict:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(30)
    s.connect(socket_path)
    try:
        s.sendall(json.dumps(payload, separators=(",", ":")).encode() + b"\n")
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        if not buf:
            raise RuntimeError("empty execution-service response")
        return json.loads(buf)
    finally:
        s.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="BRAINK resident execution control")
    ap.add_argument("--socket", default=os.environ.get("BRAINK_EXECUTION_SOCKET", "/run/braink/execution.sock"))
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("health")
    rb = sub.add_parser("readback"); rb.add_argument("work_id")
    dispatch = sub.add_parser("dispatch")
    dispatch.add_argument("route")
    dispatch.add_argument("operation", choices=["DESCRIBE_ROUTE", "RUN_ONCE", "START_RUNTIME", "STOP_RUNTIME", "RESTART_RUNTIME", "READBACK_RUNTIME"])
    dispatch.add_argument("--work-id")
    dispatch.add_argument("--actor-type", default="ADMINISTRATOR")
    dispatch.add_argument("--actor-id", default=os.environ.get("USER", "local"))
    args = ap.parse_args()

    if args.command == "health":
        result = call(args.socket, {"op": "HEALTH"})
    elif args.command == "readback":
        result = call(args.socket, {"op": "READBACK", "work_id": args.work_id})
    else:
        work_id = args.work_id or f"local-{int(time.time_ns())}"
        # Instantiate only the authority/signing mechanics locally; execution remains in the service.
        signer = ResidentExecutionFabric(ROOT, os.environ.get("BRAINK_EXECUTION_SIGNER_STATE", "/var/lib/braink/resident-execution"), key_from_env())
        envelope = signer.sign({
            "work_id": work_id,
            "correlation_id": work_id,
            "actor": {"type": args.actor_type, "id": args.actor_id},
            "sector": "runtime",
            "route": args.route,
            "operation": args.operation,
            "continuation": {"epoch": 1, "status": "ADMITTED"},
            "carrier": "cli://braink-execctl",
            "proof_required": True,
        })
        result = call(args.socket, {"op": "DISPATCH", "envelope": envelope})
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") in {"PASS", "COMPLETED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
