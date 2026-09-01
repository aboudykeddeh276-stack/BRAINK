#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from hardening import append_jsonl_fsync, atomic_write_text
from illlm_higher_order import build_topology, route_to_role
from illlm_executable_graph import build_executable_graph

BASE = Path(__file__).resolve().parents[2]
MODULES = BASE / "modules" / "kex_wbos"
STATE = BASE / "runtime" / "resident-controller" / "state.json"
HISTORY = BASE / "runtime" / "resident-controller" / "history.jsonl"
PROOF = BASE / "reports" / "kex-wbos" / "resident-runtime-proof.jsonl"
CONTINUATION = BASE / "continuation" / "KEX_RUNTIME_HARDENING_CONTINUATION_R2.json"
SERVICE_STATE = BASE / "runtime" / "supervisor" / "wbos-action-server.json"
SERVICE_BINDING = BASE / "runtime" / "KEX_RESIDENT_SERVICE_BINDING_R1.json"
ILLLM_BENCHMARK = BASE / "reports" / "kex-wbos" / "illlm-higher-order-benchmark.json"
STOP = False


def _signal_handler(signum, frame):
    global STOP
    STOP = True


def _event(event: str, **payload: Any) -> None:
    record = {"ts": time.time(), "event": event, **payload}
    append_jsonl_fsync(HISTORY, record)
    append_jsonl_fsync(PROOF, record)


def _write_state(**payload: Any) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "controllerId": "runtime://kex/resident-controller",
        "hostLineage": "K_Cloud_Substrate_Master_Daemon.ipynb",
        "serviceChild": "service://wbos/action-server",
        "semanticControl": "il-llm://braink",
        "gitDependency": "NONE_FOR_RUNTIME_LIVENESS",
        "updatedAt": time.time(),
        **payload,
    }
    atomic_write_text(STATE, json.dumps(body, indent=2, sort_keys=True) + "\n")


def _read_service_state() -> dict[str, Any]:
    if not SERVICE_STATE.exists():
        return {"observedState": "UNOBSERVED"}
    try:
        return json.loads(SERVICE_STATE.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"observedState": "STATE_READ_FAILED", "error": type(exc).__name__}


def _spawn_service(host: str, port: int) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            str(MODULES / "service_supervisor.py"),
            "--host",
            host,
            "--port",
            str(port),
            "--max-restarts",
            os.getenv("KEX_RESIDENT_MAX_RESTARTS", "5"),
            "--restart-window",
            os.getenv("KEX_RESIDENT_RESTART_WINDOW", "60"),
        ],
        cwd=BASE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=os.environ.copy(),
    )


def _health(host: str, port: int) -> dict[str, Any]:
    url = f"http://{host}:{port}/api/health"
    req = urllib.request.Request(url)
    token = os.getenv("KEX_BEARER_TOKEN", "")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            body = response.read()
            return {"ok": response.status < 400, "status": response.status, "bytes": len(body), "url": url}
    except Exception as exc:
        return {"ok": False, "status": None, "error": type(exc).__name__, "url": url}


def _service_objects() -> list[dict[str, Any]]:
    if not SERVICE_BINDING.exists():
        return []
    try:
        payload = json.loads(SERVICE_BINDING.read_text(encoding="utf-8"))
    except Exception:
        return []
    objects: list[dict[str, Any]] = []
    for item in payload.get("service_authority_fabric", []):
        identity = str(item.get("identity", ""))
        if not identity:
            continue
        execution_edges = []
        actuator = item.get("external_actuator")
        if actuator:
            execution_edges.append(str(actuator))
        objects.append({
            "identity": identity,
            "objectClass": item.get("class", "SERVICE"),
            "source": "runtime/KEX_RESIDENT_SERVICE_BINDING_R1.json",
            "role": item.get("resident_role"),
            "stateCarrier": item.get("state_carrier"),
            "knowledgeEdges": [str(item.get("state_carrier"))] if item.get("state_carrier") else [],
            "executionEdges": execution_edges,
            "proofEdges": ["reports/kex-wbos/resident-runtime-proof.jsonl"],
            "executionState": "REGISTERED",
        })
    return objects


def _load_illlm_state() -> dict[str, Any]:
    started = time.perf_counter_ns()
    topology = build_topology()
    role_index: dict[str, list[str]] = {}
    for role in {str(node.get("role", "GENERAL")).upper() for node in topology.get("nodes", [])}:
        role_index[role] = route_to_role(role, topology)

    executable_objects = []
    for node in topology.get("nodes", []):
        executable_objects.append({
            "identity": node.get("identity"),
            "objectClass": node.get("role"),
            "source": "runtime/ILLLM_FEDERATION_SEED_R1.json",
            "knowledgeEdges": list(node.get("children", [])),
            "executionEdges": [],
            "stateEdges": [node.get("continuation")] if node.get("continuation") else [],
            "proofEdges": ["runtime/illlm/traversal-ledger.jsonl"],
            "executionState": node.get("execution_state", "REGISTERED"),
        })
    executable_objects.extend(_service_objects())
    executable_graph = build_executable_graph(executable_objects)
    elapsed = time.perf_counter_ns() - started
    return {
        "topology": topology,
        "roleIndex": role_index,
        "executableGraph": executable_graph,
        "buildNs": elapsed,
        "loadedAt": time.time(),
    }


def _run_local_oracles() -> dict[str, Any]:
    commands = [
        [sys.executable, str(BASE / "scripts" / "kex-ci" / "verify_action_ledger.py")],
        [sys.executable, str(BASE / "scripts" / "kex-ci" / "test_runtime_hardening.py")],
        [sys.executable, str(BASE / "scripts" / "kex-ci" / "exercise_capability_fabric.py")],
        [sys.executable, str(BASE / "scripts" / "kex-ci" / "benchmark_illlm_higher_order.py")],
    ]
    results: list[dict[str, Any]] = []
    for command in commands:
        try:
            proc = subprocess.run(command, cwd=BASE, capture_output=True, text=True, timeout=180, shell=False)
            results.append({"command": command[-1], "returnCode": proc.returncode, "ok": proc.returncode == 0, "stdoutTail": proc.stdout[-2000:], "stderrTail": proc.stderr[-2000:]})
        except Exception as exc:
            results.append({"command": command[-1], "returnCode": None, "ok": False, "error": type(exc).__name__})
    return {"ok": all(item["ok"] for item in results), "results": results}


def _read_benchmark() -> dict[str, Any] | None:
    if not ILLLM_BENCHMARK.exists():
        return None
    try:
        return json.loads(ILLLM_BENCHMARK.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "BENCHMARK_READ_FAILED"}


def run(host: str, port: int, oracle_interval: int, health_interval: int, illlm_refresh_interval: int) -> int:
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    service = _spawn_service(host, port)
    illlm = _load_illlm_state()
    _event("RESIDENT_CONTROLLER_STARTED", pid=os.getpid(), serviceSupervisorPid=service.pid, host=host, port=port, illlmTopologyHash=illlm["topology"]["topologyHash"], illlmExecutableGraphHash=illlm["executableGraph"]["graphHash"], illlmNodes=illlm["topology"]["nodeCount"])
    last_oracle = 0.0
    last_illlm_refresh = time.time()
    consecutive_health_failures = 0

    while not STOP:
        service_state = _read_service_state()
        health = _health(host, port)
        consecutive_health_failures = 0 if health["ok"] else consecutive_health_failures + 1

        if service.poll() is not None:
            _event("SERVICE_SUPERVISOR_EXITED", exitCode=service.returncode)
            service = _spawn_service(host, port)
            _event("SERVICE_SUPERVISOR_RESPAWNED", serviceSupervisorPid=service.pid)

        now = time.time()
        if now - last_illlm_refresh >= illlm_refresh_interval:
            previous_topology = illlm["topology"]["topologyHash"]
            previous_exec = illlm["executableGraph"]["graphHash"]
            illlm = _load_illlm_state()
            last_illlm_refresh = now
            _event("ILLLM_STATE_REFRESH", previousTopologyHash=previous_topology, topologyHash=illlm["topology"]["topologyHash"], previousExecutableGraphHash=previous_exec, executableGraphHash=illlm["executableGraph"]["graphHash"], changed=(previous_topology != illlm["topology"]["topologyHash"] or previous_exec != illlm["executableGraph"]["graphHash"]), buildNs=illlm["buildNs"])

        oracle_state = None
        if now - last_oracle >= oracle_interval:
            oracle_state = _run_local_oracles()
            _event("LOCAL_ORACLE_CYCLE", result=oracle_state)
            last_oracle = now

        _write_state(
            desiredState="RUNNING",
            observedState="RUNNING" if health["ok"] else "DEGRADED",
            serviceSupervisorPid=service.pid,
            serviceSupervisorAlive=service.poll() is None,
            serviceState=service_state,
            health=health,
            consecutiveHealthFailures=consecutive_health_failures,
            illlm={
                "root": illlm["topology"]["root"],
                "topologyHash": illlm["topology"]["topologyHash"],
                "executableGraphHash": illlm["executableGraph"]["graphHash"],
                "nodeCount": illlm["topology"]["nodeCount"],
                "executableNodeCount": illlm["executableGraph"]["nodeCount"],
                "roleIndexCounts": {role: len(ids) for role, ids in illlm["roleIndex"].items()},
                "lastBuildNs": illlm["buildNs"],
                "benchmark": _read_benchmark(),
            },
            lastOracle=oracle_state,
            continuationRecord=CONTINUATION.relative_to(BASE).as_posix() if CONTINUATION.exists() else None,
        )

        if consecutive_health_failures >= 3:
            _event("HEALTH_RECOVERY_TRIGGERED", failures=consecutive_health_failures, serviceSupervisorPid=service.pid)
            if service.poll() is None:
                service.terminate()
                try:
                    service.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    service.kill(); service.wait(timeout=5)
            service = _spawn_service(host, port)
            consecutive_health_failures = 0
            _event("HEALTH_RECOVERY_RESPAWNED", serviceSupervisorPid=service.pid)

        time.sleep(max(1, health_interval))

    if service.poll() is None:
        service.terminate()
        try:
            service.wait(timeout=8)
        except subprocess.TimeoutExpired:
            service.kill(); service.wait(timeout=5)
    _write_state(desiredState="STOPPED", observedState="STOPPED", serviceSupervisorPid=service.pid, serviceSupervisorAlive=False)
    _event("RESIDENT_CONTROLLER_STOPPED", pid=os.getpid())
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("KEX_RESIDENT_HOST", os.getenv("KEX_TL2_ADDRESS", "127.0.0.1")))
    parser.add_argument("--port", type=int, default=int(os.getenv("KEX_RESIDENT_PORT", "8790")))
    parser.add_argument("--oracle-interval", type=int, default=int(os.getenv("KEX_RESIDENT_ORACLE_INTERVAL", "300")))
    parser.add_argument("--health-interval", type=int, default=int(os.getenv("KEX_RESIDENT_HEALTH_INTERVAL", "5")))
    parser.add_argument("--illlm-refresh-interval", type=int, default=int(os.getenv("KEX_ILLLM_REFRESH_INTERVAL", "60")))
    args = parser.parse_args()
    raise SystemExit(run(args.host, args.port, args.oracle_interval, args.health_interval, args.illlm_refresh_interval))
