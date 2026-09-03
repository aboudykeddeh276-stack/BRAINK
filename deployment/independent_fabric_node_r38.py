from __future__ import annotations

import argparse
import hashlib
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from enterprise.recursive_computer_runtime_r26 import RecursiveComputer
from runtime.R25.system_evolution_runtime import canonical_json, sha256_json


def _copy(value):
    return json.loads(canonical_json(value))


class IndependentFabricNode:
    def __init__(self, *, node_id: str, state_root: Path, advertised_endpoint: str | None = None):
        self.node_id = node_id
        self.state_root = state_root
        self.state_root.mkdir(parents=True, exist_ok=True)
        if (self.state_root / "computer.json").exists():
            self.computer = RecursiveComputer.restore_tree(self.state_root)
        else:
            self.computer = RecursiveComputer(computer_id=node_id, state_root=self.state_root)
            self.computer.write_state("role", "INDEPENDENT_ROUTABLE_FABRIC_NODE")
        if advertised_endpoint:
            self.computer.write_state("advertised_endpoint", advertised_endpoint)

    def identity(self):
        committed = self.computer.inspect_committed()
        return {
            "status": "READY",
            "node_id": self.node_id,
            "constructor_id": self.computer.identity.constructor_id,
            "lineage": list(self.computer.identity.lineage),
            "state_root": committed["value_hash"],
            "ledger_verified": committed["ledger_verified"],
            "advertised_endpoint": committed["value"].get("state", {}).get("advertised_endpoint"),
        }

    def join(self, peer):
        required = {"node_id", "endpoint", "state_root"}
        missing = sorted(required.difference(peer))
        if missing:
            raise ValueError("MISSING_JOIN_FIELDS:" + ",".join(missing))
        peers = _copy(self.computer.readback().get("memory", {}).get("fabric_peers", {}))
        peers[str(peer["node_id"])] = {
            "endpoint": str(peer["endpoint"]),
            "state_root": str(peer["state_root"]),
            "authority": str(peer.get("authority", "runtime://kex/fabric")),
        }
        self.computer.write_memory("fabric_peers", peers)
        return {"status": "JOINED", "peer": peers[str(peer["node_id"])], "node": self.identity()}

    def peers(self):
        return _copy(self.computer.readback().get("memory", {}).get("fabric_peers", {}))

    def proof(self, challenge: str):
        ident = self.identity()
        body = {
            "node_id": ident["node_id"],
            "state_root": ident["state_root"],
            "constructor_id": ident["constructor_id"],
            "challenge": challenge,
        }
        return {"status": "PROVED", "body": body, "proof": hashlib.sha256(canonical_json(body).encode()).hexdigest()}


def build_handler(node: IndependentFabricNode, token: str | None):
    class Handler(BaseHTTPRequestHandler):
        server_version = "KEDDEH-KEX-R38/1"

        def _authorized(self):
            if not token:
                return True
            return self.headers.get("Authorization") == f"Bearer {token}"

        def _send(self, status: int, body):
            raw = canonical_json(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self):
            n = int(self.headers.get("Content-Length", "0"))
            return json.loads(self.rfile.read(n) or b"{}")

        def do_GET(self):
            if not self._authorized():
                return self._send(401, {"status": "UNAUTHORIZED"})
            parsed = urlparse(self.path)
            if parsed.path == "/healthz":
                return self._send(200, {"status": "ALIVE", "node_id": node.node_id})
            if parsed.path == "/readyz":
                ident = node.identity()
                return self._send(200 if ident["ledger_verified"] else 503, ident)
            if parsed.path == "/v1/fabric/identity":
                return self._send(200, node.identity())
            if parsed.path == "/v1/fabric/peers":
                return self._send(200, {"status": "READ", "peers": node.peers()})
            if parsed.path == "/v1/fabric/proof":
                challenge = parse_qs(parsed.query).get("challenge", [""])[0]
                if not challenge:
                    return self._send(400, {"status": "BLOCKED", "reason": "CHALLENGE_REQUIRED"})
                return self._send(200, node.proof(challenge))
            return self._send(404, {"status": "NOT_FOUND"})

        def do_POST(self):
            if not self._authorized():
                return self._send(401, {"status": "UNAUTHORIZED"})
            if self.path == "/v1/fabric/join":
                try:
                    return self._send(200, node.join(self._read_json()))
                except Exception as exc:
                    return self._send(400, {"status": "BLOCKED", "reason": str(exc)})
            return self._send(404, {"status": "NOT_FOUND"})

        def log_message(self, fmt, *args):
            print("HTTP", self.address_string(), fmt % args, flush=True)

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--node-id", default=os.environ.get("BRAINK_NODE_ID", "BRAINK_REMOTE_R38"))
    ap.add_argument("--state-root", default=os.environ.get("BRAINK_STATE_ROOT", str(Path.home() / ".local/share/keddeh/braink-independent-r38")))
    ap.add_argument("--bind", default=os.environ.get("BRAINK_BIND", "0.0.0.0"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("BRAINK_PORT", "29700")))
    ap.add_argument("--advertised-endpoint", default=os.environ.get("BRAINK_ADVERTISED_ENDPOINT"))
    ap.add_argument("--token", default=os.environ.get("BRAINK_TOKEN"))
    args = ap.parse_args()

    node = IndependentFabricNode(node_id=args.node_id, state_root=Path(args.state_root), advertised_endpoint=args.advertised_endpoint)
    print(canonical_json({"event": "BRAINK_NODE_START", "identity": node.identity(), "bind": args.bind, "port": args.port}), flush=True)
    ThreadingHTTPServer((args.bind, args.port), build_handler(node, args.token)).serve_forever()


if __name__ == "__main__":
    main()
