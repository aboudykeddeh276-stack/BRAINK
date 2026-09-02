#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "modules" / "kex_wbos" / "action_server.py"
BASE = "http://127.0.0.1:8790"
HTTP_LEDGER = ROOT / "reports" / "kex-wbos" / "canonical-http-ledger.jsonl"
ACTION_LEDGER = ROOT / "reports" / "kex-wbos" / "canonical-action-ledger.jsonl"
REPORT = ROOT / "reports" / "kex-wbos" / "canonical-http-runtime-test.json"


def request(path: str, payload: dict | None = None, method: str = "GET") -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        body = json.loads(response.read().decode("utf-8"))
        return response.status, body


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> int:
    # Keep proof isolated from prior developer-machine state.
    for path in (HTTP_LEDGER, ACTION_LEDGER):
        if path.exists():
            path.unlink()

    proc = subprocess.Popen([sys.executable, str(SERVER)], cwd=ROOT)
    try:
        deadline = time.time() + 10
        while True:
            try:
                status, health = request("/api/health")
                if status == 200:
                    break
            except Exception:
                pass
            if time.time() > deadline:
                raise AssertionError("canonical action server did not become reachable")
            time.sleep(0.1)

        require(health.get("status") == "ok", "health semantics changed through canonical egress")

        status, armed = request(
            "/actions/execute",
            {
                "requestId": "KEX-HTTP-CANONICAL-TEST-1",
                "authority": "A.KEDDEH",
                "actionType": "CANONICAL_HTTP_SELF_TEST",
                "target": "runtime://kex-wbos",
                "payload": {
                    "state": 1,
                    "axis": [-3, -2, 1, 2, 3],
                    "resonance": 0.297,
                },
            },
            "POST",
        )
        require(status == 200, "canonical action HTTP request failed")
        require(armed.get("status") == "ARMED", "unknown external action was incorrectly promoted")
        canonical = armed.get("canonicalState", {})
        require(canonical.get("evidenceLevel") == "SOFTWARE_OBSERVED", "canonical action evidence missing")
        require(canonical.get("measurementClass") == "STRUCTURAL_PROXY", "propagation proxy classification missing")
        require(canonical.get("identityPreserved") is True, "action wrapper did not preserve canonical state")

        status, blocked = request(
            "/deployment/dns/apply",
            {
                "requestId": "KEX-HTTP-CANONICAL-DNS-1",
                "authority": "A.KEDDEH",
                "providerRoute": "",
                "records": [{"name": "casepath.com.au", "type": "A", "value": "127.0.0.1"}],
            },
            "POST",
        )
        require(status == 200, "canonical DNS action HTTP request failed")
        require(blocked.get("status") == "BLOCKED", "DNS without provider adapter was falsely promoted")
        require(blocked.get("mutated") is False, "blocked DNS action claimed mutation")
        require(blocked.get("canonicalState", {}).get("identityPreserved") is True, "DNS action skipped canonical executor")

        http_rows = read_jsonl(HTTP_LEDGER)
        action_rows = read_jsonl(ACTION_LEDGER)
        ingress = [r for r in http_rows if r.get("direction") == "INGRESS"]
        egress = [r for r in http_rows if r.get("direction") == "EGRESS"]

        require(len(ingress) >= 2, "HTTP ingress canonical receipts missing")
        require(len(egress) >= 3, "HTTP egress canonical receipts missing")
        require(len(action_rows) >= 2, "canonical action receipts missing")
        require(all(r.get("identityPreserved") is True for r in http_rows), "HTTP canonical round-trip failure recorded")
        require(all(r.get("measurementClass") == "STRUCTURAL_PROXY" for r in http_rows), "HTTP metric class overclaimed")

        receipt = {
            "schema": "kex.canonical-http-runtime-test.v1",
            "state": "PASS",
            "server": "modules/kex_wbos/action_server.py",
            "health": "PRESERVED",
            "unknownAction": armed.get("status"),
            "dnsWithoutAdapter": blocked.get("status"),
            "httpIngressReceipts": len(ingress),
            "httpEgressReceipts": len(egress),
            "canonicalActionReceipts": len(action_rows),
            "identityPreserved": True,
            "measurementClass": "STRUCTURAL_PROXY",
            "claimBoundary": (
                "PASS proves canonical JSON ingress/egress and canonical action execution "
                "through a live local WBOS HTTP process. It does not prove external network "
                "mutation, binary carrier canonicalization, hardware performance, or physical propagation."
            ),
        }
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
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
