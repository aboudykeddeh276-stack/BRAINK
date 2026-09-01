#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "modules" / "kex_wbos" / "server.py"
OPENAPI = ROOT / "openapi" / "kex-wbos-cascade-os.yaml"
LEDGER = ROOT / "reports" / "kex-wbos" / "proof-ledger.jsonl"
BASE = "http://127.0.0.1:8765"


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=3) as response:
        body = response.read()
        return response.status, response.headers.get("Content-Type", ""), body


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    if LEDGER.exists():
        LEDGER.unlink()

    spec = OPENAPI.read_text(encoding="utf-8")
    for required in ["openapi: 3.1.0", "/api/health:", "/api/services:", "/api/routes:", "/api/resolve:", "/mesh:", "/cascade:", "/api/proof-ledger:"]:
        require(required in spec, f"OpenAPI surface missing: {required}")

    proc = subprocess.Popen([sys.executable, str(SERVER)], cwd=ROOT)
    try:
        deadline = time.time() + 10
        while True:
            try:
                status, _, _ = get("/api/health")
                if status == 200:
                    break
            except Exception:
                pass
            if time.time() >= deadline:
                raise AssertionError("WBOS server did not become reachable")
            time.sleep(0.1)

        status, ctype, apex = get("/")
        require(status == 200 and "text/html" in ctype and b"KEX K.0 Apex" in apex, "apex projection failed")

        status, _, raw = get("/api/health")
        health = json.loads(raw)
        require(health["status"] == "ok", "health not ok")
        require(health["os"] == "KEX-WBOS Cascade OS", "wrong OS identity")
        require(len(health["cascade_order"]) == 10, "cascade order incomplete")
        require(set(["ts", "event", "target", "value", "actor"]).issubset(health["proof"]), "health proof incomplete")

        _, _, raw = get("/api/services")
        services = json.loads(raw)["services"]
        require(any(x["service"] == "resolver" for x in services), "resolver service absent")

        _, _, raw = get("/api/routes")
        routes = json.loads(raw)["routes"]
        require(any(x["kex"] == "KEX://ROOT/OS" for x in routes), "root KEX URI absent")

        uri = urllib.parse.quote("KEX://ROOT/OS", safe="")
        _, _, raw = get(f"/api/resolve?uri={uri}")
        resolved = json.loads(raw)
        require(resolved["result"]["found"] is True, "root KEX URI did not resolve")
        require(resolved["result"]["target"] == "wbos.apex", "root KEX URI resolved to wrong target")

        _, _, raw = get("/mesh")
        mesh = json.loads(raw)
        require(mesh["state"] == "LOCAL_REGISTRY_ONLY", "mesh boundary was over-promoted")

        _, _, raw = get("/cascade")
        cascade = json.loads(raw)
        require(cascade["root"] == "KEX://ROOT/OS", "cascade root mismatch")
        require(cascade["order"] == health["cascade_order"], "cascade order inconsistent")

        _, _, raw = get("/api/proof-ledger")
        entries = json.loads(raw)["entries"]
        require(len(entries) >= 7, "proof ledger did not capture endpoint activity")
        events = {e["event"] for e in entries}
        for event in ["WBOS_BOOT", "HEALTH_READ", "PROJECT_UI", "RESOLVE_KEX_URI", "MESH_STATUS_READ", "CASCADE_READ"]:
            require(event in events, f"proof event missing: {event}")

        receipt = {
            "schema": "kex.wbos.integration-test.v1",
            "state": "PASS",
            "openapi_surface": "resident",
            "server_process": "executed",
            "http_endpoints_exercised": 8,
            "proof_entries": len(entries),
            "mesh_boundary": mesh["state"],
            "claim_boundary": "This proves local WBOS API execution in the GitHub job/runtime context. It does not prove public deployment, external mesh connectivity, browser IndexedDB execution, or workbook substrate mounting."
        }
        out = ROOT / "reports" / "kex-wbos" / "integration.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2))
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
