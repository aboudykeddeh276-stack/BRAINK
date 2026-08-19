from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .braink_service import AuthorizationError, BRAINKService


class Handler(BaseHTTPRequestHandler):
    service: BRAINKService

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/v1/conversation/respond":
            self._json(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length) or b"{}")
            self._json(200, self.service.respond(request))
        except AuthorizationError as exc:
            self._json(403, {"error": "unauthorized_tool", "detail": str(exc)})
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": "invalid_request", "detail": str(exc)})
        except Exception as exc:
            self._json(500, {"error": "execution_failure", "detail": str(exc)})

    def do_GET(self) -> None:
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["v1", "trace"]:
            trace = self.service.trace(parts[2])
            self._json(200 if trace else 404, {"transaction_id": parts[2], "events": trace})
            return
        self._json(404, {"error": "not_found"})

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="BRAINK local proof-bearing service v1")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ledger", default=".braink/local-service-v1/evidence.jsonl")
    args = parser.parse_args()

    Handler.service = BRAINKService(Path(args.ledger))
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"BRAINK local service listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
