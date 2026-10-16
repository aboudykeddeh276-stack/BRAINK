#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from enterprise.tot_orc_dispatcher import ToTOrcDispatcher
from node_fabric.node_fabric import NodeFabric
from runtime.runtime_registry import RuntimeRegistry


def http_json(method, url, payload=None, timeout=15):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, json.loads(raw.decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            body = json.loads(raw.decode() or "{}")
        except Exception:
            body = {}
        return e.code, body


def wait_health(url, timeout=20):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            status, body = http_json("GET", url, timeout=2)
            if status < 500:
                return status, body
            last = (status, body)
        except Exception as exc:
            last = repr(exc)
        time.sleep(0.2)
    raise RuntimeError(f"health timeout: {last!r}")


def main():
    results = []

    # Exercise the existing KEX/WBOS action server and its existing RuntimeDispatcher.
    action = subprocess.Popen(
        [sys.executable, str(ROOT / "modules/kex_wbos/action_server.py")],
        cwd=ROOT,
        env={**os.environ, "KEX_BEARER_TOKEN": ""},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        wait_health("http://127.0.0.1:8790/", timeout=20)

        status, body = http_json(
            "POST",
            "http://127.0.0.1:8790/runtime/control",
            {"action": "REGISTER", "command_route": "public-gateway", "desired_state": "STOPPED"},
        )
        results.append(("WBOS_REGISTER_PUBLIC_GATEWAY", status == 200 and body.get("status") == "PASS"))

        status, body = http_json(
            "POST",
            "http://127.0.0.1:8790/runtime/control",
            {"action": "START", "runtime_id": "runtime://public-gateway"},
        )
        results.append(("WBOS_START_PUBLIC_GATEWAY", status == 200 and body.get("status") == "PASS"))

        status, body = wait_health("http://127.0.0.1:8799/health", timeout=20)
        results.append(("REAL_PUBLIC_GATEWAY_HEALTH", status == 200 and body.get("status") == "PASS"))

        # Exercise actual public-gateway projections backed by resident runtime modules.
        for name, path in [
            ("HOME_SUMMARY", "/home/summary"),
            ("DIAGNOSTICS_SUMMARY", "/diagnostics/summary"),
            ("MCP_WORKFLOWS", "/mcp/workflows"),
            ("DASHBOARD_SUMMARY", "/dashboards/summary"),
        ]:
            status, body = http_json("GET", "http://127.0.0.1:8799" + path)
            results.append((name, status == 200 and isinstance(body, dict)))

        # Stress the actual gateway, not a test server embedded in this script.
        def probe(i):
            path = "/health" if i % 2 == 0 else "/home/summary"
            return http_json("GET", "http://127.0.0.1:8799" + path, timeout=20)[0]

        for workers in (32, 64, 128, 256):
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                statuses = list(ex.map(probe, range(500)))
            ok = sum(1 for s in statuses if s == 200)
            results.append((f"ACTUAL_GATEWAY_LOAD_{workers}", ok == 500))

        # Exercise the actual persistent node-fabric implementation.
        with tempfile.TemporaryDirectory() as td:
            nf = NodeFabric(Path(td) / "node-fabric.sqlite3")
            spec = {
                "template_id": "kex-1x-stress",
                "semantic_type": "RUNTIME_STATE",
                "node_class": "SMART",
                "definition": {"purpose": "integration stress"},
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
                "attributes": {"surface": "KEX-1X"},
                "capabilities": ["state", "vfs", "runtime"],
                "integration_contracts": ["runtime://public-gateway"],
                "state_schema": {"default": {"status": "ACTIVE"}},
                "observer_contract": {"mode": "explicit"},
                "attribution_graph": [{"root": "BRAINK"}],
            }
            template = nf.define(spec)
            instance = nf.instantiate("kex-1x-stress")
            nf.set_state(instance["instance_id"], {"status": "STRESSED", "seq": 1}, instance["observer_id"])
            edge = nf.connect(instance["instance_id"], instance["instance_id"], "SELF_STATE")
            ledger = nf.verify()
            results.append(("NODE_FABRIC_DEFINE", template["template_id"] == "kex-1x-stress"))
            results.append(("NODE_FABRIC_INSTANCE", instance["vfs_uri"].startswith("vfs://node/")))
            results.append(("NODE_FABRIC_EDGE", edge["relation"] == "SELF_STATE"))
            results.append(("NODE_FABRIC_LEDGER", ledger.get("ok") is True and ledger.get("count", 0) >= 3))

        # Exercise actual runtime registry persistence.
        with tempfile.TemporaryDirectory() as td:
            rr = RuntimeRegistry(Path(td) / "runtime.sqlite3")
            route = {
                "runtime_id": "runtime://integration-probe",
                "runtime_class": "TEST",
                "command_route": "integration-probe",
                "argv": [sys.executable, "-c", "print('probe')"],
                "dependencies": [],
                "health_endpoint": None,
                "desired_state": "RUNNING",
                "observed_state": "READY",
            }
            saved = rr.upsert(route)
            observed = rr.observe("runtime://integration-probe", observed_state="READY", pid=None)
            results.append(("RUNTIME_REGISTRY_STATE_ROOT", bool(saved.get("state_root"))))
            results.append(("RUNTIME_REGISTRY_READBACK", observed.get("observed_state") == "READY"))

        # Exercise actual carrier failover mechanics.
        d = ToTOrcDispatcher()
        d.register_handler("TL2", lambda c: {"status": "FAILED"})
        d.register_handler("TL1", lambda c: {"status": "DISPATCHED"})
        d.register_handler("VPN-TL", lambda c: {"status": "DISPATCHED"})
        first = d.dispatch({"continuation_id": "continuation://kex-1x/1"})
        results.append(("CARRIER_FAILOVER_TL2_TO_TL1", first.get("carrier") == "TL1"))

        d.set_availability("TL1", False)
        d.set_availability("TL2", False)
        second = d.dispatch({"continuation_id": "continuation://kex-1x/2"})
        results.append(("CARRIER_FAILOVER_TO_VPN_TL", second.get("carrier") == "VPN-TL"))

        d.set_availability("VPN-TL", False)
        third = d.dispatch({"continuation_id": "continuation://kex-1x/3"})
        results.append(("CARRIER_EXHAUSTION_RECEIPT", third.get("status") == "FAILOVER_EXHAUSTED"))

        # Runtime readback through the existing WBOS controller.
        status, body = http_json(
            "POST",
            "http://127.0.0.1:8790/runtime/control",
            {"action": "READBACK", "runtime_id": "runtime://public-gateway"},
        )
        results.append(("WBOS_RUNTIME_READBACK", status == 200 and body.get("status") == "PASS"))

        # Stop the actual runtime through the existing controller.
        status, body = http_json(
            "POST",
            "http://127.0.0.1:8790/runtime/control",
            {"action": "STOP", "runtime_id": "runtime://public-gateway"},
        )
        results.append(("WBOS_STOP_PUBLIC_GATEWAY", status == 200 and body.get("status") == "PASS"))

    finally:
        if action.poll() is None:
            action.send_signal(signal.SIGTERM)
            try:
                action.wait(timeout=10)
            except subprocess.TimeoutExpired:
                action.kill()
                action.wait(timeout=5)

    failed = [name for name, ok in results if not ok]
    for name, ok in results:
        print(("PASS " if ok else "FAIL ") + name)

    report = {
        "test": "KEX-1X ACTUAL BRAINK/KEX RUNTIME INTEGRATION ATTACK",
        "status": "PASS" if not failed else "FAIL",
        "checks": [{"name": n, "passed": ok} for n, ok in results],
        "failed_checks": failed,
        "actual_runtime": [
            "modules/kex_wbos/action_server.py",
            "modules/kex_wbos/runtime_dispatcher.py",
            "runtime/public_gateway.py",
            "runtime/runtime_registry.py",
            "node-fabric/node_fabric.py",
            "enterprise/tot_orc_dispatcher.py",
        ],
        "external_network": False,
        "physical_1TB": False,
    }
    report_path = ROOT / "reports" / "kex-1x-actual-runtime-integration.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
