from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import argparse
import hmac
import json
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise.recursive_computer_runtime_r26 import RecursiveComputer
from runtime.R25.system_evolution_runtime import sha256_json

MAX_BODY_BYTES = 1_048_576


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class RuntimeHost:
    def __init__(self, state_root, computer_id="A"):
        self.state_root = Path(state_root)
        self.state_root.mkdir(parents=True, exist_ok=True)
        self._tree_lock = threading.RLock()
        self.computer = (
            RecursiveComputer.restore_tree(self.state_root)
            if (self.state_root / "computer.json").exists()
            else RecursiveComputer(computer_id=computer_id, state_root=self.state_root)
        )

    def restore(self):
        with self._tree_lock:
            self.computer = RecursiveComputer.restore_tree(self.state_root)
            return self.snapshot(self.computer, "RESTORED")

    def resolve(self, lineage=None):
        with self._tree_lock:
            lineage = lineage or [self.computer.identity.computer_id]
            if isinstance(lineage, str):
                lineage = [x for x in lineage.strip("/").split("/") if x]
            if not lineage or lineage[0] != self.computer.identity.computer_id:
                raise ValueError("LINEAGE_ROOT_MISMATCH")
            node = self.computer
            for cid in lineage[1:]:
                RecursiveComputer._validate_id(cid, field="lineage_component")
                if cid not in node.children:
                    child_root = node.state_root / "descendants" / cid
                    if not (child_root / "computer.json").exists():
                        raise ValueError("COMPUTER_NOT_FOUND:" + cid)
                    node.children[cid] = RecursiveComputer.restore_tree(child_root)
                node = node.children[cid]
            return node

    def snapshot(self, node=None, status="RUNNING"):
        node = node or self.computer
        rb = node.readback()
        return {
            "status": status,
            "computer_id": node.identity.computer_id,
            "generation": node.identity.generation,
            "lineage": list(node.identity.lineage),
            "constructor_id": node.identity.constructor_id,
            "state_root": sha256_json(rb),
            "state": rb["state"],
            "memory": rb["memory"],
            "children": rb["children"],
            "ledger_verified": node.ledger.verify(),
            "ledger_events": len(node.ledger.events),
        }

    def topology(self):
        with self._tree_lock:
            nodes = []

            def walk(node):
                rb = node.readback()
                nodes.append(
                    {
                        "computer_id": node.identity.computer_id,
                        "generation": node.identity.generation,
                        "lineage": list(node.identity.lineage),
                        "children": list(rb["children"]),
                        "state_root": sha256_json(rb),
                        "ledger_verified": node.ledger.verify(),
                    }
                )
                for child_id in rb["children"]:
                    child = self.resolve(list(node.identity.lineage) + [child_id])
                    walk(child)

            walk(self.computer)
            max_generation = max((x["generation"] for x in nodes), default=0)
            return {
                "status": "PASS",
                "root": self.computer.identity.computer_id,
                "node_count": len(nodes),
                "max_generation": max_generation,
                "nodes": nodes,
            }

    def continuations(self, lineage=None):
        node = self.resolve(lineage)
        snap = node.runtime.snapshot()
        queue = snap.get("continuations", {})
        return {
            "status": "PASS",
            "lineage": list(node.identity.lineage),
            "queue_depth": len(queue),
            "continuations": queue,
            "history_count": len(snap.get("history", [])),
        }

    def checkpoint(self, lineage=None):
        node = self.resolve(lineage)
        return {
            "status": "CHECKPOINTED",
            "lineage": list(node.identity.lineage),
            "runtime": node.runtime.checkpoint(),
            "snapshot": self.snapshot(node),
        }

    def instantiate(self, parent_lineage, child_id):
        parent = self.resolve(parent_lineage)
        child = parent.instantiate(child_id)
        with self._tree_lock:
            parent.children[child.identity.computer_id] = child
        return self.snapshot(child, "SUCCESSOR_CREATED")

    def write_memory(self, lineage, key, value):
        node = self.resolve(lineage)
        node.write_memory(key, value)
        return self.snapshot(node)

    def write_state(self, lineage, key, value):
        node = self.resolve(lineage)
        node.write_state(key, value)
        return self.snapshot(node)

    def reconcile(self, lineage):
        node = self.resolve(lineage)
        result = node.reconcile_once()
        return {
            "status": "RECONCILED" if result.get("status") == "COMPLETED" else result.get("status"),
            "lineage": list(node.identity.lineage),
            "continuation": result,
            "snapshot": self.snapshot(node),
        }


class RuntimeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128


class Handler(BaseHTTPRequestHandler):
    host_runtime = None
    auth_token = None
    max_body_bytes = MAX_BODY_BYTES

    def reply(self, code, obj):
        body = canonical(obj)
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def authorized(self):
        if not self.auth_token:
            return True
        presented = self.headers.get("Authorization", "")
        if presented.startswith("Bearer "):
            presented = presented[7:]
        return hmac.compare_digest(presented, self.auth_token)

    def require_authorized(self):
        if self.authorized():
            return True
        self.reply(401, {"status": "REJECTED", "reason": "UNAUTHORIZED"})
        return False

    def body(self):
        raw_length = self.headers.get("Content-Length", "0") or "0"
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("INVALID_CONTENT_LENGTH") from exc
        if length < 0:
            raise ValueError("INVALID_CONTENT_LENGTH")
        if length > self.max_body_bytes:
            raise OverflowError("REQUEST_BODY_TOO_LARGE")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("INVALID_JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("JSON_OBJECT_REQUIRED")
        return value

    def do_GET(self):
        if not self.require_authorized():
            return
        url = urlparse(self.path)
        query = parse_qs(url.query)
        try:
            lineage = query.get("lineage", [None])[0]
            if url.path == "/health":
                snap = self.host_runtime.snapshot()
                return self.reply(
                    200,
                    {
                        "status": "PASS",
                        "runtime": "BRAINK_RECURSIVE_COMPUTER_R26",
                        "constructor_id": snap["constructor_id"],
                        "computer_id": snap["computer_id"],
                        "state_root": snap["state_root"],
                        "ledger_verified": snap["ledger_verified"],
                    },
                )
            if url.path == "/state":
                return self.reply(200, self.host_runtime.snapshot(self.host_runtime.resolve(lineage)))
            if url.path == "/topology":
                return self.reply(200, self.host_runtime.topology())
            if url.path == "/continuations":
                return self.reply(200, self.host_runtime.continuations(lineage))
            return self.reply(404, {"status": "NOT_FOUND"})
        except (KeyError, ValueError) as exc:
            return self.reply(404, {"status": "REJECTED", "reason": str(exc)})
        except Exception as exc:
            return self.reply(500, {"status": "ERROR", "error": type(exc).__name__ + ":" + str(exc)})

    def do_POST(self):
        if not self.require_authorized():
            return
        path = urlparse(self.path).path
        try:
            body = self.body()
            lineage = body.get("lineage")
            if path == "/instantiate":
                return self.reply(200, self.host_runtime.instantiate(lineage, body["child_id"]))
            if path == "/memory":
                return self.reply(200, self.host_runtime.write_memory(lineage, body["key"], body.get("value")))
            if path == "/state":
                return self.reply(200, self.host_runtime.write_state(lineage, body["key"], body.get("value")))
            if path == "/restore":
                return self.reply(200, self.host_runtime.restore())
            if path == "/reconcile":
                return self.reply(200, self.host_runtime.reconcile(lineage))
            if path == "/checkpoint":
                return self.reply(200, self.host_runtime.checkpoint(lineage))
            return self.reply(404, {"status": "NOT_FOUND"})
        except OverflowError as exc:
            return self.reply(413, {"status": "REJECTED", "reason": str(exc)})
        except (KeyError, ValueError) as exc:
            return self.reply(400, {"status": "REJECTED", "reason": str(exc)})
        except Exception as exc:
            code = 409 if "STALE_STATE_CONFLICT" in str(exc) else 500
            return self.reply(code, {"status": "ERROR", "error": type(exc).__name__ + ":" + str(exc)})

    def log_message(self, *_):
        pass


def load_auth_token(path):
    if not path:
        return None
    token = Path(path).read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise ValueError("AUTH_TOKEN_TOO_SHORT")
    return token


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--computer-id", default="A")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8811)
    parser.add_argument("--auth-token-file")
    parser.add_argument("--allow-unauthenticated-nonloopback", action="store_true")
    args = parser.parse_args()

    token = load_auth_token(args.auth_token_file)
    loopback_hosts = {"127.0.0.1", "::1", "localhost"}
    if args.host not in loopback_hosts and token is None and not args.allow_unauthenticated_nonloopback:
        raise SystemExit("NON_LOOPBACK_BIND_REQUIRES_AUTH_TOKEN_OR_EXPLICIT_OVERRIDE")

    Handler.host_runtime = RuntimeHost(args.state_root, args.computer_id)
    Handler.auth_token = token
    server = RuntimeServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
