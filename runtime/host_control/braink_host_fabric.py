#!/usr/bin/env python3
"""BRAINK host fabric: admission, routing, reconciliation and offline continuity.

Host identity, authority, desired state and observed state remain distinct.
Desktop Commander and other carriers provide execution reach but are not identity
or authority. Durable receipts are transactionally chained in SQLite.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.runtime_registry import RuntimeRegistry

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_DIR = Path(os.getenv("BRAINK_HOST_FABRIC_STATE", ROOT / ".kex" / "state" / "host_fabric"))
DEFAULT_STALE_SEC = int(os.getenv("BRAINK_HOST_STALE_SEC", "30"))
SQLITE_BUSY_MS = int(os.getenv("BRAINK_HOST_SQLITE_BUSY_MS", "5000"))
DESIRED_MODES = {"ONLINE", "OFFLINE_LOCAL"}
OBSERVED_HEARTBEAT_MODES = {"ONLINE", "OFFLINE_LOCAL"}


def canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(value: Any) -> str:
    return hashlib.sha256(canon(value).encode()).hexdigest()


def now_ns() -> int:
    return time.time_ns()


class HostFabric:
    def __init__(self, db_path: Optional[Path] = None, state_dir: Optional[Path] = None):
        if db_path is not None:
            self.db_path = Path(db_path)
            self.state_dir = Path(state_dir) if state_dir else self.db_path.parent
        else:
            self.state_dir = Path(state_dir) if state_dir else DEFAULT_STATE_DIR
            self.db_path = self.state_dir / "hosts.sqlite"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_registry = RuntimeRegistry(self.state_dir / "runtimes.sqlite")
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS hosts(
              host_id TEXT PRIMARY KEY,
              node_id TEXT NOT NULL,
              host_class TEXT NOT NULL,
              os_name TEXT NOT NULL,
              kernel TEXT NOT NULL,
              architecture TEXT NOT NULL,
              hostname TEXT NOT NULL,
              addresses_json TEXT NOT NULL,
              capabilities_json TEXT NOT NULL,
              supervisor TEXT NOT NULL,
              carrier TEXT NOT NULL,
              authority_root TEXT NOT NULL,
              desired_mode TEXT NOT NULL,
              observed_mode TEXT NOT NULL,
              admission_state TEXT NOT NULL,
              last_heartbeat_ns INTEGER NOT NULL,
              stale_after_sec INTEGER NOT NULL,
              proof_root TEXT NOT NULL,
              updated_ns INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS work_queue(
              work_id TEXT PRIMARY KEY,
              capability TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              authority_root TEXT NOT NULL,
              required_mode TEXT NOT NULL,
              assigned_host_id TEXT NOT NULL,
              state TEXT NOT NULL,
              created_ns INTEGER NOT NULL,
              updated_ns INTEGER NOT NULL,
              proof_root TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS host_receipts(
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              event TEXT NOT NULL,
              previous_proof_root TEXT NOT NULL,
              proof_root TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_ns INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_hosts_ready_state
              ON hosts(admission_state, observed_mode, updated_ns);
            CREATE INDEX IF NOT EXISTS idx_work_queue_state
              ON work_queue(state, created_ns);
            """)

    def db(self):
        db = sqlite3.connect(self.db_path, timeout=max(1.0, SQLITE_BUSY_MS / 1000.0))
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_MS}")
        return db

    def append_receipt(self, event: str, **payload: Any) -> Dict[str, Any]:
        created = now_ns()
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            last = db.execute("SELECT proof_root FROM host_receipts ORDER BY seq DESC LIMIT 1").fetchone()
            previous = last[0] if last else "0" * 64
            body = {"event": event, "timestamp_ns": created, "previous_proof_root": previous, **payload}
            body["proof_root"] = sha(body)
            db.execute(
                "INSERT INTO host_receipts(event,previous_proof_root,proof_root,payload_json,created_ns) VALUES(?,?,?,?,?)",
                (event, previous, body["proof_root"], canon(body), created),
            )
            db.commit()
        return body

    @staticmethod
    def _host_root(row: Dict[str, Any]) -> str:
        return sha({k: v for k, v in row.items() if k != "proof_root"})

    @staticmethod
    def _decode_host(row: sqlite3.Row | Dict[str, Any]) -> Dict[str, Any]:
        value = dict(row)
        value["addresses"] = json.loads(value.pop("addresses_json"))
        value["capabilities"] = json.loads(value.pop("capabilities_json"))
        return value

    def _raw_host(self, host: Dict[str, Any], **overrides: Any) -> Dict[str, Any]:
        row = {
            "host_id": host["host_id"],
            "node_id": host["node_id"],
            "host_class": host["host_class"],
            "os_name": host["os_name"],
            "kernel": host["kernel"],
            "architecture": host["architecture"],
            "hostname": host["hostname"],
            "addresses_json": canon(host["addresses"]),
            "capabilities_json": canon(host["capabilities"]),
            "supervisor": host["supervisor"],
            "carrier": host["carrier"],
            "authority_root": host["authority_root"],
            "desired_mode": host["desired_mode"],
            "observed_mode": host["observed_mode"],
            "admission_state": host["admission_state"],
            "last_heartbeat_ns": int(host["last_heartbeat_ns"]),
            "stale_after_sec": int(host["stale_after_sec"]),
            "proof_root": "",
            "updated_ns": now_ns(),
        }
        row.update(overrides)
        row["proof_root"] = self._host_root(row)
        return row

    def _write_host(self, row: Dict[str, Any]) -> Dict[str, Any]:
        with self.db() as db:
            db.execute(
                """INSERT INTO hosts VALUES(
                :host_id,:node_id,:host_class,:os_name,:kernel,:architecture,:hostname,
                :addresses_json,:capabilities_json,:supervisor,:carrier,:authority_root,
                :desired_mode,:observed_mode,:admission_state,:last_heartbeat_ns,
                :stale_after_sec,:proof_root,:updated_ns)
                ON CONFLICT(host_id) DO UPDATE SET
                node_id=excluded.node_id,host_class=excluded.host_class,os_name=excluded.os_name,
                kernel=excluded.kernel,architecture=excluded.architecture,hostname=excluded.hostname,
                addresses_json=excluded.addresses_json,capabilities_json=excluded.capabilities_json,
                supervisor=excluded.supervisor,carrier=excluded.carrier,authority_root=excluded.authority_root,
                desired_mode=excluded.desired_mode,observed_mode=excluded.observed_mode,
                admission_state=excluded.admission_state,last_heartbeat_ns=excluded.last_heartbeat_ns,
                stale_after_sec=excluded.stale_after_sec,proof_root=excluded.proof_root,updated_ns=excluded.updated_ns
                """,
                row,
            )
        return self.get_host(row["host_id"])

    def get_host(self, host_id: str) -> Dict[str, Any]:
        with self.db() as db:
            row = db.execute("SELECT * FROM hosts WHERE host_id=?", (host_id,)).fetchone()
        if not row:
            raise KeyError(host_id)
        return self._decode_host(row)

    def discover_local(self, carrier: str = "desktop-commander") -> Dict[str, Any]:
        host_id = f"host:{socket.gethostname()}"
        try:
            addresses = sorted({item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None) if item and item[4]})
        except socket.gaierror:
            addresses = []
        capabilities = [
            "host.identity.read", "host.process.list", "host.process.spawn", "host.process.stop",
            "host.filesystem.read", "host.filesystem.write", "host.shell.execute",
            "host.network.inspect", "host.service.inspect", "host.service.control", "host.receipt.writeback",
        ]
        return self.admit({
            "host_id": host_id,
            "node_id": os.getenv("KEX_NODE_ID", socket.gethostname()),
            "host_class": "PHYSICAL_OR_VM",
            "os_name": platform.system(),
            "kernel": platform.release(),
            "architecture": platform.machine(),
            "hostname": socket.gethostname(),
            "addresses": addresses,
            "capabilities": capabilities,
            "supervisor": "systemd" if Path("/run/systemd/system").exists() else "process",
            "carrier": carrier,
            "authority_root": os.getenv("BRAINK_HOST_AUTHORITY_ROOT", "UNBOUND"),
            "stale_after_sec": DEFAULT_STALE_SEC,
        })

    def admit(self, host: Dict[str, Any]) -> Dict[str, Any]:
        required = ["host_id", "node_id", "os_name", "architecture", "capabilities", "carrier", "authority_root"]
        missing = [key for key in required if not host.get(key)]
        if missing:
            raise ValueError(f"HOST_ADMISSION_MISSING:{','.join(missing)}")
        try:
            existing = self.get_host(str(host["host_id"]))
        except KeyError:
            existing = None

        desired_mode = host.get("desired_mode", existing["desired_mode"] if existing else "ONLINE")
        if desired_mode not in DESIRED_MODES:
            raise ValueError("BAD_HOST_MODE")
        stale_after = int(host.get("stale_after_sec", existing["stale_after_sec"] if existing else DEFAULT_STALE_SEC))
        if stale_after <= 0:
            raise ValueError("HOST_STALE_TTL_MUST_BE_POSITIVE")

        incoming_authority = str(host["authority_root"])
        if existing and existing["authority_root"] != "UNBOUND" and incoming_authority != existing["authority_root"]:
            raise PermissionError("HOST_AUTHORITY_REBIND_REQUIRES_EXPLICIT_ROTATION")

        preserve_runtime_state = bool(
            existing
            and existing["authority_root"] != "UNBOUND"
            and incoming_authority == existing["authority_root"]
        )
        if preserve_runtime_state:
            observed_mode = existing["observed_mode"]
            admission_state = existing["admission_state"]
            last_heartbeat_ns = existing["last_heartbeat_ns"]
        else:
            observed_mode = "DISCOVERED"
            admission_state = "AUTHORITY_VERIFIED" if incoming_authority != "UNBOUND" else "IDENTIFIED"
            last_heartbeat_ns = 0

        row = {
            "host_id": str(host["host_id"]),
            "node_id": str(host["node_id"]),
            "host_class": str(host.get("host_class", existing["host_class"] if existing else "UNKNOWN")),
            "os_name": str(host["os_name"]),
            "kernel": str(host.get("kernel", existing["kernel"] if existing else "")),
            "architecture": str(host["architecture"]),
            "hostname": str(host.get("hostname", existing["hostname"] if existing else "")),
            "addresses_json": canon(sorted(set(host.get("addresses", existing["addresses"] if existing else [])))),
            "capabilities_json": canon(sorted(set(host.get("capabilities", existing["capabilities"] if existing else [])))),
            "supervisor": str(host.get("supervisor", existing["supervisor"] if existing else "unknown")),
            "carrier": str(host["carrier"]),
            "authority_root": incoming_authority,
            "desired_mode": desired_mode,
            "observed_mode": observed_mode,
            "admission_state": admission_state,
            "last_heartbeat_ns": int(last_heartbeat_ns),
            "stale_after_sec": stale_after,
            "proof_root": "",
            "updated_ns": now_ns(),
        }
        row["proof_root"] = self._host_root(row)
        updated = self._write_host(row)
        self.append_receipt(
            "HOST_ADMITTED" if not existing else "HOST_REDISCOVERED",
            host_id=row["host_id"],
            admission_state=updated["admission_state"],
            observed_mode=updated["observed_mode"],
            state_preserved=preserve_runtime_state,
            host_proof_root=updated["proof_root"],
        )
        return updated

    def heartbeat(self, host_id: str, observed_mode: str = "ONLINE") -> Dict[str, Any]:
        if observed_mode not in OBSERVED_HEARTBEAT_MODES:
            raise ValueError("BAD_OBSERVED_HOST_MODE")
        host = self.get_host(host_id)
        if host["authority_root"] == "UNBOUND":
            raise PermissionError("HOST_AUTHORITY_UNBOUND")
        if observed_mode == "OFFLINE_LOCAL" and host["admission_state"] != "HOST_READY":
            raise RuntimeError("ONLINE_ADMISSION_REQUIRED_BEFORE_OFFLINE_LOCAL")
        row = self._raw_host(
            host,
            observed_mode=observed_mode,
            admission_state="HOST_READY",
            last_heartbeat_ns=now_ns(),
        )
        updated = self._write_host(row)
        self.append_receipt(
            "HOST_HEARTBEAT",
            host_id=host_id,
            observed_mode=observed_mode,
            host_proof_root=updated["proof_root"],
        )
        return self.refresh_state(updated)

    def refresh_state(self, host: Dict[str, Any]) -> Dict[str, Any]:
        if not host["last_heartbeat_ns"]:
            host["heartbeat_age_sec"] = None
            return host
        age = (now_ns() - host["last_heartbeat_ns"]) / 1e9
        host["heartbeat_age_sec"] = round(max(0.0, age), 3)
        if age > host["stale_after_sec"] and host["admission_state"] != "STALE":
            previous_mode = host["observed_mode"]
            row = self._raw_host(host, observed_mode="STALE", admission_state="STALE")
            persisted = self._write_host(row)
            persisted["heartbeat_age_sec"] = host["heartbeat_age_sec"]
            self.append_receipt(
                "HOST_STALE",
                host_id=host["host_id"],
                previous_observed_mode=previous_mode,
                heartbeat_age_sec=host["heartbeat_age_sec"],
                stale_after_sec=host["stale_after_sec"],
                host_proof_root=persisted["proof_root"],
            )
            return persisted
        return host

    def list_hosts(self) -> List[Dict[str, Any]]:
        with self.db() as db:
            ids = [row[0] for row in db.execute("SELECT host_id FROM hosts ORDER BY host_id")]
        return [self.refresh_state(self.get_host(host_id)) for host_id in ids]

    def set_mode(self, host_id: str, mode: str) -> Dict[str, Any]:
        if mode not in DESIRED_MODES:
            raise ValueError("BAD_HOST_MODE")
        host = self.refresh_state(self.get_host(host_id))
        if mode == "OFFLINE_LOCAL" and host["admission_state"] != "HOST_READY":
            raise RuntimeError("ONLINE_ADMISSION_REQUIRED_BEFORE_OFFLINE_LOCAL")
        row = self._raw_host(host, desired_mode=mode)
        updated = self._write_host(row)
        self.append_receipt(
            "HOST_MODE_DESIRED",
            host_id=host_id,
            desired_mode=mode,
            host_proof_root=updated["proof_root"],
        )
        return updated

    def select_host(self, capability: str, require_online: bool = True, authority_root: Optional[str] = None) -> Dict[str, Any]:
        candidates = []
        for host in self.list_hosts():
            if capability not in host["capabilities"]:
                continue
            if host["authority_root"] == "UNBOUND":
                continue
            if authority_root is not None and host["authority_root"] != authority_root:
                continue
            if host["admission_state"] != "HOST_READY":
                continue
            if require_online and host["observed_mode"] != "ONLINE":
                continue
            if not require_online and host["observed_mode"] not in {"ONLINE", "OFFLINE_LOCAL"}:
                continue
            candidates.append(host)
        if not candidates:
            raise LookupError(f"NO_HOST_FOR_CAPABILITY:{capability}")
        return sorted(candidates, key=lambda value: (value.get("heartbeat_age_sec") or 1e99, value["host_id"]))[0]

    def queue_work(self, capability: str, payload: Dict[str, Any], authority_root: str, external_mutation: bool = False) -> Dict[str, Any]:
        if not authority_root or authority_root == "UNBOUND":
            raise PermissionError("WORK_AUTHORITY_UNBOUND")
        host = self.select_host(capability, require_online=external_mutation, authority_root=authority_root)
        work_id = f"work:{uuid.uuid4()}"
        created = now_ns()
        row = {
            "work_id": work_id,
            "capability": capability,
            "payload_json": canon(payload),
            "authority_root": authority_root,
            "required_mode": "ONLINE" if external_mutation else "ONLINE_OR_OFFLINE_LOCAL",
            "assigned_host_id": host["host_id"],
            "state": "QUEUED",
            "created_ns": created,
            "updated_ns": created,
            "proof_root": "",
        }
        row["proof_root"] = sha({k: v for k, v in row.items() if k != "proof_root"})
        with self.db() as db:
            db.execute(
                "INSERT INTO work_queue VALUES(:work_id,:capability,:payload_json,:authority_root,:required_mode,:assigned_host_id,:state,:created_ns,:updated_ns,:proof_root)",
                row,
            )
        self.append_receipt(
            "WORK_QUEUED",
            work_id=work_id,
            host_id=host["host_id"],
            capability=capability,
            required_mode=row["required_mode"],
            authority_root=authority_root,
            work_proof_root=row["proof_root"],
        )
        return {**row, "payload": payload}

    def reconcile(self) -> Dict[str, Any]:
        hosts = self.list_hosts()
        stale = [host["host_id"] for host in hosts if host["admission_state"] == "STALE"]
        with self.db() as db:
            queued = db.execute("SELECT count(*) FROM work_queue WHERE state='QUEUED'").fetchone()[0]
            receipts = db.execute("SELECT count(*) FROM host_receipts").fetchone()[0]
        result = {
            "hosts": len(hosts),
            "stale_hosts": stale,
            "queued_work": int(queued),
            "receipts": int(receipts),
            "timestamp_ns": now_ns(),
        }
        self.append_receipt("HOST_FABRIC_RECONCILE", **result)
        return result


def receipt(event: str, **payload: Any) -> Dict[str, Any]:
    """Compatibility entrypoint used by host activation; writes to the default fabric DB."""
    return HostFabric().append_receipt(event, **payload)


def self_test() -> Dict[str, Any]:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        state_dir = Path(tmp) / "fabric"
        fabric = HostFabric(state_dir=state_dir)
        host = fabric.admit({
            "host_id": "host:test",
            "node_id": "node:test",
            "host_class": "VM",
            "os_name": "Linux",
            "architecture": "x86_64",
            "capabilities": ["host.shell.execute", "host.filesystem.read"],
            "carrier": "desktop-commander",
            "authority_root": "proof:test",
            "addresses": ["127.0.0.1"],
            "desired_mode": "ONLINE",
            "stale_after_sec": 30,
        })
        assert host["admission_state"] == "AUTHORITY_VERIFIED"
        host = fabric.heartbeat("host:test", "ONLINE")
        first_ready_root = host["proof_root"]
        assert host["admission_state"] == "HOST_READY" and host["observed_mode"] == "ONLINE"

        rediscovered = fabric.admit({
            "host_id": "host:test",
            "node_id": "node:test",
            "host_class": "VM",
            "os_name": "Linux",
            "architecture": "x86_64",
            "capabilities": ["host.shell.execute", "host.filesystem.read"],
            "carrier": "desktop-commander",
            "authority_root": "proof:test",
            "addresses": ["127.0.0.1"],
        })
        assert rediscovered["admission_state"] == "HOST_READY"
        assert rediscovered["observed_mode"] == "ONLINE"
        assert rediscovered["last_heartbeat_ns"] == host["last_heartbeat_ns"]

        assert fabric.select_host("host.shell.execute", authority_root="proof:test")["host_id"] == "host:test"
        desired = fabric.set_mode("host:test", "OFFLINE_LOCAL")
        assert desired["desired_mode"] == "OFFLINE_LOCAL"
        assert desired["observed_mode"] == "ONLINE"
        assert desired["proof_root"] not in {first_ready_root, ""}

        host = fabric.heartbeat("host:test", "OFFLINE_LOCAL")
        assert host["observed_mode"] == "OFFLINE_LOCAL"
        work = fabric.queue_work("host.filesystem.read", {"path": "/tmp/x"}, "proof:test", external_mutation=False)
        assert work["state"] == "QUEUED"

        try:
            fabric.queue_work("host.shell.execute", {"cmd": "true"}, "proof:test", external_mutation=True)
            raise AssertionError("external mutation should require observed ONLINE")
        except LookupError:
            pass
        try:
            fabric.select_host("host.filesystem.read", authority_root="proof:wrong")
            raise AssertionError("authority mismatch must not route")
        except LookupError:
            pass
        try:
            fabric.heartbeat("host:test", "CONNECTED")
            raise AssertionError("arbitrary observed modes must be rejected")
        except ValueError:
            pass

        with fabric.db() as db:
            rows = db.execute("SELECT previous_proof_root,proof_root FROM host_receipts ORDER BY seq").fetchall()
        assert len(rows) >= 4
        for index in range(1, len(rows)):
            assert rows[index][0] == rows[index - 1][1]
        assert (state_dir / "hosts.sqlite").exists()
        assert not (state_dir / "host_receipts.jsonl").exists()

        return {
            "status": "PASS",
            "checks": [
                "isolated_test_state", "admission", "heartbeat", "rediscovery_preserves_observation",
                "routing", "desired_observed_separation", "desired_mutation_re_roots_state",
                "offline_local", "external_mutation_gate", "authority_matched_routing",
                "observed_mode_validation", "transactional_receipt_chain",
            ],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--discover-local", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--heartbeat")
    parser.add_argument("--heartbeat-mode", default="ONLINE")
    parser.add_argument("--reconcile", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2, sort_keys=True))
        return 0
    fabric = HostFabric()
    if args.discover_local:
        print(json.dumps(fabric.discover_local(), indent=2, sort_keys=True))
        return 0
    if args.heartbeat:
        print(json.dumps(fabric.heartbeat(args.heartbeat, args.heartbeat_mode), indent=2, sort_keys=True))
        return 0
    if args.reconcile:
        print(json.dumps(fabric.reconcile(), indent=2, sort_keys=True))
        return 0
    if args.list:
        print(json.dumps(fabric.list_hosts(), indent=2, sort_keys=True))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
