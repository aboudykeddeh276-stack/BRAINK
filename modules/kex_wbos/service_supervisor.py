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
STATE = BASE / "runtime" / "supervisor" / "wbos-action-server.json"
HISTORY = BASE / "runtime" / "supervisor" / "wbos-action-server-history.jsonl"
STOP = False


def _signal_handler(signum, frame):
    global STOP
    STOP = True


def _event(event: str, payload: dict) -> int:
    row, _ = append_jsonl_fsync(HISTORY, {"ts": time.time(), "event": event, **payload})
    return row


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


def _state(*, generation: int, child: subprocess.Popen | None, host: str, port: int, observed: str, desired: str = "RUNNING", max_restarts: int | None = None, restart_window: int | None = None, **extra) -> dict:
    payload = {
        "serviceId": "service://wbos/action-server",
        "supervisorPid": os.getpid(),
        "generation": generation,
        "childPid": child.pid if child else None,
        "desiredState": desired,
        "observedState": observed,
        "host": host,
        "port": port,
        "historyPath": HISTORY.relative_to(BASE).as_posix(),
        "updatedAt": time.time(),
        **extra,
    }
    if max_restarts is not None and restart_window is not None:
        payload["restartPolicy"] = {"maxRestarts": max_restarts, "windowSec": restart_window}
    return payload


def supervise(host: str, port: int, max_restarts: int = 5, restart_window: int = 60) -> int:
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    generation = 0
    restart_times: deque[float] = deque()
    child: subprocess.Popen | None = None
    _event("SUPERVISOR_STARTED", {"serviceId": "service://wbos/action-server", "supervisorPid": os.getpid(), "host": host, "port": port, "maxRestarts": max_restarts, "restartWindowSec": restart_window})

    while not STOP:
        generation += 1
        child = _spawn(host, port)
        started = _state(generation=generation, child=child, host=host, port=port, observed="STARTING", max_restarts=max_restarts, restart_window=restart_window)
        started["historyRow"] = _event("CHILD_STARTED", {"generation": generation, "childPid": child.pid, "host": host, "port": port})
        _write_state(started)

        while not STOP and child.poll() is None:
            running = _state(generation=generation, child=child, host=host, port=port, observed="RUNNING", max_restarts=max_restarts, restart_window=restart_window)
            _write_state(running)
            time.sleep(1.0)

        if STOP:
            break

        exit_code = child.returncode
        now = time.time()
        restart_times.append(now)
        while restart_times and now - restart_times[0] > restart_window:
            restart_times.popleft()
        exit_row = _event("CHILD_EXITED", {"generation": generation, "childPid": child.pid, "exitCode": exit_code, "restartCountInWindow": len(restart_times)})

        if len(restart_times) > max_restarts:
            failed = _state(generation=generation, child=child, host=host, port=port, observed="FAILED_RESTART_INTENSITY", max_restarts=max_restarts, restart_window=restart_window, exitCode=exit_code, restartCountInWindow=len(restart_times), historyRow=exit_row)
            _write_state(failed)
            _event("SUPERVISOR_ESCALATED", {"generation": generation, "exitCode": exit_code, "reason": "restart_intensity_exceeded", "restartCountInWindow": len(restart_times)})
            return 70

        restarting = _state(generation=generation, child=child, host=host, port=port, observed="RESTARTING", max_restarts=max_restarts, restart_window=restart_window, exitCode=exit_code, restartCountInWindow=len(restart_times), historyRow=exit_row)
        _write_state(restarting)
        _event("CHILD_RESTART_SCHEDULED", {"generation": generation, "nextGeneration": generation + 1, "restartCountInWindow": len(restart_times)})
        time.sleep(min(2 ** min(len(restart_times), 4), 10))

    if child is not None and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)

    stopped = _state(generation=generation, child=child, host=host, port=port, observed="STOPPED", desired="STOPPED")
    stopped["historyRow"] = _event("SUPERVISOR_STOPPED", {"generation": generation, "childPid": child.pid if child else None})
    _write_state(stopped)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--max-restarts", type=int, default=5)
    parser.add_argument("--restart-window", type=int, default=60)
    args = parser.parse_args()
    raise SystemExit(supervise(args.host, args.port, args.max_restarts, args.restart_window))
