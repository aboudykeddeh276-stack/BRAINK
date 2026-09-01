#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from hardening import constant_time_bearer_matches, require_secure_bind
from illlm_higher_order import build_topology
from illlm_hydrator import apply_delta, hydrate_recursive_runtime

BASE = Path(__file__).resolve().parents[2]
STATE_DIR = BASE / "runtime" / "illlm"
DELTA_FILE = STATE_DIR / "pending-delta.json"


class RuntimeHolder:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.runtime = hydrate_recursive_runtime(build_topology())
        self.loaded_at = time.time()
        self.last_delta: dict[str, Any] | None = None

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            snap = self.runtime.snapshot()
            snap["loadedAt"] = self.loaded_at
            snap["lastDelta"] = self.last_delta
            return snap

    def query(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return self.runtime.compile_context_plan(
                str(payload.get("query", "")),
                role=payload.get("role"),
                within=payload.get("within"),
                require_execution=bool(payload.get("requireExecution", False)),
            )

    def traverse(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return self.runtime.shortest_traversal(
                str(payload["source"]),
                str(payload["target"]),
                executable_only=bool(payload.get("executableOnly", False)),
            )

    def delta(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            result = apply_delta(self.runtime, payload)
            self.last_delta = {"at": time.time(), **result}
            return result

    def rebuild(self) -> dict[str, Any]:
        with self.lock:
            previous = self.runtime.graph_hash()
            self.runtime = hydrate_recursive_runtime(build_topology())
            self.loaded_at = time.time()
            return {
                "status": "REBUILT",
                "previousGraphHash": previous,
                "graphHash": self.runtime.graph_hash(),
                "nodeCount": len(self.runtime.nodes),
                "generation": self.runtime.generation,
            }


HOLDER = RuntimeHolder()


class Handler(BaseHTTPRequestHandler):
    server_version = "KEX-ILLLM/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _auth_ok(self) -> bool:
        expected = os.getenv("KEX_BEARER_TOKEN", "")
        if not expected:
            return True
        return constant_time_bearer_matches(self.headers.get("Authorization"), expected)

    def _json(self, status: int, body: Any) -> None:
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > int(os.getenv("KEX_ILLLM_MAX_REQUEST_BYTES", "1048576")):
            raise ValueError("request_too_large")
        raw = self.rfile.read(length) if length else b"{}"
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("object_required")
        return value

    def do_GET(self) -> None:
        if self.path in {"/health", "/snapshot"}:
            if not self._auth_ok():
                self._json(401, {"status": "UNAUTHORIZED"}); return
            snap = HOLDER.snapshot()
            self._json(200, {"status": "ok", "service": "service://illlm/recursive-runtime", **snap})
            return
        self._json(404, {"status": "NOT_FOUND"})

    def do_POST(self) -> None:
        if not self._auth_ok():
            self._json(401, {"status": "UNAUTHORIZED"}); return
        try:
            payload = self._body()
            if self.path == "/query":
                self._json(200, HOLDER.query(payload)); return
            if self.path == "/traverse":
                self._json(200, HOLDER.traverse(payload)); return
            if self.path == "/delta":
                self._json(200, HOLDER.delta(payload)); return
            if self.path == "/rebuild":
                self._json(200, HOLDER.rebuild()); return
            self._json(404, {"status": "NOT_FOUND"})
        except (KeyError, ValueError) as exc:
            self._json(400, {"status": "REJECTED", "error": type(exc).__name__, "message": str(exc)})
        except Exception as exc:
            self._json(500, {"status": "FAIL", "error": type(exc).__name__})


def serve(host: str = "127.0.0.1", port: int = 8791) -> None:
    require_secure_bind(host, os.getenv("KEX_BEARER_TOKEN"))
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("KEX_ILLLM_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("KEX_ILLLM_PORT", "8791")))
    args = parser.parse_args()
    serve(args.host, args.port)
