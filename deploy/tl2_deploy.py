#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
MODULES = BASE / "modules" / "kex_wbos"
sys.path.insert(0, str(MODULES))
from hardening import append_jsonl_fsync, atomic_write_text

REPORT = BASE / "reports/kex-wbos/tl2-deployment.json"
PROOF = BASE / "reports/kex-wbos/tl2-proof-ledger.jsonl"
SUPERVISOR_STATE = BASE / "runtime/supervisor/wbos-action-server.json"
SOURCE_ID = "source://github/BRAINK/modules/kex_wbos/action_server.py"
SERVICE_ID = "service://wbos/action-server"
RUNTIME_ID = "runtime://kex/wbos"
TL2_ID = "tlvpn://kex/tl2"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _detect() -> tuple[str | None, str]:
    if os.getenv("KEX_TL2_ADDRESS"):
        return os.environ["KEX_TL2_ADDRESS"], "KEX_TL2_ADDRESS"
    try:
        interfaces = json.loads(subprocess.check_output(["ip", "-j", "addr"], text=True, stderr=subprocess.DEVNULL))
        for interface in interfaces:
            name = str(interface.get("ifname", "")).lower()
            if any(token in name for token in ("tl2", "tlvpn", "tailscale", "wg", "tun")):
                for address in interface.get("addr_info", []):
                    if address.get("family") == "inet" and address.get("local") and not str(address["local"]).startswith("127."):
                        return str(address["local"]), interface.get("ifname", "tunnel")
    except Exception:
        pass
    return None, "unresolved"


def _proof(event: str, payload: dict) -> None:
    append_jsonl_fsync(PROOF, {"ts": time.time(), "event": event, **payload})


def _write_report(payload: dict) -> None:
    unsigned = dict(payload)
    unsigned.pop("receiptHash", None)
    payload["receiptHash"] = _sha(json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    atomic_write_text(REPORT, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _wait(url: str, token: str, timeout: int = 20) -> dict:
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=3) as response:
                body = response.read()
                return {
                    "url": url,
                    "status": response.status,
                    "bytes": len(body),
                    "sha256": _sha(body),
                    "ok": response.status < 400,
                }
        except Exception as exc:
            last = type(exc).__name__
            time.sleep(0.25)
    return {"url": url, "status": None, "bytes": 0, "sha256": None, "ok": False, "error": last}


def _spawn_supervisor(host: str, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["RUNNER_TRACKING_ID"] = ""
    return subprocess.Popen(
        [
            sys.executable,
            str(MODULES / "service_supervisor.py"),
            "--host",
            host,
            "--port",
            str(port),
            "--max-restarts",
            "5",
            "--restart-window",
            "60",
        ],
        cwd=BASE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )


def _read_supervisor_state() -> dict:
    if not SUPERVISOR_STATE.exists():
        return {"observedState": "UNOBSERVED"}
    try:
        return json.loads(SUPERVISOR_STATE.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"observedState": "STATE_READ_FAILED", "error": type(exc).__name__}


def deploy(daemon: bool) -> int:
    host, source = _detect()
    token = os.getenv("KEX_BEARER_TOKEN", "")
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    if not host:
        result = {
            "status": "BLOCKED_TL2_ACTUATOR",
            "promotion": None,
            "identity": TL2_ID,
            "source_object": SOURCE_ID,
            "service": SERVICE_ID,
            "runtime": RUNTIME_ID,
            "reason": "No KEX_TL2_ADDRESS or observed TL2/tunnel interface address",
            "unrelated_blocks_excluded": ["PUBLIC_DNS", "PUBLIC_TLS", "DRIVE_WRITEBACK", "BITCOIN_IBD", "BRAINK_FULL_MIGRATION"],
        }
        _write_report(result)
        _proof("TL2_BIND_BLOCKED", result)
        print(json.dumps(result, indent=2))
        return 2

    if not token:
        result = {
            "status": "BLOCKED_TL2_AUTH",
            "promotion": None,
            "identity": TL2_ID,
            "address": host,
            "reason": "KEX_BEARER_TOKEN is required for non-loopback TL2 action-runtime binding",
        }
        _write_report(result)
        _proof("TL2_AUTH_BLOCKED", result)
        print(json.dumps(result, indent=2))
        return 5

    with socket.socket() as sock:
        try:
            sock.bind((host, 0))
        except OSError as exc:
            result = {"status": "BLOCKED_TL2_BIND", "promotion": None, "identity": TL2_ID, "address": host, "error": str(exc)}
            _write_report(result)
            _proof("TL2_BIND_BLOCKED", result)
            print(json.dumps(result, indent=2))
            return 3

    _proof("TL2_SOURCE_BOUND", {"source_object": SOURCE_ID, "service": SERVICE_ID, "runtime": RUNTIME_ID, "transport": TL2_ID})
    _proof("TL2_TUNNEL_BOUND", {"identity": TL2_ID, "address": host, "source": source})

    supervisor = _spawn_supervisor(host, 8790)
    checks = [
        _wait(f"http://{host}:8790/api/health", token),
        _wait(f"http://{host}:8790/api/services", token),
        _wait(f"http://{host}:8790/api/routes", token),
        _wait(f"http://{host}:8790/api/proof-ledger", token),
    ]
    time.sleep(0.25)
    supervisor_alive = supervisor.poll() is None
    supervisor_state = _read_supervisor_state()
    child_running = supervisor_state.get("observedState") in {"STARTING", "RUNNING", "RESTARTING"}
    ok = supervisor_alive and child_running and all(check["ok"] for check in checks)
    result = {
        "status": "VERIFIED" if ok else "FAIL",
        "promotion": "TL2_LIVE" if ok else None,
        "identity": TL2_ID,
        "address": host,
        "identity_source": source,
        "source_object": SOURCE_ID,
        "service": SERVICE_ID,
        "runtime": RUNTIME_ID,
        "supervision": {
            "supervisorPid": supervisor.pid,
            "aliveAfterReadback": supervisor_alive,
            "state": supervisor_state,
        },
        "readback": checks,
        "proof_ledger": str(PROOF.relative_to(BASE)),
        "excluded_from_deploy": ["PUBLIC_LIVE", "LIBRARY_PERSISTED", "BITCOIN_LIVE", "BRAINK_MIGRATED"],
        "public_promotions": ["NOT_CLAIMED"],
    }
    _write_report(result)
    _proof("TL2_DEPLOYMENT_READBACK", result)
    print(json.dumps(result, indent=2))

    if not ok or not daemon:
        supervisor.terminate()
        try:
            supervisor.wait(timeout=8)
        except subprocess.TimeoutExpired:
            supervisor.kill()
            supervisor.wait(timeout=5)
    return 0 if ok else 4


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true")
    raise SystemExit(deploy(parser.parse_args().daemon))
