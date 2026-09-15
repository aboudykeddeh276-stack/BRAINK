from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "r40-process-restart-token-0123456789abcdef"


def free_port():
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close(); return port


def request(port, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = Request(
        f"http://127.0.0.1:{port}{path}", data=data,
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urlopen(req, timeout=3) as response:
        return response.status, json.loads(response.read())


def start(state, port):
    env = {**os.environ, "KEX_AUTH_TOKEN": TOKEN, "PYTHONPATH": str(ROOT)}
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "deployment" / "kex_runtime_service_r40.py"),
         "--state-root", str(state), "--computer-id", "A", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    deadline = time.time() + 10
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("R40_PROCESS_EXITED_EARLY:" + (proc.stdout.read() if proc.stdout else ""))
        try:
            status, body = request(port, "/readyz")
            if status == 200 and body.get("status") == "READY": return proc
        except Exception:
            time.sleep(0.1)
    proc.terminate(); proc.wait(timeout=5)
    raise RuntimeError("R40_PROCESS_READINESS_TIMEOUT")


def stop(proc):
    proc.terminate()
    try: proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill(); proc.wait(timeout=5)


def main():
    command = {
        "source": "test://r40/process-restart",
        "data_class": "CORRECTION",
        "payload": {"restart": True},
        "authority": "authority://source/local",
        "capabilities": ["process", "readback"],
        "illlm": {"intent": "state.write", "lineage": "A", "key": "restart_marker", "value": "PERSISTED"},
    }
    with tempfile.TemporaryDirectory(prefix="braink-r40-restart-") as tmp:
        state = Path(tmp) / "state"; port = free_port()
        first = start(state, port)
        try:
            status, result = request(port, "/v1/canonical/execute", command)
            if status != 200 or result.get("readback", {}).get("state", {}).get("restart_marker") != "PERSISTED":
                raise RuntimeError("R40_PRE_RESTART_EXECUTION_FAILED:" + json.dumps(result, sort_keys=True))
        finally:
            stop(first)

        second = start(state, port)
        try:
            status, root = request(port, "/v1/root")
            if status != 200 or root.get("state", {}).get("restart_marker") != "PERSISTED":
                raise RuntimeError("R40_POST_RESTART_READBACK_FAILED:" + json.dumps(root, sort_keys=True))
            if not root.get("ledger_verified"):
                raise RuntimeError("R40_POST_RESTART_LEDGER_UNVERIFIED")
            status, canonical = request(port, "/v1/canonical/status")
            if status != 200 or canonical.get("runtime", {}).get("status") != "READY":
                raise RuntimeError("R40_POST_RESTART_NOT_READY:" + json.dumps(canonical, sort_keys=True))
            print(json.dumps({"status": "PASS", "restart_marker": root["state"]["restart_marker"],
                              "ledger_verified": root["ledger_verified"], "runtime": canonical["runtime"]}, sort_keys=True))
        finally:
            stop(second)


if __name__ == "__main__":
    main()
