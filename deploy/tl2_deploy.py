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
REPORT = BASE / "reports" / "kex-wbos" / "tl2-deployment.json"
PROOF = BASE / "reports" / "kex-wbos" / "tl2-proof-ledger.jsonl"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _detect_tl2_address() -> tuple[str | None, str]:
    explicit = os.getenv("KEX_TL2_ADDRESS")
    if explicit:
        return explicit, "KEX_TL2_ADDRESS"
    try:
        raw = subprocess.check_output(["ip", "-j", "addr"], text=True, stderr=subprocess.DEVNULL)
        for iface in json.loads(raw):
            name = str(iface.get("ifname", "")).lower()
            if not any(token in name for token in ("tl2", "tlvpn", "tailscale", "wg", "tun")):
                continue
            for info in iface.get("addr_info", []):
                if info.get("family") == "inet" and info.get("local") and not str(info["local"]).startswith("127."):
                    return str(info["local"]), iface.get("ifname", "tunnel")
    except Exception:
        pass
    return None, "unresolved"


def _wait(url: str, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                body = r.read()
                return {"url": url, "status": r.status, "bytes": len(body), "sha256": _sha(body), "ok": r.status < 400}
        except Exception as exc:
            last = type(exc).__name__
            time.sleep(0.25)
    return {"url": url, "status": None, "bytes": 0, "sha256": None, "ok": False, "error": last}


def _proof(event: str, payload: dict) -> None:
    PROOF.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": time.time(), "event": event, **payload}
    with PROOF.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def _spawn(module: str, host: str, port: int) -> subprocess.Popen:
    code = (
        "import sys; "
        f"sys.path.insert(0, {repr(str(BASE / 'modules' / 'kex_wbos'))}); "
        f"import {module}; {module}.serve({host!r}, {port})"
    )
    return subprocess.Popen([sys.executable, "-c", code], cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def deploy(daemon: bool) -> int:
    host, identity_source = _detect_tl2_address()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    if not host:
        receipt = {
            "status": "BLOCKED_TL2_ACTUATOR",
            "promotion": None,
            "identity": "tlvpn://kex/tl2",
            "reason": "No KEX_TL2_ADDRESS or observed TL2/tunnel interface address",
            "public_promotions": ["BLOCKED"],
        }
        REPORT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        _proof("TL2_BIND_BLOCKED", receipt)
        print(json.dumps(receipt, indent=2))
        return 2

    # Fail early if the selected tunnel address is not bindable on this host.
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, 0))
    except OSError as exc:
        receipt = {"status": "BLOCKED_TL2_BIND", "promotion": None, "address": host, "error": str(exc)}
        REPORT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        _proof("TL2_BIND_BLOCKED", receipt)
        print(json.dumps(receipt, indent=2))
        return 3
    finally:
        probe.close()

    _proof("TL2_TUNNEL_BOUND", {"identity": "tlvpn://kex/tl2", "address": host, "source": identity_source})
    wbos = _spawn("server", host, 8765)
    action = _spawn("action_server", host, 8790)
    checks = [
        _wait(f"http://{host}:8765/api/health"),
        _wait(f"http://{host}:8790/api/health"),
        _wait(f"http://{host}:8790/api/services"),
        _wait(f"http://{host}:8790/api/routes"),
        _wait(f"http://{host}:8790/api/proof-ledger"),
    ]
    ok = all(c["ok"] for c in checks)
    promotion = "TL2_LIVE" if ok else None
    receipt = {
        "status": "VERIFIED" if ok else "FAIL",
        "promotion": promotion,
        "identity": "tlvpn://kex/tl2",
        "address": host,
        "identity_source": identity_source,
        "services": {"wbos": {"pid": wbos.pid, "port": 8765}, "action_runtime": {"pid": action.pid, "port": 8790}},
        "readback": checks,
        "proof_ledger": str(PROOF.relative_to(BASE)),
        "public_promotions": ["NOT_CLAIMED"],
    }
    REPORT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    _proof("TL2_DEPLOYMENT_READBACK", receipt)
    print(json.dumps(receipt, indent=2))

    if not ok or not daemon:
        for proc in (action, wbos):
            proc.terminate()
        for proc in (action, wbos):
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    return 0 if ok else 4


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true", help="Leave verified services resident on a persistent TL2 host")
    args = parser.parse_args()
    raise SystemExit(deploy(args.daemon))
