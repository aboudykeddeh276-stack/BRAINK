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

BASE = Path(__file__).resolve().parents[2]
MODULES = BASE / "modules" / "kex_wbos"
STATE = BASE / "runtime" / "resident-controller" / "state.json"
HISTORY = BASE / "runtime" / "resident-controller" / "history.jsonl"
PROOF = BASE / "reports" / "kex-wbos" / "resident-runtime-proof.jsonl"
CONTINUATION = BASE / "continuation" / "KEX_RUNTIME_HARDENING_CONTINUATION_R2.json"
WBOS_STATE = BASE / "runtime" / "supervisor" / "wbos-action-server.json"
ILLLM_STATE = BASE / "runtime" / "supervisor" / "illlm-recursive-runtime.json"
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
        "serviceChildren": ["service://wbos/action-server", "service://illlm/recursive-runtime"],
        "semanticControl": "il-llm://meta/il-llm-of-il-llms",
        "gitDependency": "NONE_FOR_RUNTIME_LIVENESS",
        "updatedAt": time.time(),
        **payload,
    }
    atomic_write_text(STATE, json.dumps(body, indent=2, sort_keys=True) + "\n")


def _read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"observedState": "UNOBSERVED"}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {"observedState": "INVALID_STATE_SHAPE"}
    except Exception as exc:
        return {"observedState": "STATE_READ_FAILED", "error": type(exc).__name__}


def retain_latest_oracle(previous: dict[str, Any] | None, current: dict[str, Any] | None) -> dict[str, Any] | None:
    """Keep the latest completed oracle result until a newer cycle replaces it."""
    return current if current is not None else previous


def _spawn_supervisor(script: str, host: str, port: int) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            str(MODULES / script),
            "--host", host,
            "--port", str(port),
            "--max-restarts", os.getenv("KEX_RESIDENT_MAX_RESTARTS", "5"),
            "--restart-window", os.getenv("KEX_RESIDENT_RESTART_WINDOW", "60"),
        ],
        cwd=BASE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=os.environ.copy(),
    )


def _http_json(host: str, port: int, path: str) -> dict[str, Any]:
    url = f"http://{host}:{port}{path}"
    req = urllib.request.Request(url)
    token = os.getenv("KEX_BEARER_TOKEN", "")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            body = response.read()
            parsed = json.loads(body) if body else {}
            return {"ok": response.status < 400, "status": response.status, "url": url, "body": parsed}
    except Exception as exc:
        return {"ok": False, "status": None, "error": type(exc).__name__, "url": url}


def _terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill(); proc.wait(timeout=5)


def _run_local_oracles() -> dict[str, Any]:
    commands = [
        [sys.executable, str(BASE / "scripts" / "kex-ci" / "verify_action_ledger.py")],
        [sys.executable, str(BASE / "scripts" / "kex-ci" / "test_runtime_hardening.py")],
        [sys.executable, str(BASE / "scripts" / "kex-ci" / "exercise_capability_fabric.py")],
        [sys.executable, str(BASE / "scripts" / "kex-ci" / "test_illlm_recursive_runtime.py")],
        [sys.executable, str(BASE / "scripts" / "kex-ci" / "test_lease_fencing.py")],
        [sys.executable, str(BASE / "scripts" / "kex-ci" / "test_resident_oracle_projection.py")],
        [sys.executable, str(BASE / "scripts" / "kex-ci" / "test_vfs_generation_mirror_learning.py")],
    ]
    results: list[dict[str, Any]] = []
    for command in commands:
        try:
            proc = subprocess.run(command, cwd=BASE, capture_output=True, text=True, timeout=180, shell=False)
            results.append({
                "command": command[-1],
                "returnCode": proc.returncode,
                "ok": proc.returncode == 0,
                "stdoutTail": proc.stdout[-3000:],
                "stderrTail": proc.stderr[-3000:],
            })
        except Exception as exc:
            results.append({"command": command[-1], "returnCode": None, "ok": False, "error": type(exc).__name__})
    return {"ok": all(item["ok"] for item in results), "results": results}


def run(host: str, wbos_port: int, illlm_port: int, oracle_interval: int, health_interval: int) -> int:
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    wbos = _spawn_supervisor("service_supervisor.py", host, wbos_port)
    illlm = _spawn_supervisor("illlm_service_supervisor.py", host, illlm_port)
    _event(
        "RESIDENT_CONTROLLER_STARTED",
        pid=os.getpid(),
        host=host,
        wbosSupervisorPid=wbos.pid,
        illlmSupervisorPid=illlm.pid,
        wbosPort=wbos_port,
        illlmPort=illlm_port,
    )
    last_oracle = 0.0
    latest_oracle_state: dict[str, Any] | None = None
    wbos_failures = 0
    illlm_failures = 0

    while not STOP:
        if wbos.poll() is not None:
            _event("WBOS_SUPERVISOR_EXITED", exitCode=wbos.returncode)
            wbos = _spawn_supervisor("service_supervisor.py", host, wbos_port)
            _event("WBOS_SUPERVISOR_RESPAWNED", supervisorPid=wbos.pid)
        if illlm.poll() is not None:
            _event("ILLLM_SUPERVISOR_EXITED", exitCode=illlm.returncode)
            illlm = _spawn_supervisor("illlm_service_supervisor.py", host, illlm_port)
            _event("ILLLM_SUPERVISOR_RESPAWNED", supervisorPid=illlm.pid)

        wbos_health = _http_json(host, wbos_port, "/api/health")
        illlm_health = _http_json(host, illlm_port, "/health")
        wbos_failures = 0 if wbos_health["ok"] else wbos_failures + 1
        illlm_failures = 0 if illlm_health["ok"] else illlm_failures + 1

        oracle_state = None
        now = time.time()
        if now - last_oracle >= oracle_interval:
            oracle_state = _run_local_oracles()
            _event("LOCAL_ORACLE_CYCLE", result=oracle_state)
            last_oracle = now
        latest_oracle_state = retain_latest_oracle(latest_oracle_state, oracle_state)

        _write_state(
            desiredState="RUNNING",
            observedState="RUNNING" if wbos_health["ok"] and illlm_health["ok"] else "DEGRADED",
            services={
                "wbos": {
                    "supervisorPid": wbos.pid,
                    "supervisorAlive": wbos.poll() is None,
                    "state": _read_state(WBOS_STATE),
                    "health": wbos_health,
                    "consecutiveHealthFailures": wbos_failures,
                },
                "illlm": {
                    "supervisorPid": illlm.pid,
                    "supervisorAlive": illlm.poll() is None,
                    "state": _read_state(ILLLM_STATE),
                    "health": illlm_health,
                    "consecutiveHealthFailures": illlm_failures,
                },
            },
            lastOracle=latest_oracle_state,
            continuationRecord=CONTINUATION.relative_to(BASE).as_posix() if CONTINUATION.exists() else None,
        )

        if wbos_failures >= 3:
            _event("WBOS_HEALTH_RECOVERY_TRIGGERED", failures=wbos_failures, supervisorPid=wbos.pid)
            _terminate(wbos)
            wbos = _spawn_supervisor("service_supervisor.py", host, wbos_port)
            wbos_failures = 0
        if illlm_failures >= 3:
            _event("ILLLM_HEALTH_RECOVERY_TRIGGERED", failures=illlm_failures, supervisorPid=illlm.pid)
            _terminate(illlm)
            illlm = _spawn_supervisor("illlm_service_supervisor.py", host, illlm_port)
            illlm_failures = 0

        time.sleep(max(1, health_interval))

    _terminate(wbos)
    _terminate(illlm)
    _write_state(desiredState="STOPPED", observedState="STOPPED", lastOracle=latest_oracle_state)
    _event("RESIDENT_CONTROLLER_STOPPED", pid=os.getpid())
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("KEX_RESIDENT_HOST", os.getenv("KEX_TL2_ADDRESS", "127.0.0.1")))
    parser.add_argument("--port", dest="wbos_port", type=int, default=int(os.getenv("KEX_RESIDENT_PORT", "8790")))
    parser.add_argument("--illlm-port", type=int, default=int(os.getenv("KEX_ILLLM_PORT", "8791")))
    parser.add_argument("--oracle-interval", type=int, default=int(os.getenv("KEX_RESIDENT_ORACLE_INTERVAL", "300")))
    parser.add_argument("--health-interval", type=int, default=int(os.getenv("KEX_RESIDENT_HEALTH_INTERVAL", "5")))
    args = parser.parse_args()
    raise SystemExit(run(args.host, args.wbos_port, args.illlm_port, args.oracle_interval, args.health_interval))
