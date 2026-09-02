from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import argparse
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise.recursive_computer_runtime_r26 import RecursiveComputer
from runtime.R25.system_evolution_runtime import sha256_json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class RuntimeHost:
    def __init__(self, state_root: str | Path, computer_id: str = "A"):
        self.state_root = Path(state_root)
        self.state_root.mkdir(parents=True, exist_ok=True)
        computer_file = self.state_root / "computer.json"
        self.computer = RecursiveComputer.restore_tree(self.state_root) if computer_file.exists() else RecursiveComputer(computer_id=computer_id, state_root=self.state_root)

    def refresh(self):
        self.computer = RecursiveComputer.restore_tree(self.state_root)
        return self.computer

    def snapshot(self):
        rb = self.computer.readback()
        return {
            "status": "RUNNING",
            "computer_id": self.computer.identity.computer_id,
            "generation": self.computer.identity.generation,
            "lineage": list(self.computer.identity.lineage),
            "constructor_id": self.computer.identity.constructor_id,
            "state_root": sha256_json(rb),
            "state": rb["state"],
            "memory": rb["memory"],
            "children": rb["children"],
            "ledger_verified": self.computer.ledger.verify(),
            "ledger_events": len(self.computer.ledger.events),
        }

    def instantiate(self, child_id: str):
        child = self.computer.instantiate(child_id)
        rb = child.readback()
        return {
            "status": "SUCCESSOR_CREATED",
            "computer_id": child.identity.computer_id,
            "lineage": list(child.identity.lineage),
            "constructor_id": child.identity.constructor_id,
            "state_root": sha256_json(rb),
            "memory": rb["memory"],
        }

    def write_memory(self, key, value):
        self.computer.write_memory(key, value)
        return self.snapshot()

    def write_state(self, key, value):
        self.computer.write_state(key, value)
        return self.snapshot()

    def restore(self):
        self.refresh()
        return {"status": "RESTORED", **self.snapshot()}


class Handler(BaseHTTPRequestHandler):
    host_runtime: RuntimeHost | None = None

    def reply(self, code, value):
        raw = canonical(value)
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def body(self):
        size = int(self.headers.get("Content-Length", "0") or "0")
        return json.loads(self.rfile.read(size) or b"{}")

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/health":
                snap = self.host_runtime.snapshot()
                return self.reply(200, {
                    "status": "PASS",
                    "runtime": "BRAINK_RECURSIVE_COMPUTER_R26",
                    "constructor_id": snap["constructor_id"],
                    "computer_id": snap["computer_id"],
                    "state_root": snap["state_root"],
                    "ledger_verified": snap["ledger_verified"],
                })
            if path == "/state":
                return self.reply(200, self.host_runtime.snapshot())
            return self.reply(404, {"status": "NOT_FOUND"})
        except Exception as exc:
            return self.reply(500, {"status": "ERROR", "error": type(exc).__name__ + ":" + str(exc)})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self.body()
            if path == "/instantiate":
                return self.reply(200, self.host_runtime.instantiate(body["child_id"]))
            if path == "/memory":
                return self.reply(200, self.host_runtime.write_memory(body["key"], body.get("value")))
            if path == "/state":
                return self.reply(200, self.host_runtime.write_state(body["key"], body.get("value")))
            if path == "/restore":
                return self.reply(200, self.host_runtime.restore())
            return self.reply(404, {"status": "NOT_FOUND"})
        except (KeyError, ValueError) as exc:
            return self.reply(400, {"status": "REJECTED", "reason": str(exc)})
        except Exception as exc:
            return self.reply(409 if "STALE_STATE_CONFLICT" in str(exc) else 500, {"status": "ERROR", "error": type(exc).__name__ + ":" + str(exc)})

    def log_message(self, *_):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-root", required=True)
    ap.add_argument("--computer-id", default=os.getenv("BRAINK_COMPUTER_ID", "A"))
    ap.add_argument("--host", default=os.getenv("BRAINK_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.getenv("BRAINK_PORT", "8811")))
    args = ap.parse_args()
    Handler.host_runtime = RuntimeHost(args.state_root, args.computer_id)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
