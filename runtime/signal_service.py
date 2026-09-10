from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from runtime.estate_signal_handlers import register_estate_handlers
from runtime.signal_fabric import SignalRequest, SignalRuntime, default_mutation_handler

STATE_DIR = Path(os.getenv("KEX_SIGNAL_STATE_DIR", "/tmp/kex-signal-fabric"))
_RUNTIME_LOCK = threading.RLock()
_RUNTIMES: dict[str, SignalRuntime] = {}


def _auth_token() -> str:
    token = os.getenv("KEX_SIGNAL_AUTH_TOKEN", "")
    if not token:
        raise RuntimeError("KEX_SIGNAL_AUTH_TOKEN must be configured")
    return token


def _target_key(target: str) -> str:
    if not target:
        raise ValueError("target required")
    return hashlib.sha256(target.encode("utf-8")).hexdigest()


def runtime_for_target(target: str) -> SignalRuntime:
    key = _target_key(target)
    with _RUNTIME_LOCK:
        runtime = _RUNTIMES.get(key)
        if runtime is None:
            root = STATE_DIR / "targets" / key
            runtime = SignalRuntime(root / "state.json", root / "last_receipt.json")
            runtime.register("STATE_PATCH", default_mutation_handler)
            register_estate_handlers(runtime)
            _RUNTIMES[key] = runtime
        return runtime


def operation_manifest() -> list[str]:
    probe = runtime_for_target("runtime://kex/manifest-probe")
    return sorted(probe.handlers)


class Handler(BaseHTTPRequestHandler):
    server_version = "KEXSignal/1.2"

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        expected = f"Bearer {_auth_token()}"
        return hmac.compare_digest(supplied, expected)

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._send(401, {"error": "unauthorized"})
        return False

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._send(200, {
                "status": "ok",
                "abi": "kex.signal/1",
                "grammar": ["VERIFY", "ADDRESS", "PROPAGATE", "EXECUTE", "COMMIT", "RECEIPT"],
                "operations": operation_manifest(),
                "target_partitioning": "sha256(target)",
                "authority_boundary": "bearer-authenticated local ingress",
            })
            return
        if parsed.path not in {"/v1/state", "/v1/receipt"}:
            self._send(404, {"error": "not_found"})
            return
        if not self._require_auth():
            return
        query = parse_qs(parsed.query)
        target = query.get("target", [""])[0]
        try:
            runtime = runtime_for_target(target)
            if parsed.path == "/v1/state":
                self._send(200, {"target": target, "state": runtime._read_state(), "head_receipt": runtime._previous_receipt()})
                return
            signal_id = query.get("signal_id", [""])[0]
            if not signal_id:
                self._send(400, {"error": "signal_id_required"})
                return
            receipt = runtime.get_receipt(signal_id)
            if receipt is None:
                self._send(404, {"error": "receipt_not_found", "signal_id": signal_id})
                return
            self._send(200, asdict(receipt))
        except (KeyError, ValueError, TypeError, RuntimeError) as exc:
            self._send(409, {"error": type(exc).__name__, "detail": str(exc)})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/propagate":
            self._send(404, {"error": "not_found"})
            return
        if not self._require_auth():
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
            receipt = runtime_for_target(req.target).execute(req)
            self._send(200, asdict(receipt))
        except (KeyError, ValueError, TypeError, RuntimeError, json.JSONDecodeError) as exc:
            self._send(409, {"error": type(exc).__name__, "detail": str(exc)})

    def log_message(self, fmt: str, *args) -> None:
        if os.getenv("KEX_SIGNAL_QUIET") != "1":
            super().log_message(fmt, *args)


def main() -> None:
    _auth_token()
    host = os.getenv("KEX_SIGNAL_HOST", "127.0.0.1")
    port = int(os.getenv("KEX_SIGNAL_PORT", "18033"))
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
