#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

from hardening import append_jsonl_fsync, atomic_write_text

BASE = Path(__file__).resolve().parents[2]
STATE = BASE / "runtime" / "supervisor" / "illlm-recursive-runtime.json"
HISTORY = BASE / "runtime" / "supervisor" / "illlm-recursive-runtime-history.jsonl"
STOP = False


def _signal_handler(signum, frame):
    global STOP
    STOP = True


def _event(event: str, **payload):
    append_jsonl_fsync(HISTORY, {"ts": time.time(), "event": event, **payload})


def _write(payload: dict):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(STATE, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _spawn(host: str, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["RUNNER_TRACKING_ID"] = ""
    return subprocess.Popen(
        [sys.executable, str(BASE / "modules" / "kex_wbos" / "illlm_service.py"), "--host", host, "--port", str(port)],
        cwd=BASE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )


def supervise(host: str, port: int, max_restarts: int = 5, restart_window: int = 60) -> int:
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    generation = 0
    child = None
    restarts: deque[float] = deque()
    _event("SUPERVISOR_STARTED", serviceId="service://illlm/recursive-runtime", supervisorPid=os.getpid(), host=host, port=port)
    while not STOP:
        generation += 1
        child = _spawn(host, port)
        _event("CHILD_STARTED", generation=generation, childPid=child.pid)
        while not STOP and child.poll() is None:
            _write({
                "serviceId": "service://illlm/recursive-runtime",
                "supervisorPid": os.getpid(),
                "generation": generation,
                "childPid": child.pid,
                "desiredState": "RUNNING",
                "observedState": "RUNNING",
                "host": host,
                "port": port,
                "updatedAt": time.time(),
            })
            time.sleep(1)
        if STOP:
            break
        now = time.time()
        restarts.append(now)
        while restarts and now - restarts[0] > restart_window:
            restarts.popleft()
        _event("CHILD_EXITED", generation=generation, childPid=child.pid, exitCode=child.returncode, restartCountInWindow=len(restarts))
        if len(restarts) > max_restarts:
            _write({
                "serviceId": "service://illlm/recursive-runtime",
                "supervisorPid": os.getpid(),
                "generation": generation,
                "childPid": child.pid,
                "desiredState": "RUNNING",
                "observedState": "FAILED_RESTART_INTENSITY",
                "host": host,
                "port": port,
                "updatedAt": time.time(),
            })
            _event("SUPERVISOR_ESCALATED", generation=generation, reason="restart_intensity_exceeded")
            return 70
        time.sleep(min(2 ** min(len(restarts), 4), 10))
    if child is not None and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill(); child.wait(timeout=5)
    _write({
        "serviceId": "service://illlm/recursive-runtime",
        "supervisorPid": os.getpid(),
        "generation": generation,
        "childPid": child.pid if child else None,
        "desiredState": "STOPPED",
        "observedState": "STOPPED",
        "host": host,
        "port": port,
        "updatedAt": time.time(),
    })
    _event("SUPERVISOR_STOPPED", generation=generation)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=8791)
    parser.add_argument("--max-restarts", type=int, default=5)
    parser.add_argument("--restart-window", type=int, default=60)
    args = parser.parse_args()
    raise SystemExit(supervise(args.host, args.port, args.max_restarts, args.restart_window))
