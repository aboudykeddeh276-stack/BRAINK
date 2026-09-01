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

from hardening import atomic_write_text

BASE = Path(__file__).resolve().parents[2]
STATE = BASE / "runtime" / "supervisor" / "wbos-action-server.json"
STOP = False


def _signal_handler(signum, frame):
    global STOP
    STOP = True


def _write_state(payload: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(STATE, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _spawn(host: str, port: int) -> subprocess.Popen:
    code = (
        "import sys; "
        f"sys.path.insert(0,{str(BASE / 'modules' / 'kex_wbos')!r}); "
        "import action_server; "
        f"action_server.serve({host!r},{port})"
    )
    env = os.environ.copy()
    env["RUNNER_TRACKING_ID"] = ""
    return subprocess.Popen(
        [sys.executable, "-c", code],
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
    restart_times: deque[float] = deque()
    child: subprocess.Popen | None = None

    while not STOP:
        generation += 1
        child = _spawn(host, port)
        _write_state({
            "serviceId": "service://wbos/action-server",
            "supervisorPid": os.getpid(),
            "generation": generation,
            "childPid": child.pid,
            "desiredState": "RUNNING",
            "observedState": "STARTING",
            "host": host,
            "port": port,
            "restartPolicy": {"maxRestarts": max_restarts, "windowSec": restart_window},
            "updatedAt": time.time(),
        })

        while not STOP and child.poll() is None:
            _write_state({
                "serviceId": "service://wbos/action-server",
                "supervisorPid": os.getpid(),
                "generation": generation,
                "childPid": child.pid,
                "desiredState": "RUNNING",
                "observedState": "RUNNING",
                "host": host,
                "port": port,
                "restartPolicy": {"maxRestarts": max_restarts, "windowSec": restart_window},
                "updatedAt": time.time(),
            })
            time.sleep(1.0)

        if STOP:
            break

        exit_code = child.returncode
        now = time.time()
        restart_times.append(now)
        while restart_times and now - restart_times[0] > restart_window:
            restart_times.popleft()

        if len(restart_times) > max_restarts:
            _write_state({
                "serviceId": "service://wbos/action-server",
                "supervisorPid": os.getpid(),
                "generation": generation,
                "childPid": child.pid,
                "desiredState": "RUNNING",
                "observedState": "FAILED_RESTART_INTENSITY",
                "exitCode": exit_code,
                "restartCountInWindow": len(restart_times),
                "updatedAt": now,
            })
            return 70

        _write_state({
            "serviceId": "service://wbos/action-server",
            "supervisorPid": os.getpid(),
            "generation": generation,
            "childPid": child.pid,
            "desiredState": "RUNNING",
            "observedState": "RESTARTING",
            "exitCode": exit_code,
            "restartCountInWindow": len(restart_times),
            "updatedAt": now,
        })
        time.sleep(min(2 ** min(len(restart_times), 4), 10))

    if child is not None and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)

    _write_state({
        "serviceId": "service://wbos/action-server",
        "supervisorPid": os.getpid(),
        "generation": generation,
        "childPid": child.pid if child else None,
        "desiredState": "STOPPED",
        "observedState": "STOPPED",
        "updatedAt": time.time(),
    })
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--max-restarts", type=int, default=5)
    parser.add_argument("--restart-window", type=int, default=60)
    args = parser.parse_args()
    raise SystemExit(supervise(args.host, args.port, args.max_restarts, args.restart_window))
