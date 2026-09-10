#!/usr/bin/env python3
"""BRAINK host fabric: admission, capability routing, reconciliation, offline continuity.

This module composes the existing RuntimeRegistry with host-control carriers such as
Desktop Commander. It does not treat the carrier as identity or authority.
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
from typing import Any, Dict, List

from runtime.runtime_registry import RuntimeRegistry

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = Path(os.getenv("BRAINK_HOST_FABRIC_STATE", ROOT / ".kex" / "state" / "host_fabric"))
DB_PATH = STATE_DIR / "hosts.sqlite"
RUNTIME_DB = STATE_DIR / "runtimes.sqlite"
RECEIPTS = STATE_DIR / "host_receipts.jsonl"
DEFAULT_STALE_SEC = int(os.getenv("BRAINK_HOST_STALE_SEC", "30"))
OBSERVED_MODES = {"ONLINE", "OFFLINE_LOCAL"}
DESIRED_MODES = {"ONLINE", "OFFLINE_LOCAL"}


def canon(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(v: Any) -> str:
    return hashlib.sha256(canon(v).encode()).hexdigest()


def now_ns() -> int:
    return time.time_ns()


def receipt(event: str, **payload: Any) -> Dict[str, Any]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    prev = "0" * 64
    if RECEIPTS.exists():
        try:
            last = RECEIPTS.read_text(encoding="utf-8").splitlines()[-1]
            prev = json.loads(last).get("proof_root", prev)
        except Exception:
            pass
    body = {"event": event, "timestamp_ns": now_ns(), "previous_proof_root": prev, **payload}
    body["proof_root"] = sha(body)
    with RECEIPTS.open("a", encoding="utf-8") as fh:
        fh.write(canon(body) + "\n")
    return body


class HostFabric:
    def __init__(self, db_path: Path = DB_PATH):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path)
        self.runtime_registry = RuntimeRegistry(RUNTIME_DB)
        with self.db() as d:
            d.executescript("""
            CREATE TABLE IF NOT EXISTS hosts(
              host_id TEXT PRIMARY KEY,
              node_id TEXT,
              host_class TEXT,
              os_name TEXT,
              kernel TEXT,
              architecture TEXT,
              hostname TEXT,
              addresses_json TEXT,
              capabilities_json TEXT,
              supervisor TEXT,
              carrier TEXT,
              authority_root TEXT,
              desired_mode TEXT,
              observed_mode TEXT,
              admission_state TEXT,
              last_heartbeat_ns INTEGER,
              stale_after_sec INTEGER,
              proof_root TEXT,
              updated_ns INTEGER
            );
            CREATE TABLE IF NOT EXISTS work_queue(
              work_id TEXT PRIMARY KEY,
              capability TEXT,
              payload_json TEXT,
              authority_root TEXT,
              required_mode TEXT,
              assigned_host_id TEXT,
              state TEXT,
              created_ns INTEGER,
              updated_ns INTEGER,
              proof_root TEXT
            );
            """)

    def db(self):
        d = sqlite3.connect(self.db_path)
        d.row_factory = sqlite3.Row
        d.execute("PRAGMA journal_mode=WAL")
        d.execute("PRAGMA synchronous=FULL")
        return d

    def _host_root(self, row: Dict[str, Any]) -> str:
        return sha({k: v for k, v in row.items() if k != "proof_root"})

    def discover_local(self, carrier: str = "desktop-commander") -> Dict[str, Any]:
        host_id = f"host:{socket.gethostname()}"
        addresses = sorted({x[4][0] for x in socket.getaddrinfo(socket.gethostname(), None) if x and x[4]})
        capabilities = [
            "host.identity.read", "host.process.list", "host.process.spawn", "host.process.stop",
            "host.filesystem.read", "host.filesystem.write", "host.shell.execute",
            "host.network.inspect", "host.service.inspect", "host.service.control", "host.receipt.writeback"
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
            "desired_mode": "ONLINE",
            "observed_mode": "DISCOVERED",
            "stale_after_sec": DEFAULT_STALE_SEC,
        })

    def admit(self, h: Dict[str, Any]) -> Dict[str, Any]:
        required = ["host_id", "node_id", "os_name", "architecture", "capabilities", "carrier", "authority_root"]
        missing = [k for k in required if not h.get(k)]
        if missing:
            raise ValueError(f"HOST_ADMISSION_MISSING:{','.join(missing)}")
        authority_ok = h["authority_root"] != "UNBOUND"
        state = "AUTHORITY_VERIFIED" if authority_ok else "IDENTIFIED"
        row = {
            "host_id": h["host_id"], "node_id": h["node_id"], "host_class": h.get("host_class", "UNKNOWN"),
            "os_name": h["os_name"], "kernel": h.get("kernel", ""), "architecture": h["architecture"],
            "hostname": h.get("hostname", ""), "addresses_json": canon(h.get("addresses", [])),
            "capabilities_json": canon(sorted(set(h.get("capabilities", [])))), "supervisor": h.get("supervisor", "unknown"),
            "carrier": h["carrier"], "authority_root": h["authority_root"], "desired_mode": h.get("desired_mode", "ONLINE"),
            "observed_mode": h.get("observed_mode", "DISCOVERED"), "admission_state": state,
            "last_heartbeat_ns": int(h.get("last_heartbeat_ns", 0)), "stale_after_sec": int(h.get("stale_after_sec", DEFAULT_STALE_SEC)),
            "proof_root": "", "updated_ns": now_ns(),
        }
        row["proof_root"] = self._host_root(row)
        with self.db() as d:
            d.execute("""INSERT INTO hosts VALUES(:host_id,:node_id,:host_class,:os_name,:kernel,:architecture,:hostname,:addresses_json,
            :capabilities_json,:supervisor,:carrier,:authority_root,:desired_mode,:observed_mode,:admission_state,:last_heartbeat_ns,
            :stale_after_sec,:proof_root,:updated_ns) ON CONFLICT(host_id) DO UPDATE SET
            node_id=excluded.node_id,host_class=excluded.host_class,os_name=excluded.os_name,kernel=excluded.kernel,
            architecture=excluded.architecture,hostname=excluded.hostname,addresses_json=excluded.addresses_json,
            capabilities_json=excluded.capabilities_json,supervisor=excluded.supervisor,carrier=excluded.carrier,
            authority_root=excluded.authority_root,desired_mode=excluded.desired_mode,observed_mode=excluded.observed_mode,
            admission_state=excluded.admission_state,last_heartbeat_ns=excluded.last_heartbeat_ns,stale_after_sec=excluded.stale_after_sec,
            proof_root=excluded.proof_root,updated_ns=excluded.updated_ns""", row)
        receipt("HOST_ADMITTED", host_id=row["host_id"], admission_state=state, proof_root_observed=row["proof_root"])
        return self.get_host(row["host_id"])

    def get_host(self, host_id: str) -> Dict[str, Any]:
        with self.db() as d:
            r = d.execute("SELECT * FROM hosts WHERE host_id=?", (host_id,)).fetchone()
        if not r:
            raise KeyError(host_id)
        x = dict(r)
        x["addresses"] = json.loads(x.pop("addresses_json"))
        x["capabilities"] = json.loads(x.pop("capabilities_json"))
        return x

    def list_hosts(self) -> List[Dict[str, Any]]:
        with self.db() as d:
            ids = [r[0] for r in d.execute("SELECT host_id FROM hosts ORDER BY host_id")]
        return [self.refresh_state(self.get_host(i)) for i in ids]

    def heartbeat(self, host_id: str, observed_mode: str = "ONLINE") -> Dict[str, Any]:
        if observed_mode not in OBSERVED_MODES:
            raise ValueError("BAD_OBSERVED_HOST_MODE")
        h = self.get_host(host_id)
        if h["authority_root"] == "UNBOUND":
            raise PermissionError("HOST_AUTHORITY_UNBOUND")
        if observed_mode == "OFFLINE_LOCAL" and h["admission_state"] != "HOST_READY":
            raise RuntimeError("ONLINE_ADMISSION_REQUIRED_BEFORE_OFFLINE_LOCAL")
        t = now_ns()
        admission = "HOST_READY"
        with self.db() as d:
            d.execute("UPDATE hosts SET observed_mode=?,admission_state=?,last_heartbeat_ns=?,updated_ns=? WHERE host_id=?",
                      (observed_mode, admission, t, t, host_id))
        receipt("HOST_HEARTBEAT", host_id=host_id, observed_mode=observed_mode)
        return self.refresh_state(self.get_host(host_id))

    def refresh_state(self, h: Dict[str, Any]) -> Dict[str, Any]:
        if h["last_heartbeat_ns"]:
            age = (now_ns() - h["last_heartbeat_ns"]) / 1e9
            h["heartbeat_age_sec"] = round(age, 3)
            if age > h["stale_after_sec"] and h["observed_mode"] != "OFFLINE_LOCAL":
                h["observed_mode"] = "STALE"
                h["admission_state"] = "STALE"
        else:
            h["heartbeat_age_sec"] = None
        return h

    def set_mode(self, host_id: str, mode: str) -> Dict[str, Any]:
        if mode not in DESIRED_MODES:
            raise ValueError("BAD_HOST_MODE")
        h = self.get_host(host_id)
        if mode == "OFFLINE_LOCAL" and h["admission_state"] != "HOST_READY":
            raise RuntimeError("ONLINE_ADMISSION_REQUIRED_BEFORE_OFFLINE_LOCAL")
        with self.db() as d:
            d.execute("UPDATE hosts SET desired_mode=?,updated_ns=? WHERE host_id=?", (mode, now_ns(), host_id))
        receipt("HOST_MODE_DESIRED", host_id=host_id, desired_mode=mode)
        return self.get_host(host_id)

    def select_host(self, capability: str, require_online: bool = True) -> Dict[str, Any]:
        candidates = []
        for h in self.list_hosts():
            if capability not in h["capabilities"]:
                continue
            if h["authority_root"] == "UNBOUND":
                continue
            if require_online and h["observed_mode"] != "ONLINE":
                continue
            if h["admission_state"] != "HOST_READY":
                continue
            candidates.append(h)
        if not candidates:
            raise LookupError(f"NO_HOST_FOR_CAPABILITY:{capability}")
        return sorted(candidates, key=lambda x: (x.get("heartbeat_age_sec") or 1e99, x["host_id"]))[0]

    def queue_work(self, capability: str, payload: Dict[str, Any], authority_root: str, external_mutation: bool = False) -> Dict[str, Any]:
        if not authority_root or authority_root == "UNBOUND":
            raise PermissionError("WORK_AUTHORITY_UNBOUND")
        host = self.select_host(capability, require_online=external_mutation)
        state = "QUEUED"
        work_id = f"work:{uuid.uuid4()}"
        row = {"work_id": work_id, "capability": capability, "payload_json": canon(payload), "authority_root": authority_root,
               "required_mode": "ONLINE" if external_mutation else "ONLINE_OR_OFFLINE_LOCAL", "assigned_host_id": host["host_id"],
               "state": state, "created_ns": now_ns(), "updated_ns": now_ns(), "proof_root": ""}
        row["proof_root"] = sha({k: v for k, v in row.items() if k != "proof_root"})
        with self.db() as d:
            d.execute("INSERT INTO work_queue VALUES(:work_id,:capability,:payload_json,:authority_root,:required_mode,:assigned_host_id,:state,:created_ns,:updated_ns,:proof_root)", row)
        receipt("WORK_QUEUED", work_id=work_id, host_id=host["host_id"], capability=capability, required_mode=row["required_mode"])
        return {**row, "payload": payload}

    def reconcile(self) -> Dict[str, Any]:
        hosts = self.list_hosts()
        stale = [h["host_id"] for h in hosts if h["admission_state"] == "STALE"]
        with self.db() as d:
            pending = [dict(r) for r in d.execute("SELECT * FROM work_queue WHERE state='QUEUED' ORDER BY created_ns")]
        result = {"hosts": len(hosts), "stale_hosts": stale, "queued_work": len(pending), "timestamp_ns": now_ns()}
        receipt("HOST_FABRIC_RECONCILE", **result)
        return result


def self_test() -> Dict[str, Any]:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        f = HostFabric(Path(td) / "hosts.sqlite")
        h = f.admit({"host_id":"host:test","node_id":"node:test","host_class":"VM","os_name":"Linux","architecture":"x86_64",
                     "capabilities":["host.shell.execute","host.filesystem.read"],"carrier":"desktop-commander",
                     "authority_root":"proof:test","addresses":["127.0.0.1"],"desired_mode":"ONLINE","observed_mode":"DISCOVERED","stale_after_sec":30})
        assert h["admission_state"] == "AUTHORITY_VERIFIED"
        h = f.heartbeat("host:test", "ONLINE")
        assert h["admission_state"] == "HOST_READY" and h["observed_mode"] == "ONLINE"
        assert f.select_host("host.shell.execute")["host_id"] == "host:test"

        desired = f.set_mode("host:test", "OFFLINE_LOCAL")
        assert desired["desired_mode"] == "OFFLINE_LOCAL"
        assert desired["observed_mode"] == "ONLINE", "desired mode must not rewrite observed mode"

        h = f.heartbeat("host:test", "OFFLINE_LOCAL")
        assert h["observed_mode"] == "OFFLINE_LOCAL"
        work = f.queue_work("host.filesystem.read", {"path":"/tmp/x"}, "proof:test", external_mutation=False)
        assert work["state"] == "QUEUED"
        try:
            f.queue_work("host.shell.execute", {"cmd":"true"}, "proof:test", external_mutation=True)
            raise AssertionError("external mutation should require observed ONLINE")
        except LookupError:
            pass

        try:
            f.heartbeat("host:test", "CONNECTED")
            raise AssertionError("arbitrary observed modes must be rejected")
        except ValueError:
            pass

        return {"status":"PASS","checks":["admission","heartbeat","routing","desired_observed_separation","offline_local","external_mutation_gate","observed_mode_validation"]}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--discover-local", action="store_true")
    p.add_argument("--list", action="store_true")
    p.add_argument("--heartbeat")
    p.add_argument("--reconcile", action="store_true")
    args = p.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2)); return 0
    f = HostFabric()
    if args.discover_local:
        print(json.dumps(f.discover_local(), indent=2)); return 0
    if args.heartbeat:
        print(json.dumps(f.heartbeat(args.heartbeat), indent=2)); return 0
    if args.reconcile:
        print(json.dumps(f.reconcile(), indent=2)); return 0
    if args.list:
        print(json.dumps(f.list_hosts(), indent=2)); return 0
    p.print_help(); return 2

if __name__ == "__main__":
    raise SystemExit(main())
