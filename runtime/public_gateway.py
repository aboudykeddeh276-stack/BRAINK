#!/usr/bin/env python3
"""
BRAINK public rail gateway.

This gateway is a projection/control surface, not resident authority.  It exposes
bounded front-surface routes backed by observed BRAINK/KEX state and existing
local rails.  It never promotes UI state from a button click alone.
"""
from __future__ import annotations
import base64
import http.server
import json
import os
import socket
import time
import urllib.parse
import uuid
from pathlib import Path

from runtime.host_control.braink_host_fabric import HostFabric
from runtime.resident_root_projection_r28 import ResidentRootResolver, carrier_projection
from runtime.runtime_registry import RuntimeRegistry

OAUTH_SOCKET = os.environ.get("BRAINK_OAUTH_SOCKET", "/tmp/braink-oauth.sock")
STRIPE_SOCKET = os.environ.get("BRAINK_STRIPE_SOCKET", "/tmp/braink-stripe.sock")
REPO_ROOT = Path(os.environ.get("BRAINK_REPO_ROOT", ".")).resolve()
CARRIER_ENDPOINT = os.environ.get("BRAINK_CARRIER_ENDPOINT", "")
CARRIER_KIND = os.environ.get("BRAINK_CARRIER_KIND", "HTTP")
HOST_ID = os.environ.get("BRAINK_HOST_ID", socket.gethostname())
HOST_STATE = Path(os.environ.get("BRAINK_HOST_FABRIC_STATE", REPO_ROOT / ".kex" / "state" / "host_fabric"))
RUNTIME_DB = Path(os.environ.get("BRAINK_RUNTIME_DB", HOST_STATE / "runtimes.sqlite"))
BACKBONE_RECEIPTS = Path(os.environ.get("KEDDEH_BACKBONE_RECEIPTS", "/var/lib/keddeh/backbone/backbone_receipts.jsonl"))
BACKBONE_STALE_SEC = float(os.environ.get("BRAINK_BACKBONE_STALE_SEC", "30"))
MAX_BODY = int(os.environ.get("BRAINK_PUBLIC_MAX_BODY", str(1 << 20)))


def rail_call(path: str, payload: dict) -> dict:
    body = (json.dumps(payload, separators=(",", ":")) + "\n").encode()
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.settimeout(10)
        s.connect(path)
        s.sendall(body)
        buf = b""
        while not buf.endswith(b"\n") and len(buf) <= MAX_BODY:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        if not buf:
            raise RuntimeError("EMPTY_RAIL_RESPONSE")
        if len(buf) > MAX_BODY:
            raise RuntimeError("RAIL_RESPONSE_TOO_LARGE")
        out = json.loads(buf.decode())
        if out.get("status") not in ("PASS", "OK", "AUTHORIZED", "CREATED"):
            raise RuntimeError(out.get("error", "RAIL_REJECTED"))
        return out
    finally:
        s.close()


def resident_snapshot(domain: str) -> dict:
    return ResidentRootResolver(str(REPO_ROOT)).canonical_snapshot(domain)


def host_fabric() -> HostFabric:
    return HostFabric(state_dir=HOST_STATE)


def runtime_registry() -> RuntimeRegistry:
    return RuntimeRegistry(RUNTIME_DB)


def _backbone_observation() -> dict:
    if not BACKBONE_RECEIPTS.is_file():
        return {"status": "UNOBSERVED", "reason": "BACKBONE_RECEIPT_LOG_MISSING"}
    try:
        lines = BACKBONE_RECEIPTS.read_text(encoding="utf-8").splitlines()[-256:]
        records = [json.loads(line) for line in lines if line.strip()]
    except Exception as exc:
        return {"status": "UNOBSERVED", "reason": f"BACKBONE_RECEIPT_READ_FAILED:{type(exc).__name__}"}
    heartbeat = next((r for r in reversed(records) if r.get("event") == "BACKBONE_HEARTBEAT"), None)
    ready = any(r.get("event") == "BACKBONE_READY" for r in records)
    mesh = any(r.get("event") == "MESH_LISTENING" for r in records)
    dns = any(r.get("event") == "DNS_LISTENING" for r in records)
    if not heartbeat:
        return {"status": "UNOBSERVED", "ready_receipt": ready, "mesh_receipt": mesh, "dns_receipt": dns}
    ts = heartbeat.get("timestamp_ns")
    age = None
    if isinstance(ts, int):
        age = max(0.0, (time.time_ns() - ts) / 1e9)
    else:
        raw = str(heartbeat.get("timestamp_utc", ""))
        try:
            from datetime import datetime
            age = max(0.0, time.time() - datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp())
        except Exception:
            age = None
    state = "UP" if age is not None and age <= BACKBONE_STALE_SEC and ready and mesh and dns else "STALE"
    return {
        "status": state,
        "heartbeat_age_sec": round(age, 3) if age is not None else None,
        "ready_receipt": ready,
        "mesh_receipt": mesh,
        "dns_receipt": dns,
        "proof_root": heartbeat.get("proof_root"),
    }


def _dashboard_summary() -> dict:
    try:
        hosts = host_fabric().list_hosts()
    except Exception:
        hosts = []
    try:
        runtimes = runtime_registry().list()
    except Exception:
        runtimes = []
    nodes = [
        {
            "id": h.get("node_id") or h.get("host_id"),
            "host_id": h.get("host_id"),
            "status": h.get("admission_state"),
            "mode": h.get("observed_mode"),
            "role": h.get("host_class"),
            "heartbeat_age_sec": h.get("heartbeat_age_sec"),
        }
        for h in hosts
    ]
    modules = [
        {
            "id": r.get("runtime_id"),
            "state": r.get("observed_state"),
            "desired_state": r.get("desired_state"),
            "type": r.get("runtime_class"),
        }
        for r in runtimes
    ]
    active = sum(1 for r in runtimes if r.get("observed_state") in {"RUNNING", "READY", "ACTIVE"})
    return {
        "status": "PASS",
        "nodes": nodes,
        "skills": [],
        "skills_state": "UNBOUND_REGISTRY",
        "modules": modules,
        "mesh": _backbone_observation(),
        "metrics": {
            "processActive": active,
            "processMax": max(len(runtimes), 1),
            "skillOpsPerMin": 0,
            "skillMaxOpsPerMin": 1,
        },
    }


def _boot_state() -> tuple[int, dict]:
    control = REPO_ROOT / ".kex" / "runner-control-plane.json"
    if not control.is_file():
        return 503, {"status": "BLOCKED", "reason": "CONTROL_PLANE_MISSING"}
    try:
        hosts = host_fabric().list_hosts()
    except Exception as exc:
        return 503, {"status": "BLOCKED", "reason": f"HOST_FABRIC_UNAVAILABLE:{type(exc).__name__}"}
    ready = [h for h in hosts if h.get("admission_state") == "HOST_READY" and h.get("observed_mode") == "ONLINE"]
    mesh = _backbone_observation()
    if not ready:
        return 409, {
            "status": "BLOCKED",
            "reason": "NO_FRESH_ONLINE_HOST_READY",
            "mesh": mesh,
            "host_count": len(hosts),
        }
    runtime_state = "ONLINE" if mesh.get("status") == "UP" else "HOST_READY_NETWORK_UNPROVEN"
    return 200, {
        "status": runtime_state,
        "hosts_ready": [h.get("host_id") for h in ready],
        "mesh": mesh,
        "control_plane": "MOUNTED",
    }


def _chat_execute(data: dict) -> tuple[int, dict]:
    task = str(data.get("task", "")).strip()
    if not task:
        return 400, {"status": "REJECTED", "reason": "TASK_REQUIRED"}
    if len(task) > 8192:
        return 413, {"status": "REJECTED", "reason": "TASK_TOO_LARGE"}
    process_id = f"process:{uuid.uuid4()}"
    frame_id = f"frame:{uuid.uuid4()}"
    lowered = task.casefold()
    if any(token in lowered for token in ("mesh status", "show mesh", "network status", "show network")):
        observation = _dashboard_summary()
        return 200, {
            "status": "PASS",
            "process_id": process_id,
            "frame_id": frame_id,
            "reply": json.dumps({"mesh": observation["mesh"], "nodes": observation["nodes"]}, separators=(",", ":")),
            "execution_class": "OBSERVED_READ",
        }
    return 202, {
        "status": "INTENT_ACCEPTED_NO_ACTUATOR",
        "process_id": process_id,
        "frame_id": frame_id,
        "reply": "Request normalized as a BRAINK process intent, but no execution actuator is bound for this free-form task yet.",
        "execution_class": "PROCESS_INTENT_ONLY",
    }


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "BRAINKPublic/3"

    def json(self, code, obj):
        body = json.dumps(obj, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        n = int(self.headers.get("Content-Length", "0"))
        if n < 0 or n > MAX_BODY:
            raise ValueError("REQUEST_BODY_TOO_LARGE")
        raw = self.rfile.read(n)
        ctype = self.headers.get("Content-Type", "")
        if "json" in ctype:
            return raw, json.loads(raw or b"{}")
        return raw, dict(urllib.parse.parse_qsl(raw.decode()))

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/health":
            return self.json(200, {"status": "PASS", "runtime": "runtime://braink/public-gateway/3", "carrier_role": "PROJECTION_ONLY"})
        if u.path == "/mesh/ping":
            observation = _backbone_observation()
            return self.json(200 if observation.get("status") == "UP" else 503, observation)
        if u.path == "/dashboards/summary":
            return self.json(200, _dashboard_summary())
        if u.path == "/braink/resident-roots":
            domain = q.get("domain", ["keddeh.com"])[0]
            try:
                snapshot = resident_snapshot(domain)
                return self.json(200, {"status": "PASS", "authority": "BRAINK_RESIDENT_OBJECT_GRAPH", **snapshot})
            except Exception as exc:
                return self.json(500, {"status": "FAIL", "component": "BRAINK_RESIDENT_ROOT_RESOLVER", "error": str(exc)})
        if u.path == "/braink/carrier-projection":
            domain = q.get("domain", ["keddeh.com"])[0]
            if not CARRIER_ENDPOINT:
                return self.json(409, {"status": "UNBOUND", "component": "BRAINK_CARRIER_PROJECTION", "reason": "BRAINK_CARRIER_ENDPOINT_NOT_SET"})
            try:
                snapshot = resident_snapshot(domain)
                projection = carrier_projection(snapshot, endpoint=CARRIER_ENDPOINT, carrier=CARRIER_KIND, host_id=HOST_ID)
                return self.json(200, {"status": "PASS", "carrier_role": "PROJECTION_ONLY", "projection": projection})
            except Exception as exc:
                return self.json(500, {"status": "FAIL", "component": "BRAINK_CARRIER_PROJECTION", "error": str(exc)})
        if u.path == "/auth/google/start":
            domain = q.get("domain", ["braink.com.au"])[0]
            try:
                result = rail_call(OAUTH_SOCKET, {"op": "AUTHORIZE_URL", "domain": domain, "return_to": q.get("return_to", ["/"])[0]})
                self.send_response(302)
                self.send_header("Location", result["authorization_url"])
                self.end_headers()
            except Exception as exc:
                self.json(503, {"status": "BLOCKED", "component": "BRAINK_GOOGLE_OAUTH_RAIL", "error": str(exc)})
            return
        if u.path == "/auth/google/callback":
            try:
                result = rail_call(OAUTH_SOCKET, {"op": "CALLBACK", "query": {k: v[0] for k, v in q.items()}})
                return self.json(200, {"status": "PASS", "session": result.get("session"), "profile": result.get("profile")})
            except Exception as exc:
                return self.json(401, {"status": "REJECTED", "component": "BRAINK_GOOGLE_OAUTH_RAIL", "error": str(exc)})
        return self.json(404, {"status": "NOT_FOUND"})

    def do_POST(self):
        try:
            raw, data = self.read_body()
        except Exception as exc:
            return self.json(400, {"status": "REJECTED", "reason": str(exc)})
        if self.path == "/braink/boot":
            code, result = _boot_state()
            return self.json(code, result)
        if self.path == "/chat/execute":
            code, result = _chat_execute(data)
            return self.json(code, result)
        if self.path == "/payments/checkout":
            try:
                result = rail_call(STRIPE_SOCKET, {"op": "CREATE_CHECKOUT", "request": data})
                return self.json(200, {"status": "PASS", "checkout_url": result["checkout_url"], "session_id": result.get("session_id")})
            except Exception as exc:
                return self.json(503, {"status": "BLOCKED", "component": "BRAINK_STRIPE_PAYMENT_RAIL", "error": str(exc)})
        if self.path == "/payments/stripe/webhook":
            try:
                result = rail_call(STRIPE_SOCKET, {"op": "WEBHOOK", "payload_b64": base64.b64encode(raw).decode(), "stripe_signature": self.headers.get("Stripe-Signature", "")})
                return self.json(200, {"status": "PASS", "event": result.get("event")})
            except Exception as exc:
                return self.json(400, {"status": "REJECTED", "component": "BRAINK_STRIPE_PAYMENT_RAIL", "error": str(exc)})
        return self.json(404, {"status": "NOT_FOUND"})


if __name__ == "__main__":
    host = os.environ.get("BRAINK_BIND", "127.0.0.1")
    port = int(os.environ.get("BRAINK_PORT", "8799"))
    http.server.ThreadingHTTPServer((host, port), Handler).serve_forever()
