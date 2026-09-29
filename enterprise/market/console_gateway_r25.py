from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import json
import os
import secrets
from pathlib import Path

from enterprise.market.service_fabric_r24 import MarketServiceFabric


class AuthenticatedConsoleGateway:
    def __init__(self, db_path: str | Path, token: str | None = None):
        self.store = MarketServiceFabric(db_path)
        self.token = token or os.environ.get("KEDDEH_CONSOLE_BEARER_TOKEN", "")
        if not self.token:
            raise RuntimeError("KEDDEH_CONSOLE_BEARER_TOKEN_REQUIRED")

    def handler(self):
        store = self.store
        expected = self.token

        class H(BaseHTTPRequestHandler):
            def _json(self, code, obj):
                raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _authorized(self):
                raw = self.headers.get("Authorization", "")
                if not raw.startswith("Bearer "):
                    return False
                return secrets.compare_digest(raw[7:], expected)

            def _require_auth(self):
                if self._authorized():
                    return True
                self._json(401, {"status": "UNAUTHORIZED"})
                return False

            def _body(self):
                n = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(n) if n else b"{}"
                return json.loads(raw or b"{}")

            def do_GET(self):
                if not self._require_auth():
                    return
                p = urlparse(self.path).path
                if p == "/health":
                    return self._json(200, {
                        "status": "OK",
                        "service": "KEDDEH_BRAINK_AUTHENTICATED_CONSOLE_GATEWAY",
                    })
                if p == "/runtime/status":
                    metrics = store.metrics()
                    return self._json(200, {
                        "status": "OBSERVED",
                        "runtime": "KEDDEH_SYSTEMS_MARKET_SERVICE_FABRIC_R24",
                        "metrics": metrics,
                    })
                if p == "/runtime/receipts":
                    with store.db() as db:
                        rows = db.execute(
                            "SELECT id,action,target_id,status,evidence_root,created_ns "
                            "FROM receipts ORDER BY created_ns DESC LIMIT 100"
                        ).fetchall()
                    return self._json(200, {
                        "status": "OBSERVED",
                        "receipts": [dict(r) for r in rows],
                    })
                if p == "/runtime/capabilities":
                    return self._json(200, {
                        "status": "OBSERVED",
                        "capabilities": [
                            "create_customer","create_workspace","write_artifact","create_site",
                            "put_page","publish_site","register_role","register_agent",
                            "create_work_module","assign_agent","deploy_server_set",
                            "metrics","receipts"
                        ]
                    })
                return self._json(404, {"status": "NOT_FOUND"})

            def do_POST(self):
                if not self._require_auth():
                    return
                p = urlparse(self.path).path
                if p != "/runtime/execute":
                    return self._json(404, {"status": "NOT_FOUND"})
                body = self._body()
                operation = body.get("operation")
                args = body.get("args") or {}
                operations = {
                    "create_customer": lambda: store.create_customer(args["name"], args.get("email")),
                    "create_workspace": lambda: store.create_workspace(args["customer_id"], args["name"]),
                    "write_artifact": lambda: store.write_artifact(args["workspace_id"], args["path"], args["content"]),
                    "create_site": lambda: store.create_site(args["customer_id"], args["name"], args["domain"], args.get("site_type", "WEBSITE")),
                    "put_page": lambda: store.put_page(args["site_id"], args["slug"], args["title"], args["body"]),
                    "publish_site": lambda: store.publish_site(args["site_id"]),
                    "register_role": lambda: store.register_role(args["name"], args["scope"], args.get("supervision_only", False)),
                    "register_agent": lambda: store.register_agent(args["name"], args["role_id"]),
                    "create_work_module": lambda: store.create_work_module(args["foundry"], args["function"], args["instruction"]),
                    "assign_agent": lambda: store.assign_agent(args["work_module_id"], args["agent_id"], args["supervisor_id"], args["group_name"], args["scope"]),
                    "deploy_server_set": lambda: store.deploy_server_set(args["business_id"], args["server_family"], args["replicas"], args["config"]),
                }
                fn = operations.get(operation)
                if fn is None:
                    return self._json(400, {"status": "REJECTED", "reason": "UNKNOWN_OPERATION"})
                try:
                    result = fn()
                    return self._json(200, {"status": "EXECUTED", "operation": operation, "result": result})
                except Exception as exc:
                    return self._json(400, {
                        "status": "REJECTED",
                        "operation": operation,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    })

            def log_message(self, *_):
                pass

        return H

    def serve(self, host="127.0.0.1", port=19621):
        ThreadingHTTPServer((host, port), self.handler()).serve_forever()


if __name__ == "__main__":
    AuthenticatedConsoleGateway("runtime/market_service_r24.sqlite3").serve(
        os.environ.get("KEDDEH_CONSOLE_HOST", "127.0.0.1"),
        int(os.environ.get("KEDDEH_CONSOLE_PORT", "19621")),
    )
