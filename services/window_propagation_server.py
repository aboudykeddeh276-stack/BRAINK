from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.window_propagation import WindowPropagationLedger, WindowPropagationRuntime, WindowSignal

STATE = Path(os.environ.get("BRAINK_PROPAGATION_LEDGER", ROOT / "state" / "window-propagation.sqlite3"))
HOST = os.environ.get("BRAINK_PROPAGATION_HOST", "127.0.0.1")
PORT = int(os.environ.get("BRAINK_PROPAGATION_PORT", "18771"))
RUNTIME = WindowPropagationRuntime(WindowPropagationLedger(STATE))


class Handler(BaseHTTPRequestHandler):
    server_version = "BRAINKWindowPropagation/1.0"

    def _send(self, status: int, payload: dict):
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            return self._send(200, {"status": "ok", "service": "window-propagation"})
        if self.path.startswith("/v1/replay/"):
            work_id = self.path.removeprefix("/v1/replay/")
            value = RUNTIME.replay(work_id)
            return self._send(200 if value else 404, {"status": "ok" if value else "not_found", "frame": value})
        return self._send(404, {"status": "not_found"})

    def do_POST(self):
        if self.path != "/v1/compile":
            return self._send(404, {"status": "not_found"})
        try:
            length = int(self.headers.get("content-length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            signals = [WindowSignal(**item) for item in body.get("signals", [])]
            frame = RUNTIME.compile(str(body["work_id"]), int(body["sequence"]), signals)
            return self._send(201, {"status": "compiled", "frame": frame.__dict__ | {"signals": [s.__dict__ for s in frame.signals]}})
        except Exception as exc:
            return self._send(400, {"status": "rejected", "error_type": type(exc).__name__, "error": str(exc)})

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
