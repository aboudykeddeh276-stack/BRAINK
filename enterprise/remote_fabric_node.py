from __future__ import annotations

"""Minimal independently-routable BRAINK fabric node.

This service is intentionally narrow. It does not pretend that HTTP is BRAINK identity
or that a tunnel is the machine. It exposes a concrete transport interface for a
logical BRAINK machine identity and produces a signed fabric-join receipt.

Boundary model:
    logical BRAINK node identity
        -> HTTP service interface
        -> TCP listener
        -> public tunnel/carrier
        -> remote fabric peer

The service signs each join receipt with an ephemeral host key generated on the
independent machine. The fabric peer verifies that signature against the public key
advertised by the same remote node identity.
"""

import argparse
import base64
import hashlib
import json
import os
import platform
import socket
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def machine_material() -> str:
    parts = [socket.gethostname(), platform.platform(), platform.machine()]
    machine_id = Path("/etc/machine-id")
    if machine_id.exists():
        parts.append(machine_id.read_text("utf-8").strip())
    return "|".join(parts)


class FabricNodeState:
    def __init__(self, *, commit_sha: str, run_id: str, private_key: Path, public_key: Path, receipt_path: Path):
        self.commit_sha = commit_sha
        self.run_id = run_id
        self.private_key = private_key
        self.public_key = public_key
        self.receipt_path = receipt_path
        self.public_key_pem = public_key.read_text("utf-8")
        self.public_key_sha256 = sha256_bytes(self.public_key_pem.encode("utf-8"))
        seed = f"{run_id}|{commit_sha}|{machine_material()}".encode("utf-8")
        self.node_id = "BRAINK-REMOTE-" + hashlib.sha256(seed).hexdigest()[:24]
        self.started_ns = time.time_ns()

    def identity(self) -> dict[str, Any]:
        return {
            "schema": "braink.remote-fabric-node.identity.v1",
            "node_id": self.node_id,
            "commit_sha": self.commit_sha,
            "run_id": self.run_id,
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "pid": os.getpid(),
            "started_ns": self.started_ns,
            "public_key_sha256": self.public_key_sha256,
            "public_key_pem": self.public_key_pem,
            "interfaces": ["http/tcp", "fabric/join/challenge-response"],
        }

    def sign(self, payload: dict[str, Any]) -> str:
        proc = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private_key)],
            input=canonical(payload),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return base64.b64encode(proc.stdout).decode("ascii")

    def join(self, request: dict[str, Any], peer_ip: str) -> dict[str, Any]:
        fabric_node_id = str(request.get("fabric_node_id") or "").strip()
        challenge = str(request.get("challenge") or "").strip()
        if not fabric_node_id or not challenge:
            raise ValueError("fabric_node_id and challenge are required")
        receipt = {
            "schema": "braink.remote-fabric-node.join-receipt.v1",
            "remote_node_id": self.node_id,
            "fabric_node_id": fabric_node_id,
            "challenge": challenge,
            "commit_sha": self.commit_sha,
            "run_id": self.run_id,
            "peer_ip": peer_ip,
            "joined_ns": time.time_ns(),
            "transport": "http-over-tcp-public-carrier",
            "public_key_sha256": self.public_key_sha256,
        }
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        with self.receipt_path.open("a", encoding="utf-8") as fh:
            fh.write(canonical(receipt).decode("utf-8") + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return {"receipt": receipt, "signature_b64": self.sign(receipt)}


class Handler(BaseHTTPRequestHandler):
    state: FabricNodeState

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        raw = canonical(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(200, {"status": "OK", "node_id": self.state.node_id})
            return
        if self.path == "/identity":
            self._json(200, self.state.identity())
            return
        self._json(404, {"status": "NOT_FOUND"})

    def do_POST(self) -> None:
        if self.path != "/fabric/join":
            self._json(404, {"status": "NOT_FOUND"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            result = self.state.join(body, self.client_address[0])
        except Exception as exc:
            self._json(400, {"status": "REJECTED", "reason": str(exc)})
            return
        self._json(200, {"status": "JOINED", **result})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"remote-node {self.address_string()} {fmt % args}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, default=Path("build/remote-fabric-join-receipts.jsonl"))
    args = parser.parse_args()

    state = FabricNodeState(
        commit_sha=args.commit,
        run_id=args.run_id,
        private_key=args.private_key,
        public_key=args.public_key,
        receipt_path=args.receipts,
    )
    Handler.state = state
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(json.dumps({"status": "LISTENING", **state.identity(), "bind": [args.host, args.port]}, sort_keys=True), flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
