#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import signal
import sqlite3
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

PORT = int(os.getenv("PORT", "8080"))
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
DB_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "cloudworkspace.db")))
NODE_ID = os.getenv("MESH_NODE_ID", "cloudworkspace-engine")
REGION_ID = os.getenv("MESH_REGION_ID", "sovereign-primary")
STARTED_AT = time.time()
STARTUP_COMPLETE = threading.Event()
SHUTTING_DOWN = threading.Event()

DEPENDENCY_POLICY = json.loads(os.getenv("DEPENDENCY_POLICY_JSON", "{}"))
FALLBACK_ADAPTERS = json.loads(os.getenv("FALLBACK_ADAPTERS_JSON", "{}"))
REQUIRED_CAPABILITIES = {
    item.strip() for item in os.getenv("READINESS_REQUIRED_CAPABILITIES", "application-core,vfs,runtime-config").split(",") if item.strip()
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def _initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    state TEXT NOT NULL,
                    observed_at REAL NOT NULL,
                    receipt_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS manifests (
                    application_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    expected_hash TEXT NOT NULL,
                    actual_hash TEXT NOT NULL,
                    admission_state TEXT NOT NULL,
                    submitted_at REAL NOT NULL,
                    PRIMARY KEY(application_id, version)
                );
                CREATE TABLE IF NOT EXISTS failures (
                    failure_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    receipt_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                """
            )

    def upsert_node(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        node_id = str(payload.get("nodeId") or payload.get("node_id") or uuid.uuid4())
        now = time.time()
        record = {**payload, "nodeId": node_id, "regionId": payload.get("regionId", REGION_ID), "observedAt": now}
        receipt_hash = sha256(record)
        with self._lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO nodes(node_id,payload,state,observed_at,receipt_hash) VALUES(?,?,?,?,?) "
                "ON CONFLICT(node_id) DO UPDATE SET payload=excluded.payload,state=excluded.state,observed_at=excluded.observed_at,receipt_hash=excluded.receipt_hash",
                (node_id, canonical_json(record), str(payload.get("state", "HEALTHY")), now, receipt_hash),
            )
        return {"node": record, "receiptHash": receipt_hash}

    def node_health(self, node_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM nodes WHERE node_id=?", (node_id,)).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload"])
        return {"nodeId": node_id, "state": row["state"], "observedAt": row["observed_at"], "receiptHash": row["receipt_hash"], "capabilities": payload.get("capabilities", [])}

    def submit_manifest(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        manifest = payload.get("manifest", payload)
        application_id = str(manifest.get("applicationId", "unknown"))
        version = str(manifest.get("version", "0.0.0"))
        expected = str(payload.get("expectedSha256", payload.get("expected_hash", "")))
        actual = sha256(manifest)
        state = "ADMITTED" if expected and expected == actual else "INTEGRITY_REJECTED"
        now = time.time()
        with self._lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO manifests(application_id,version,payload,expected_hash,actual_hash,admission_state,submitted_at) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(application_id,version) DO UPDATE SET payload=excluded.payload,expected_hash=excluded.expected_hash,actual_hash=excluded.actual_hash,admission_state=excluded.admission_state,submitted_at=excluded.submitted_at",
                (application_id, version, canonical_json(manifest), expected, actual, state, now),
            )
        return {"applicationId": application_id, "version": version, "expectedSha256": expected, "actualSha256": actual, "admissionState": state, "promotionBoundary": "NODE_EXECUTION" if state == "ADMITTED" else "INTEGRITY_READBACK"}

    def create_failure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        failure_id = str(payload.get("failureId") or uuid.uuid4())
        now = time.time()
        criticality = str(payload.get("criticality", "CORE_DEGRADED"))
        state = "BOUNDED_STOP" if criticality == "CORE_MANDATORY" else "DEFERRED"
        record = {
            **payload,
            "failureId": failure_id,
            "state": state,
            "globalStop": False,
            "createdAt": payload.get("createdAt", now),
            "updatedAt": now,
        }
        with self._lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO failures(failure_id,payload,state,created_at,updated_at) VALUES(?,?,?,?,?) "
                "ON CONFLICT(failure_id) DO UPDATE SET payload=excluded.payload,state=excluded.state,updated_at=excluded.updated_at",
                (failure_id, canonical_json(record), state, float(record["createdAt"]), now),
            )
        return record

    def list_failures(self, state: Optional[str] = None) -> list[Dict[str, Any]]:
        query = "SELECT payload FROM failures"
        args: tuple[Any, ...] = ()
        if state:
            query += " WHERE state=?"
            args = (state,)
        query += " ORDER BY updated_at DESC"
        with self.connect() as conn:
            return [json.loads(row["payload"]) for row in conn.execute(query, args)]

    def get_failure(self, failure_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute("SELECT payload FROM failures WHERE failure_id=?", (failure_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def reconcile_failure(self, failure_id: str, evidence: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        current = self.get_failure(failure_id)
        if current is None:
            return None
        recovered = bool(evidence.get("dependencyHealthy")) and bool(evidence.get("reintegrationTestPassed"))
        current["state"] = "REINTEGRATED" if recovered else "DEFERRED"
        current["updatedAt"] = time.time()
        current["reconciliationEvidence"] = evidence
        current["globalStop"] = False
        with self._lock, self.connect() as conn:
            conn.execute("UPDATE failures SET payload=?,state=?,updated_at=? WHERE failure_id=?", (canonical_json(current), current["state"], current["updatedAt"], failure_id))
            receipt = {"failureId": failure_id, "state": current["state"], "evidence": evidence, "globalStop": False, "createdAt": time.time()}
            receipt_id = sha256(receipt)
            conn.execute("INSERT INTO receipts(receipt_id,kind,payload,created_at) VALUES(?,?,?,?)", (receipt_id, "FAILURE_RECONCILIATION", canonical_json(receipt), receipt["createdAt"]))
        return {"failure": current, "receiptId": receipt_id}

    def readiness(self) -> Dict[str, Any]:
        capabilities = {
            "application-core": "HEALTHY",
            "vfs": "HEALTHY" if os.access(DATA_DIR, os.W_OK) else "BOUNDED_STOP",
            "runtime-config": "HEALTHY" if DEPENDENCY_POLICY else "BOUNDED_STOP",
            "mesh-registry": "CORE_DEGRADED",
        }
        missing = sorted(cap for cap in REQUIRED_CAPABILITIES if capabilities.get(cap) != "HEALTHY")
        return {
            "state": "READY" if not missing else "NOT_READY",
            "nodeId": NODE_ID,
            "regionId": REGION_ID,
            "capabilities": capabilities,
            "missingMandatoryCapabilities": missing,
            "globalStop": False,
        }


STORE = Store(DB_PATH)


class Handler(BaseHTTPRequestHandler):
    server_version = "CloudWorkspaceEngine/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print(canonical_json({"time": time.time(), "client": self.client_address[0], "message": format % args}))

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 2 * 1024 * 1024:
            raise ValueError("payload_too_large")
        raw = self.rfile.read(length) if length else b"{}"
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("object_required")
        return value

    def _send(self, status: int, payload: Dict[str, Any]) -> None:
        body = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-KEX-Node-Id", NODE_ID)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/startupz":
            self._send(HTTPStatus.OK if STARTUP_COMPLETE.is_set() else HTTPStatus.SERVICE_UNAVAILABLE, {"state": "STARTED" if STARTUP_COMPLETE.is_set() else "STARTING", "globalStop": False})
            return
        if path == "/healthz":
            healthy = not SHUTTING_DOWN.is_set()
            self._send(HTTPStatus.OK if healthy else HTTPStatus.SERVICE_UNAVAILABLE, {"state": "HEALTHY" if healthy else "SHUTTING_DOWN", "uptimeSeconds": time.time() - STARTED_AT, "globalStop": False})
            return
        if path == "/readyz":
            readiness = STORE.readiness()
            self._send(HTTPStatus.OK if readiness["state"] == "READY" else HTTPStatus.SERVICE_UNAVAILABLE, readiness)
            return
        if path == "/metrics":
            failures = STORE.list_failures()
            self._send(HTTPStatus.OK, {"uptime_seconds": time.time() - STARTED_AT, "failure_records": len(failures), "global_stop": 0})
            return
        if path.startswith("/v1/nodes/") and path.endswith("/health"):
            node_id = path.split("/")[3]
            result = STORE.node_health(node_id)
            self._send(HTTPStatus.OK if result else HTTPStatus.NOT_FOUND, result or {"error": "node_not_found"})
            return
        if path == "/v1/failures":
            state = parse_qs(parsed.query).get("state", [None])[0]
            self._send(HTTPStatus.OK, {"items": STORE.list_failures(state), "globalStop": False})
            return
        if path.startswith("/v1/failures/"):
            failure_id = path.split("/")[3]
            result = STORE.get_failure(failure_id)
            self._send(HTTPStatus.OK if result else HTTPStatus.NOT_FOUND, result or {"error": "failure_not_found"})
            return
        self._send(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})

    def do_POST(self) -> None:
        try:
            payload = self._read_json()
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        path = urlparse(self.path).path
        if path == "/v1/nodes":
            self._send(HTTPStatus.CREATED, STORE.upsert_node(payload))
            return
        if path.startswith("/v1/nodes/") and path.endswith("/heartbeat"):
            payload["nodeId"] = path.split("/")[3]
            payload["state"] = payload.get("state", "HEALTHY")
            self._send(HTTPStatus.OK, STORE.upsert_node(payload))
            return
        if path == "/v1/packages/manifests":
            result = STORE.submit_manifest(payload)
            self._send(HTTPStatus.ACCEPTED if result["admissionState"] == "ADMITTED" else HTTPStatus.UNPROCESSABLE_ENTITY, result)
            return
        if path == "/v1/failures":
            self._send(HTTPStatus.CREATED, STORE.create_failure(payload))
            return
        if path.startswith("/v1/failures/") and path.endswith("/reconcile"):
            failure_id = path.split("/")[3]
            result = STORE.reconcile_failure(failure_id, payload)
            self._send(HTTPStatus.OK if result else HTTPStatus.NOT_FOUND, result or {"error": "failure_not_found"})
            return
        self._send(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STARTUP_COMPLETE.set()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)

    def stop(_signum: int, _frame: Any) -> None:
        SHUTTING_DOWN.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(canonical_json({"event": "cloudworkspace_started", "nodeId": NODE_ID, "port": PORT, "database": str(DB_PATH)}))
    server.serve_forever(poll_interval=0.25)
    server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
