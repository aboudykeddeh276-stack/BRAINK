from __future__ import annotations

import json
import os
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from runtime.signal_fabric import SignalRequest, SignalRuntime, default_mutation_handler

STATE_DIR = Path(os.getenv("KEX_SIGNAL_STATE_DIR", "/tmp/kex-signal-fabric"))
RUNTIME = SignalRuntime(STATE_DIR / "state.json", STATE_DIR / "last_receipt.json")
RUNTIME.register("STATE_PATCH", default_mutation_handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "KEXSignal/1.0"

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._send(200, {"status": "ok", "abi": "kex.signal/1", "grammar": ["VERIFY", "ADDRESS", "PROPAGATE", "EXECUTE", "COMMIT", "RECEIPT"]})
            return
        self._send(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/propagate":
            self._send(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = json.loads(self.rfile.read(length).decode("utf-8"))
            req = SignalRequest(
                signal_id=raw["signal_id"], source=raw["source"], target=raw["target"], operation=raw["operation"],
                state_hash_before=raw["state_hash_before"], compiled_payload=raw["compiled_payload"],
                invariants=tuple(raw.get("invariants", [])), authority=raw["authority"], sequence=int(raw["sequence"]),
                proof_root=raw["proof_root"], abi=raw.get("abi", "kex.signal/1"),
            )
            receipt = RUNTIME.execute(req)
            self._send(200, asdict(receipt))
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send(409, {"error": type(exc).__name__, "detail": str(exc)})

    def log_message(self, fmt: str, *args) -> None:
        if os.getenv("KEX_SIGNAL_QUIET") != "1":
            super().log_message(fmt, *args)


def main() -> None:
    host = os.getenv("KEX_SIGNAL_HOST", "127.0.0.1")
    port = int(os.getenv("KEX_SIGNAL_PORT", "18033"))
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
