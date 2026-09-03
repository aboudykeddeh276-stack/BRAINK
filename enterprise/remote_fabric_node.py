from __future__ import annotations

"""Independently-routable BRAINK fabric node bound to resident BRAINK/KEX state.

Authority order:
    resident BRAINK/KEX state
      -> canonical typed root graph
      -> machine-specific projection
      -> HTTP/TCP interface
      -> public carrier

The carrier never defines the node.  This process refuses to start without a resolved
resident-root graph, and every fabric-join receipt is cryptographically bound to that
graph plus the canonical BRAINK/CLOUD/SERVER root digests.
"""

import argparse
import base64
import hashlib
import json
import os
import platform
import socket
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def machine_material() -> str:
    parts = [socket.gethostname(), platform.platform(), platform.machine()]
    machine_id = Path("/etc/machine-id")
    if machine_id.exists():
        parts.append(machine_id.read_text("utf-8").strip())
    return "|".join(parts)


def load_resident_graph(path: Path) -> dict[str, Any]:
    graph = json.loads(path.read_text("utf-8"))
    required = {"BRAINK_ROOT", "SERVER_ROOT", "CLOUD_ROOT"}
    roots = graph.get("roots", {})
    missing = required - set(roots)
    if missing:
        raise RuntimeError(f"RESIDENT_ROOTS_MISSING:{sorted(missing)}")
    material = dict(graph)
    claimed = material.pop("graph_digest", None)
    observed = hashlib.sha256(canonical(material)).hexdigest()
    if claimed != observed:
        raise RuntimeError("RESIDENT_GRAPH_DIGEST_MISMATCH")
    for rid in required:
        envelope = roots[rid]
        if envelope.get("stateDigest") is None:
            raise RuntimeError(f"ROOT_DIGEST_MISSING:{rid}")
        if envelope.get("payload", {}).get("state") != "BOUND":
            raise RuntimeError(f"ROOT_NOT_BOUND:{rid}")
    return graph


class FabricNodeState:
    def __init__(
        self,
        *,
        commit_sha: str,
        run_id: str,
        private_key: Path,
        public_key: Path,
        receipt_path: Path,
        resident_roots: Path,
    ):
        self.commit_sha = commit_sha
        self.run_id = run_id
        self.private_key = private_key
        self.public_key = public_key
        self.receipt_path = receipt_path
        self.resident_graph = load_resident_graph(resident_roots)
        self.resident_graph_digest = self.resident_graph["graph_digest"]
        roots = self.resident_graph["roots"]
        self.root_digests = {
            rid: roots[rid]["stateDigest"]
            for rid in ("BRAINK_ROOT", "SERVER_ROOT", "CLOUD_ROOT")
        }
        self.public_key_pem = public_key.read_text("utf-8")
        self.public_key_sha256 = sha256_bytes(self.public_key_pem.encode("utf-8"))
        semantic_seed = canonical(
            {
                "braink_root": self.root_digests["BRAINK_ROOT"],
                "cloud_root": self.root_digests["CLOUD_ROOT"],
                "server_root": self.root_digests["SERVER_ROOT"],
                "resident_graph": self.resident_graph_digest,
                "machine_projection": machine_material(),
            }
        )
        self.node_id = "BRAINK-REMOTE-" + hashlib.sha256(semantic_seed).hexdigest()[:24]
        self.started_ns = time.time_ns()

    def identity(self) -> dict[str, Any]:
        return {
            "schema": "braink.remote-fabric-node.identity.v2",
            "node_id": self.node_id,
            "semantic_identity": f"LEX://BRAINK/MACHINE/{self.node_id}",
            "commit_sha": self.commit_sha,
            "run_id": self.run_id,
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "pid": os.getpid(),
            "started_ns": self.started_ns,
            "resident_graph_digest": self.resident_graph_digest,
            "root_digests": self.root_digests,
            "public_key_sha256": self.public_key_sha256,
            "public_key_pem": self.public_key_pem,
            "interfaces": ["http/tcp", "fabric/join/challenge-response"],
            "carrier_role": "PROJECTION_ONLY",
        }

    def roots_projection(self) -> dict[str, Any]:
        return {
            "schema": self.resident_graph["schema"],
            "graph_digest": self.resident_graph_digest,
            "authority_order": self.resident_graph["authority_order"],
            "roots": {
                rid: self.resident_graph["roots"][rid]
                for rid in (
                    "BRAINK_ROOT",
                    "DOMAIN_ROOT",
                    "DNS_ROOT",
                    "REGISTRAR_ROOT",
                    "TLS_ROOT",
                    "SERVER_ROOT",
                    "CLOUD_ROOT",
                )
                if rid in self.resident_graph["roots"]
            },
        }

    def sign(self, payload: dict[str, Any]) -> str:
        proc = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private_key)],
            input=canonical(payload),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return base64.b64encode(proc.stdout).decode("ascii")

    def join(self, request: dict[str, Any], peer_ip: str) -> dict[str, Any]:
        fabric_node_id = str(request.get("fabric_node_id") or "").strip()
        challenge = str(request.get("challenge") or "").strip()
        expected_graph = str(request.get("resident_graph_digest") or "").strip()
        if not fabric_node_id or not challenge or not expected_graph:
            raise ValueError("fabric_node_id, challenge and resident_graph_digest are required")
        if expected_graph != self.resident_graph_digest:
            raise ValueError("RESIDENT_GRAPH_MISMATCH")
        receipt = {
            "schema": "braink.remote-fabric-node.join-receipt.v2",
            "remote_node_id": self.node_id,
            "fabric_node_id": fabric_node_id,
            "challenge": challenge,
            "commit_sha": self.commit_sha,
            "run_id": self.run_id,
            "resident_graph_digest": self.resident_graph_digest,
            "root_digests": self.root_digests,
            "peer_ip": peer_ip,
            "joined_ns": time.time_ns(),
            "transport": "http-over-tcp-public-carrier",
            "carrier_role": "PROJECTION_ONLY",
            "public_key_sha256": self.public_key_sha256,
        }
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        with self.receipt_path.open("a", encoding="utf-8") as fh:
            fh.write(canonical(receipt).decode("utf-8") + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return {"receipt": receipt, "signature_b64": self.sign(receipt)}


class Handler(BaseHTTPRequestHandler):
    state: FabricNodeState

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        raw = canonical(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(
                200,
                {
                    "status": "OK",
                    "node_id": self.state.node_id,
                    "resident_graph_digest": self.state.resident_graph_digest,
                },
            )
            return
        if self.path == "/identity":
            self._json(200, self.state.identity())
            return
        if self.path == "/roots":
            self._json(200, self.state.roots_projection())
            return
        self._json(404, {"status": "NOT_FOUND"})

    def do_POST(self) -> None:
        if self.path != "/fabric/join":
            self._json(404, {"status": "NOT_FOUND"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            result = self.state.join(body, self.client_address[0])
        except Exception as exc:
            self._json(400, {"status": "REJECTED", "reason": str(exc)})
            return
        self._json(200, {"status": "JOINED", **result})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"remote-node {self.address_string()} {fmt % args}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--resident-roots", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, default=Path("build/remote-fabric-join-receipts.jsonl"))
    args = parser.parse_args()

    state = FabricNodeState(
        commit_sha=args.commit,
        run_id=args.run_id,
        private_key=args.private_key,
        public_key=args.public_key,
        receipt_path=args.receipts,
        resident_roots=args.resident_roots,
    )
    Handler.state = state
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(json.dumps({"status": "LISTENING", **state.identity(), "bind": [args.host, args.port]}, sort_keys=True), flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
