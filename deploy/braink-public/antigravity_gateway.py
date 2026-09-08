#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import socket
import stat
import http.server

ORCHESTRATOR_SOCKET = os.environ.get("BRAINK_ORCHESTRATOR_SOCKET", "/tmp/braink-orchestrator.sock")
BIND = os.environ.get("BRAINK_ANTIGRAVITY_BIND", "127.0.0.1")
PORT = int(os.environ.get("BRAINK_ANTIGRAVITY_PORT", "8800"))
PROTOCOL = "braink.adapter.v1"
RUNTIME = "runtime://braink/antigravity-gateway/1"


def socket_ready(path: str) -> bool:
    try:
        return stat.S_ISSOCK(os.stat(path).st_mode)
    except OSError:
        return False


def orchestrator_call(envelope: dict) -> dict:
    if not socket_ready(ORCHESTRATOR_SOCKET):
        raise RuntimeError(f"BRAINK_ORCHESTRATOR_SOCKET_NOT_READY:{ORCHESTRATOR_SOCKET}")
    payload = {
        "op": "DISPATCH",
        "authority": "braink://local/orchestrator",
        "semantic_traversal": "illlm://local/traversal",
        "addressing": "kex://local/addressing",
        "execution": "kex://local/execution",
        "vfs": "vfs://kex/root",
        "memory": "memory://braink/session",
        "proof": "ledger://braink/proof",
        "envelope": envelope,
    }
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(float(os.environ.get("BRAINK_ANTIGRAVITY_TIMEOUT", "30")))
    s.connect(ORCHESTRATOR_SOCKET)
    try:
        s.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        if not buf:
            raise RuntimeError("EMPTY_BRAINK_ORCHESTRATOR_RESPONSE")
        result = json.loads(buf.decode())
    finally:
        s.close()
    if result.get("correlation_id") not in (None, envelope["correlation_id"]):
        raise RuntimeError("BRAINK_CORRELATION_MISMATCH")
    if result.get("status") in ("COMPLETED", "PASS", "OK") and not result.get("proof"):
        raise RuntimeError("BRAINK_COMPLETION_WITHOUT_PROOF")
    return result


def validate_envelope(data: dict) -> None:
    if data.get("protocol") != PROTOCOL:
        raise ValueError("INVALID_PROTOCOL")
    if data.get("kind") != "intent":
        raise ValueError("INVALID_KIND")
    if not isinstance(data.get("correlation_id"), str) or not data["correlation_id"].strip():
        raise ValueError("MISSING_CORRELATION_ID")
    if not isinstance(data.get("intent"), str) or not data["intent"].strip():
        raise ValueError("MISSING_INTENT")


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "BRAINKAntigravity/1"

    def reply(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            ready = socket_ready(ORCHESTRATOR_SOCKET)
            return self.reply(200 if ready else 503, {
                "status": "PASS" if ready else "BLOCKED",
                "runtime": RUNTIME,
                "protocol": PROTOCOL,
                "orchestrator": "braink://local/orchestrator",
                "orchestrator_socket_ready": ready,
            })
        return self.reply(404, {"status": "NOT_FOUND"})

    def do_POST(self):
        if self.path != "/braink/dispatch":
            return self.reply(404, {"status": "NOT_FOUND"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(n) or b"{}")
            validate_envelope(data)
            result = orchestrator_call(data)
            result.setdefault("correlation_id", data["correlation_id"])
            return self.reply(200, result)
        except ValueError as exc:
            return self.reply(400, {"status": "REJECTED", "error": str(exc)})
        except Exception as exc:
            return self.reply(503, {"status": "BLOCKED", "component": RUNTIME, "error": str(exc)})


if __name__ == "__main__":
    http.server.ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()
