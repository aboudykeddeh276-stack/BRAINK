#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

OS_NAME = "KEX-WBOS Cascade OS"
PORT = 8765
ROOT_URI = "KEX://ROOT/OS"
CASCADE_ORDER = [
    "MOUNT",
    "VERIFY_ALL",
    "HYDRATE_INDEXEDDB",
    "RESOLVE_KEX_URI",
    "PROJECT_UI",
    "DISPATCH_TRIGGER",
    "MUTATE_STATE",
    "WRITEBACK",
    "PROOF_COMMIT",
    "REHYDRATE_ON_FAILURE",
]

BASE = Path(__file__).resolve().parents[2]
LEDGER = BASE / "reports" / "kex-wbos" / "proof-ledger.jsonl"

SERVICES = [
    {"service": "apex", "route": "/", "port": PORT, "role": "K.0 apex projection"},
    {"service": "hybrid-os", "route": "/hybrid-os", "port": PORT, "role": "hybrid OS projection"},
    {"service": "health", "route": "/api/health", "port": PORT, "role": "runtime health"},
    {"service": "resolver", "route": "/api/resolve", "port": PORT, "role": "KEX URI resolution"},
    {"service": "proof-ledger", "route": "/api/proof-ledger", "port": PORT, "role": "proof readback"},
]

ROUTES = [
    {"host": "127.0.0.1", "path": "/", "target": "wbos.apex", "kex": ROOT_URI},
    {"host": "127.0.0.1", "path": "/hybrid-os", "target": "wbos.hybrid", "kex": "KEX://ROOT/HYBRID_OS"},
    {"host": "127.0.0.1", "path": "/api/health", "target": "wbos.health", "kex": "KEX://ROOT/OS/HEALTH"},
    {"host": "127.0.0.1", "path": "/api/services", "target": "wbos.services", "kex": "KEX://ROOT/OS/SERVICES"},
    {"host": "127.0.0.1", "path": "/api/routes", "target": "wbos.routes", "kex": "KEX://ROOT/OS/ROUTES"},
    {"host": "127.0.0.1", "path": "/mesh", "target": "braink.mesh", "kex": "KEX://BRAINK/MESH"},
    {"host": "127.0.0.1", "path": "/cascade", "target": "wbos.cascade", "kex": "KEX://ROOT/OS/CASCADE"},
]
ROUTE_BY_KEX = {row["kex"].upper(): row for row in ROUTES}


def append_proof(event: str, target: str, value: str, actor: str = "kex-wbos") -> dict:
    entry = {"ts": time.time(), "event": event, "target": target, "value": value, "actor": actor}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def read_proofs(limit: int = 100) -> list[dict]:
    if not LEDGER.exists():
        return []
    rows = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def resolve_kex(uri: str) -> dict:
    normalized = (uri or ROOT_URI).strip().upper()
    route = ROUTE_BY_KEX.get(normalized)
    if route:
        return {"found": True, "type": "route", **route}
    return {"found": False, "type": "unresolved", "target": None, "kex": normalized}


def mesh_status() -> dict:
    # This is registry state, not a claim that external mesh nodes are online.
    return {
        "braink_mesh": "configured",
        "nodes": ["wbos-local"],
        "state": "LOCAL_REGISTRY_ONLY",
    }


def cascade_info() -> dict:
    return {
        "root": ROOT_URI,
        "order": CASCADE_ORDER,
        "children": [s["service"] for s in SERVICES],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "KEX-WBOS/1.0"

    def _json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, title: str, body_text: str) -> None:
        body = f"<!doctype html><html><head><title>{title}</title></head><body><main><h1>{title}</h1><p>{body_text}</p></main></body></html>".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            append_proof("PROJECT_UI", "wbos.apex", "rendered")
            return self._html("KEX K.0 Apex", "KEX-WBOS local apex projection.")
        if path == "/hybrid-os":
            append_proof("PROJECT_UI", "wbos.hybrid", "rendered")
            return self._html("KEX Hybrid OS", "Hybrid OS local projection.")
        if path == "/api/health":
            proof = append_proof("HEALTH_READ", ROOT_URI, "ok")
            return self._json({"status": "ok", "os": OS_NAME, "cascade_order": CASCADE_ORDER, "proof": proof})
        if path == "/api/services":
            append_proof("SERVICE_LIST_READ", ROOT_URI, str(len(SERVICES)))
            return self._json({"services": SERVICES})
        if path == "/api/routes":
            append_proof("ROUTE_LIST_READ", ROOT_URI, str(len(ROUTES)))
            return self._json({"routes": ROUTES})
        if path == "/api/resolve":
            uri = parse_qs(parsed.query).get("uri", [ROOT_URI])[0]
            result = resolve_kex(uri)
            append_proof("RESOLVE_KEX_URI", uri, "found" if result["found"] else "unresolved")
            return self._json({"uri": uri, "result": result})
        if path == "/mesh":
            append_proof("MESH_STATUS_READ", "braink.mesh", "local-registry")
            return self._json(mesh_status())
        if path == "/cascade":
            append_proof("CASCADE_READ", ROOT_URI, str(len(CASCADE_ORDER)))
            return self._json(cascade_info())
        if path == "/api/proof-ledger":
            return self._json({"entries": read_proofs(100)})
        return self._json({"error": "not_found", "path": path}, 404)


def serve(host: str = "127.0.0.1", port: int = PORT) -> None:
    append_proof("WBOS_BOOT", ROOT_URI, f"{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    serve()
