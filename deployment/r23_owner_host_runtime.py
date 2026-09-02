from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise.runtime.process_supervisor import ManagedProcess


@dataclass
class Readback:
    status: str
    health: dict[str, Any]
    state: dict[str, Any]
    pid: int | None


class R23OwnerHostRuntime:
    """Start and observe the existing R23 closure HTTP service on one host.

    This is a binding around the resident R23 service and resident ManagedProcess.
    Durable state is read directly from the owner-host state carrier; it is not
    exported through the HTTP service. This proves local process/service activation
    and durable restart rehydration only. It does not claim public ingress, DNS/TLS
    activation, or physical multi-host state.
    """

    def __init__(self, state_path: str | Path, host: str = "127.0.0.1", port: int = 8800):
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("R23_OWNER_HOST_BINDING_REQUIRES_LOOPBACK")
        self.state_path = Path(state_path).resolve()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.host = host
        self.port = int(port)
        self.base = f"http://{host}:{self.port}"
        self.process = ManagedProcess(
            "braink-r23-closure",
            [
                sys.executable,
                str(ROOT / "deployment" / "r23_foundry_closure_service.py"),
                "--state",
                str(self.state_path),
                "--host",
                host,
                "--port",
                str(self.port),
            ],
        )

    def _json(self, method: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 2.0) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        req = urllib.request.Request(
            self.base + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    def _local_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            raise RuntimeError("R23_LOCAL_STATE_CARRIER_MISSING")
        return json.loads(self.state_path.read_text("utf-8"))

    def wait_ready(self, timeout: float = 8.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: Exception | None = None
        while time.monotonic() < deadline:
            if not self.process.alive():
                raise RuntimeError("R23_PROCESS_EXITED_BEFORE_READY")
            try:
                health = self._json("GET", "/closure/health", timeout=0.75)
                if health.get("status") == "PASS" and health.get("runtime") == "BRAINK_R23":
                    return health
            except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
                last = exc
            time.sleep(0.05)
        raise RuntimeError(f"R23_HEALTH_READBACK_TIMEOUT:{last}")

    def start(self) -> Readback:
        pid = self.process.start()
        health = self.wait_ready()
        state = self._local_state()
        return Readback("EXECUTED", health, state, pid)

    def operate(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._json("POST", "/closure/operate", {"action": action, "payload": payload})

    def readback(self) -> Readback:
        health = self._json("GET", "/closure/health")
        state = self._local_state()
        return Readback("OBSERVED", health, state, self.process.proc.pid if self.process.proc else None)

    def public_state_summary(self) -> dict[str, Any]:
        return self._json("GET", "/closure/state")

    def restart_and_rehydrate(self) -> Readback:
        before = self.readback().state
        before_root = before.get("state_root")
        before_generation = before.get("generation")
        self.process.stop()
        if self.process.alive():
            raise RuntimeError("R23_PROCESS_FAILED_TO_STOP")
        after = self.start()
        if after.state.get("state_root") != before_root or after.state.get("generation") != before_generation:
            self.process.stop()
            raise RuntimeError("R23_REHYDRATION_STATE_MISMATCH")
        return after

    def stop(self) -> None:
        self.process.stop()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8800)
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    runtime = R23OwnerHostRuntime(args.state, args.host, args.port)
    try:
        started = runtime.start()
        output = {"status": started.status, "pid": started.pid, "health": started.health, "generation": started.state.get("generation"), "state_root": started.state.get("state_root")}
        if args.probe:
            output["rehydrated"] = runtime.restart_and_rehydrate().__dict__
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    finally:
        runtime.stop()


if __name__ == "__main__":
    raise SystemExit(main())
