#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from braink_runtime.process_engine import ExecutionContract, ProcessEngine, make_receipt

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv("BRAINK_DATA_DIR", str(ROOT / "data")))
AUTHORITY = os.getenv("BRAINK_OPERATOR_AUTHORITY", "USER_OPERATOR")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_workstation() -> tuple[Path, str]:
    raw = os.getenv("BRAINK_WORKSTATION_HTML", "").strip()
    if not raw:
        raise RuntimeError("BLOCKED:BRAINK_WORKSTATION_HTML_UNBOUND")
    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        raise RuntimeError(f"BLOCKED:WORKSTATION_HTML_NOT_FOUND:{path}")
    digest = sha256_file(path)
    expected = os.getenv("BRAINK_WORKSTATION_SHA256", "").strip().lower()
    if expected and digest.lower() != expected:
        raise RuntimeError(f"FAILED:WORKSTATION_SHA256_MISMATCH:{digest}")
    return path, digest


class WorkstationState:
    def __init__(self, path: Path, digest: str) -> None:
        self.path = path
        self.digest = digest
        self.started_ns = time.time_ns()
        self.request_count = 0


class Handler(BaseHTTPRequestHandler):
    server_version = "BRAINKWorkstation/1.0"

    def _json(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        state: WorkstationState = self.server.workstation_state  # type: ignore[attr-defined]
        state.request_count += 1
        route = urlparse(self.path).path
        if route == "/healthz":
            self._json(200, {
                "schema": "braink.workstation.health.v1",
                "status": "PASS",
                "authority": AUTHORITY,
                "workstation": state.path.name,
                "sha256": state.digest,
                "requests": state.request_count,
                "uptime_ns": time.time_ns() - state.started_ns,
            })
            return
        if route not in {"/", "/index.html"}:
            self._json(404, {"status": "NOT_FOUND", "path": route})
            return
        payload = state.path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-BRAINK-Workstation-SHA256", state.digest)
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        return


def start_server(path: Path, digest: str) -> tuple[ThreadingHTTPServer, str, str]:
    host = os.getenv("BRAINK_WORKSTATION_BIND", "127.0.0.1")
    raw_port = os.getenv("BRAINK_WORKSTATION_PORT", "0").strip() or "0"
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise RuntimeError(f"FAILED:INVALID_PORT:{raw_port}") from exc
    if not 0 <= port <= 65535:
        raise RuntimeError(f"FAILED:INVALID_PORT:{port}")

    server = ThreadingHTTPServer((host, port), Handler)
    server.workstation_state = WorkstationState(path, digest)  # type: ignore[attr-defined]
    actual_host, actual_port = server.server_address[:2]
    url = f"http://{actual_host}:{actual_port}/"
    health = f"http://{actual_host}:{actual_port}/healthz"
    return server, url, health


def _boot_capability(contract: ExecutionContract):
    started = time.time_ns()
    try:
        path, digest = resolve_workstation()
        server, url, health = start_server(path, digest)
    except RuntimeError as exc:
        text = str(exc)
        status = "BLOCKED" if text.startswith("BLOCKED:") else "FAIL"
        return make_receipt(contract, status=status, started_ns=started, observed={"status": text})

    thread = threading.Thread(target=server.serve_forever, name="braink-workstation", daemon=True)
    thread.start()

    actual_host, actual_port = server.server_address[:2]
    DATA.mkdir(parents=True, exist_ok=True)
    observed = {
        "status": "WORKSTATION_SERVICE_RUNNING",
        "authority": AUTHORITY,
        "target": contract.target,
        "html": str(path),
        "sha256": digest,
        "bind": actual_host,
        "port": actual_port,
        "url": url,
        "health": health,
        "pid": os.getpid(),
    }
    receipt_path = DATA / "workstation_service_receipt.json"
    receipt_path.write_text(json.dumps({"schema": "braink.workstation.service.receipt.v1", **observed}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if contract.payload.get("open_browser", False):
        webbrowser.open(url)
    receipt = make_receipt(contract, status="PASS", started_ns=started, observed=observed)
    receipt._server = server  # type: ignore[attr-defined]
    return receipt


def build_transition(open_browser: bool = False):
    engine = ProcessEngine()
    engine.register_capability("BOOT_RESIDENT_WORKSTATION", _boot_capability)
    contract = ExecutionContract(
        contract_id=f"workstation-{uuid.uuid4().hex}",
        state="WORKSTATION_BOOT",
        authority=AUTHORITY,
        target="BRAINK_RESIDENT_HTML_WORKSTATION",
        capability="BOOT_RESIDENT_WORKSTATION",
        payload={"open_browser": open_browser},
    )
    return engine.execute(contract)


def main() -> int:
    parser = argparse.ArgumentParser(description="BRAINK resident workstation service")
    parser.add_argument("--open", action="store_true", dest="open_browser", help="open the workstation URL in the default browser")
    parser.add_argument("--probe", action="store_true", help="validate workstation binding/hash without keeping a service alive")
    args = parser.parse_args()

    if args.probe:
        try:
            path, digest = resolve_workstation()
        except RuntimeError as exc:
            print(json.dumps({"schema": "braink.workstation.probe.v1", "status": str(exc)}, indent=2, sort_keys=True))
            return 1
        print(json.dumps({
            "schema": "braink.workstation.probe.v1",
            "status": "PASS",
            "authority": AUTHORITY,
            "html": str(path),
            "sha256": digest,
        }, indent=2, sort_keys=True))
        return 0

    transition = build_transition(open_browser=args.open_browser)
    print(json.dumps(transition, indent=2, sort_keys=True))
    if transition["receipt"]["status"] != "PASS":
        return 1
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
