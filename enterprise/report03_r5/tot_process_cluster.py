#!/usr/bin/env python3
"""Independent-process transport/persistence layer for the KEDDEH ToT safety model.

This module deliberately does not claim a production consensus protocol. It advances
one specific evidence boundary: each of the nine ToT voter identities runs as an
independent OS process, communicates through loopback TCP, and persists vote/log
state in its own SQLite WAL database with synchronous=FULL.

The process cluster retains an external orchestration client. Therefore autonomous
peer-to-peer election timers, authenticated peer identity, dynamic membership and
multi-host failure-domain independence remain outside the proven scope.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable
import json
import multiprocessing as mp
import os
import socket
import socketserver
import sqlite3
import time

from tot_safety_kernel import (
    VOTERS, GENESIS_ROOT, Proposal, SafetyViolation, canonical, h,
    is_global_quorum, quorum_shape,
)

SCHEMA = "keddeh.tot-process-cluster.v2"


class TransportFault(RuntimeError):
    pass


class NoQuorum(RuntimeError):
    pass


class IndeterminateCommit(RuntimeError):
    def __init__(self, entry: dict[str, Any], commit_acks: tuple[str, ...]):
        super().__init__("COMMIT_ACK_QUORUM_NOT_OBSERVED")
        self.entry = entry
        self.commit_acks = commit_acks


@dataclass
class FaultPlan:
    """Deterministic transport fault schedule applied by the cluster client."""
    blocked: set[tuple[str, str, str]] = field(default_factory=set)
    drop_response: set[tuple[str, str, str]] = field(default_factory=set)
    delay_ms: dict[tuple[str, str, str], int] = field(default_factory=dict)

    def blocked_link(self, sender: str, receiver: str, phase: str) -> bool:
        return (sender, receiver, phase) in self.blocked

    def dropped_response(self, sender: str, receiver: str, phase: str) -> bool:
        return (sender, receiver, phase) in self.drop_response

    def delay(self, sender: str, receiver: str, phase: str) -> float:
        return max(0, self.delay_ms.get((sender, receiver, phase), 0)) / 1000.0


class ReplicaStore:
    def __init__(self, voter: str, db_path: str | Path):
        if voter not in VOTERS:
            raise ValueError("UNKNOWN_TOT_VOTER")
        self.voter = voter
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, timeout=5.0)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS log (
              idx INTEGER PRIMARY KEY,
              term INTEGER NOT NULL,
              leader TEXT NOT NULL,
              previous_root TEXT NOT NULL,
              operation TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              payload_root TEXT NOT NULL,
              proposal_root TEXT NOT NULL,
              entry_root TEXT,
              committed INTEGER NOT NULL DEFAULT 0,
              certificate_json TEXT
            );
            """
        )
        defaults = {
            "schema": SCHEMA,
            "voter": voter,
            "current_term": "0",
            "voted_for": "",
            "commit_index": "0",
            "committed_root": GENESIS_ROOT,
        }
        with self.conn:
            for k, v in defaults.items():
                self.conn.execute("INSERT OR IGNORE INTO meta(key,value) VALUES(?,?)", (k, v))
        self.verify_integrity()

    def close(self) -> None:
        self.conn.close()

    def _get(self, key: str) -> str:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        if not row:
            raise SafetyViolation(f"REPLICA_META_MISSING:{key}")
        return str(row[0])

    def _set_many(self, values: dict[str, str]) -> None:
        for k, v in values.items():
            self.conn.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))

    @property
    def current_term(self) -> int:
        return int(self._get("current_term"))

    @property
    def voted_for(self) -> str | None:
        return self._get("voted_for") or None

    @property
    def commit_index(self) -> int:
        return int(self._get("commit_index"))

    @property
    def committed_root(self) -> str:
        return self._get("committed_root")

    def _row_to_entry(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "term": int(row["term"]),
            "index": int(row["idx"]),
            "leader": row["leader"],
            "previous_root": row["previous_root"],
            "operation": row["operation"],
            "payload": json.loads(row["payload_json"]),
            "payload_root": row["payload_root"],
            "proposal_root": row["proposal_root"],
            "certificate": json.loads(row["certificate_json"]) if row["certificate_json"] else None,
            "entry_root": row["entry_root"],
            "committed": bool(row["committed"]),
        }

    def entries(self, *, committed_only: bool = False) -> list[dict[str, Any]]:
        q = "SELECT * FROM log"
        if committed_only:
            q += " WHERE committed=1"
        q += " ORDER BY idx"
        return [self._row_to_entry(r) for r in self.conn.execute(q)]

    def _last(self) -> tuple[int, str]:
        row = self.conn.execute("SELECT idx, COALESCE(entry_root, proposal_root) AS root FROM log ORDER BY idx DESC LIMIT 1").fetchone()
        if not row:
            return 0, GENESIS_ROOT
        return int(row["idx"]), str(row["root"])

    def _committed_roots(self) -> list[str]:
        return [e["entry_root"] for e in self.entries(committed_only=True)]

    def verify_integrity(self) -> dict[str, Any]:
        prev = GENESIS_ROOT
        expected = 1
        latest_committed = 0
        latest_committed_root = GENESIS_ROOT
        seen_uncommitted = False
        for row in self.conn.execute("SELECT * FROM log ORDER BY idx"):
            e = self._row_to_entry(row)
            if e["index"] != expected:
                raise SafetyViolation("REPLICA_LOG_INDEX_DISCONTINUITY")
            if e["previous_root"] != prev:
                raise SafetyViolation("REPLICA_LOG_PREVIOUS_ROOT_MISMATCH")
            if h(e["payload"]) != e["payload_root"]:
                raise SafetyViolation("REPLICA_PAYLOAD_ROOT_MISMATCH")
            proposal_body = {
                "schema": "keddeh.tot-proposal.v1",
                "kernel_id": "KEX://SAFETY/TOT/DOMAIN-FABRIC/V1",
                "term": e["term"], "index": e["index"], "leader": e["leader"],
                "previous_root": e["previous_root"], "operation": e["operation"],
                "payload_root": e["payload_root"],
            }
            if h(proposal_body) != e["proposal_root"]:
                raise SafetyViolation("REPLICA_PROPOSAL_ROOT_MISMATCH")
            if e["committed"]:
                if seen_uncommitted:
                    raise SafetyViolation("REPLICA_COMMITTED_AFTER_UNCOMMITTED_GAP")
                cert = e["certificate"] or {}
                if not is_global_quorum(cert.get("voters", [])):
                    raise SafetyViolation("REPLICA_COMMIT_CERTIFICATE_INVALID")
                body = {k: e[k] for k in ["term","index","leader","previous_root","operation","payload","payload_root","proposal_root","certificate"]}
                if h(body) != e["entry_root"]:
                    raise SafetyViolation("REPLICA_ENTRY_ROOT_MISMATCH")
                latest_committed = e["index"]
                latest_committed_root = e["entry_root"]
                prev = e["entry_root"]
            else:
                seen_uncommitted = True
                prev = e["proposal_root"]
            expected += 1
        if latest_committed != self.commit_index or latest_committed_root != self.committed_root:
            raise SafetyViolation("REPLICA_COMMIT_HEAD_MISMATCH")
        return {"state": "REPLICA_VERIFIED", "voter": self.voter, "entries": expected - 1, "commit_index": latest_committed, "committed_root": latest_committed_root}

    def state(self) -> dict[str, Any]:
        self.verify_integrity()
        last_index, last_root = self._last()
        journal = self.conn.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = int(self.conn.execute("PRAGMA synchronous").fetchone()[0])
        return {
            "schema": SCHEMA, "voter": self.voter, "pid": os.getpid(),
            "current_term": self.current_term, "voted_for": self.voted_for,
            "commit_index": self.commit_index, "committed_root": self.committed_root,
            "last_index": last_index, "last_root": last_root,
            "committed_roots": self._committed_roots(),
            "sqlite": {"journal_mode": str(journal).upper(), "synchronous": synchronous, "db_path": str(self.db_path)},
        }

    def vote(self, req: dict[str, Any]) -> dict[str, Any]:
        term = int(req["term"])
        candidate = str(req["candidate"])
        chain = list(req.get("candidate_committed_roots", []))
        if term < self.current_term:
            return {"vote": False, "reason": "STALE_TERM", "current_term": self.current_term}
        if self.commit_index > len(chain):
            return {"vote": False, "reason": "CANDIDATE_COMMITTED_PREFIX_SHORTER"}
        if self.commit_index and chain[self.commit_index - 1] != self.committed_root:
            return {"vote": False, "reason": "CANDIDATE_MISSING_COMMITTED_PREFIX"}
        if term == self.current_term and self.voted_for not in (None, candidate):
            return {"vote": False, "reason": "ALREADY_VOTED_OTHER"}
        with self.conn:
            if term > self.current_term:
                self._set_many({"current_term": str(term), "voted_for": candidate})
            elif not self.voted_for:
                self._set_many({"voted_for": candidate})
        return {"vote": True, "voter": self.voter, "term": term, "commit_index": self.commit_index, "committed_root": self.committed_root}

    @staticmethod
    def _valid_election_cert(cert: dict[str, Any], leader: str, term: int) -> bool:
        return cert.get("candidate") == leader and int(cert.get("term", -1)) == term and is_global_quorum(cert.get("voters", []))

    def append(self, req: dict[str, Any]) -> dict[str, Any]:
        p = req["proposal"]
        term = int(p["term"])
        leader = p["leader"]
        if not self._valid_election_cert(req.get("election_certificate", {}), leader, term):
            return {"accepted": False, "reason": "INVALID_ELECTION_CERTIFICATE"}
        if term < self.current_term:
            return {"accepted": False, "reason": "STALE_TERM"}
        if term > self.current_term:
            with self.conn:
                self._set_many({"current_term": str(term), "voted_for": ""})
        idx = int(p["index"])
        existing = self.conn.execute("SELECT * FROM log WHERE idx=?", (idx,)).fetchone()
        if existing:
            e = self._row_to_entry(existing)
            if e["proposal_root"] == p["proposal_root"]:
                return {"accepted": True, "idempotent": True, "voter": self.voter}
            if e.get("committed"):
                return {"accepted": False, "reason": "CONFLICTING_COMMITTED_ENTRY_AT_INDEX"}
            # A failed minority prepare must not poison this index forever.
            # Only a strictly higher elected term may supersede an uncommitted entry,
            # and only when it still extends this replica's committed head.
            if term <= int(e["term"]):
                return {"accepted": False, "reason": "CONFLICTING_UNCOMMITTED_ENTRY_SAME_OR_OLDER_TERM"}
            if idx != self.commit_index + 1 or p["previous_root"] != self.committed_root:
                return {"accepted": False, "reason": "UNCOMMITTED_SUPERSESSION_DOES_NOT_EXTEND_COMMITTED_HEAD"}
            with self.conn:
                self.conn.execute("DELETE FROM log WHERE idx>=? AND committed=0", (idx,))
        last_idx, last_root = self._last()
        if idx != last_idx + 1:
            return {"accepted": False, "reason": "APPEND_INDEX_GAP", "last_index": last_idx}
        if p["previous_root"] != last_root:
            return {"accepted": False, "reason": "APPEND_PREVIOUS_ROOT_MISMATCH", "last_root": last_root}
        if h(p["payload"]) != p["payload_root"]:
            return {"accepted": False, "reason": "PAYLOAD_ROOT_MISMATCH"}
        with self.conn:
            self.conn.execute(
                "INSERT INTO log(idx,term,leader,previous_root,operation,payload_json,payload_root,proposal_root,committed) VALUES(?,?,?,?,?,?,?,?,0)",
                (idx, term, leader, p["previous_root"], p["operation"], canonical(p["payload"]), p["payload_root"], p["proposal_root"]),
            )
        return {"accepted": True, "idempotent": False, "voter": self.voter, "index": idx}

    def commit(self, req: dict[str, Any]) -> dict[str, Any]:
        e = req["entry"]
        idx = int(e["index"])
        cert = e.get("certificate", {})
        if not is_global_quorum(cert.get("voters", [])):
            return {"committed": False, "reason": "INVALID_COMMIT_CERTIFICATE"}
        row = self.conn.execute("SELECT * FROM log WHERE idx=?", (idx,)).fetchone()
        if not row:
            return {"committed": False, "reason": "MISSING_PREPARED_ENTRY"}
        cur = self._row_to_entry(row)
        if cur["proposal_root"] != e["proposal_root"]:
            return {"committed": False, "reason": "PROPOSAL_ROOT_MISMATCH"}
        if cur["committed"]:
            if cur["entry_root"] != e["entry_root"]:
                return {"committed": False, "reason": "CONFLICTING_COMMIT_ROOT"}
            return {"committed": True, "idempotent": True, "voter": self.voter}
        if idx != self.commit_index + 1 or e["previous_root"] != self.committed_root:
            return {"committed": False, "reason": "NONCONTIGUOUS_COMMIT"}
        body = {k: e[k] for k in ["term","index","leader","previous_root","operation","payload","payload_root","proposal_root","certificate"]}
        if h(body) != e["entry_root"]:
            return {"committed": False, "reason": "ENTRY_ROOT_MISMATCH"}
        with self.conn:
            self.conn.execute("UPDATE log SET committed=1, entry_root=?, certificate_json=? WHERE idx=?", (e["entry_root"], canonical(cert), idx))
            self._set_many({"commit_index": str(idx), "committed_root": e["entry_root"], "current_term": str(max(self.current_term, int(e["term"])))})
        self.verify_integrity()
        return {"committed": True, "idempotent": False, "voter": self.voter, "commit_index": idx, "committed_root": e["entry_root"]}

    def install_committed(self, req: dict[str, Any]) -> dict[str, Any]:
        entries = list(req.get("entries", []))
        prev = GENESIS_ROOT
        expected = 1
        for e in entries:
            if e["index"] != expected or e["previous_root"] != prev:
                raise SafetyViolation("INSTALL_LOG_CHAIN_INVALID")
            if not is_global_quorum(e.get("certificate", {}).get("voters", [])):
                raise SafetyViolation("INSTALL_CERTIFICATE_INVALID")
            body = {k: e[k] for k in ["term","index","leader","previous_root","operation","payload","payload_root","proposal_root","certificate"]}
            if h(body) != e["entry_root"]:
                raise SafetyViolation("INSTALL_ENTRY_ROOT_INVALID")
            prev = e["entry_root"]
            expected += 1
        with self.conn:
            self.conn.execute("DELETE FROM log")
            for e in entries:
                self.conn.execute(
                    "INSERT INTO log(idx,term,leader,previous_root,operation,payload_json,payload_root,proposal_root,entry_root,committed,certificate_json) VALUES(?,?,?,?,?,?,?,?,?,1,?)",
                    (e["index"],e["term"],e["leader"],e["previous_root"],e["operation"],canonical(e["payload"]),e["payload_root"],e["proposal_root"],e["entry_root"],canonical(e["certificate"])),
                )
            self._set_many({"commit_index": str(len(entries)), "committed_root": prev, "current_term": str(max([self.current_term] + [int(e["term"]) for e in entries])), "voted_for": ""})
        return self.verify_integrity()

    def handle(self, req: dict[str, Any]) -> dict[str, Any]:
        op = req.get("op")
        if op == "STATE": return self.state()
        if op == "LOG": return {"entries": self.entries(committed_only=bool(req.get("committed_only")))}
        if op == "VOTE": return self.vote(req)
        if op == "APPEND": return self.append(req)
        if op == "COMMIT": return self.commit(req)
        if op == "INSTALL_COMMITTED": return self.install_committed(req)
        if op == "VERIFY": return self.verify_integrity()
        if op == "PING": return {"pong": True, "voter": self.voter, "pid": os.getpid()}
        raise ValueError(f"UNKNOWN_RPC:{op}")


class _ReplicaTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        try:
            raw = self.rfile.readline(8 * 1024 * 1024)
            req = json.loads(raw.decode("utf-8"))
            if req.get("op") == "SHUTDOWN":
                out = {"shutdown": True}
                self.wfile.write((canonical(out) + "\n").encode())
                self.wfile.flush()
                # Shutdown from a separate process-safe thread is unnecessary; process will be terminated by parent.
                return
            out = self.server.store.handle(req)  # type: ignore[attr-defined]
            self.wfile.write((canonical({"ok": True, "result": out}) + "\n").encode())
        except Exception as exc:
            self.wfile.write((canonical({"ok": False, "error": type(exc).__name__, "message": str(exc)}) + "\n").encode())


def _serve_replica(voter: str, db_path: str, ready_q: mp.Queue) -> None:
    store = ReplicaStore(voter, db_path)
    server = _ReplicaTCPServer(("127.0.0.1", 0), _Handler)
    server.store = store  # type: ignore[attr-defined]
    ready_q.put({"voter": voter, "port": server.server_address[1], "pid": os.getpid()})
    try:
        server.serve_forever(poll_interval=0.05)
    finally:
        store.close()
        server.server_close()


class ProcessCluster:
    def __init__(self, root: str | Path, *, rpc_timeout: float = 1.5, auto_start: bool = True):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.rpc_timeout = rpc_timeout
        self.processes: dict[str, mp.Process] = {}
        self.ports: dict[str, int] = {}
        self.pids: dict[str, int] = {}
        self.term = 0
        self.leader: str | None = None
        self.election_certificate: dict[str, Any] | None = None
        if auto_start:
            self.start_all()

    def _db_path(self, voter: str) -> Path:
        return self.root / "voters" / f"{voter.replace(':','__')}.sqlite3"

    def start_node(self, voter: str) -> None:
        if voter in self.processes and self.processes[voter].is_alive():
            return
        ctx = mp.get_context("forkserver")
        q = ctx.Queue()
        p = ctx.Process(target=_serve_replica, args=(voter, str(self._db_path(voter)), q), daemon=True)
        p.start()
        info = q.get(timeout=5)
        self.processes[voter] = p
        self.ports[voter] = int(info["port"])
        self.pids[voter] = int(info["pid"])
        self._rpc(voter, {"op":"PING"}, sender="BOOT", phase="PING", fault=None)

    def start_all(self) -> None:
        for v in VOTERS:
            self.start_node(v)

    def kill_node(self, voter: str) -> None:
        p = self.processes.get(voter)
        if p and p.is_alive():
            p.terminate(); p.join(timeout=2)
        self.processes.pop(voter, None)
        self.ports.pop(voter, None)

    def restart_node(self, voter: str) -> None:
        self.kill_node(voter)
        self.start_node(voter)

    def stop(self) -> None:
        for v in list(self.processes):
            self.kill_node(v)

    def __enter__(self) -> "ProcessCluster": return self
    def __exit__(self, *_: Any) -> None: self.stop()

    def _rpc(self, voter: str, request: dict[str, Any], *, sender: str, phase: str, fault: FaultPlan | None) -> dict[str, Any]:
        if voter not in self.ports:
            raise TransportFault(f"NODE_DOWN:{voter}")
        if fault and fault.blocked_link(sender, voter, phase):
            raise TransportFault(f"LINK_BLOCKED:{sender}->{voter}:{phase}")
        if fault:
            d = fault.delay(sender, voter, phase)
            if d: time.sleep(d)
        try:
            with socket.create_connection(("127.0.0.1", self.ports[voter]), timeout=self.rpc_timeout) as s:
                s.settimeout(self.rpc_timeout)
                s.sendall((canonical(request) + "\n").encode())
                if fault and fault.dropped_response(sender, voter, phase):
                    raise TransportFault(f"RESPONSE_DROPPED:{sender}<-{voter}:{phase}")
                f = s.makefile("rb")
                line = f.readline(8 * 1024 * 1024)
                if not line:
                    raise TransportFault(f"EMPTY_RESPONSE:{voter}")
                out = json.loads(line.decode())
                if not out.get("ok", True):
                    raise SafetyViolation(f"REMOTE_{out.get('error')}:{out.get('message')}")
                return out.get("result", out)
        except (OSError, TimeoutError) as exc:
            raise TransportFault(f"RPC_FAILED:{voter}:{phase}:{exc}") from exc

    def state(self, voter: str) -> dict[str, Any]:
        return self._rpc(voter, {"op":"STATE"}, sender="OBSERVER", phase="STATE", fault=None)

    def all_states(self) -> dict[str, dict[str, Any]]:
        out = {}
        for v in VOTERS:
            try: out[v] = self.state(v)
            except TransportFault: out[v] = {"voter":v,"state":"DOWN"}
        return out

    def log(self, voter: str, *, committed_only: bool = True) -> list[dict[str, Any]]:
        return self._rpc(voter, {"op":"LOG","committed_only":committed_only}, sender="OBSERVER", phase="LOG", fault=None)["entries"]

    @staticmethod
    def _election_cert(term: int, candidate: str, voters: Iterable[str]) -> dict[str, Any]:
        voters = tuple(sorted(set(voters)))
        body = {"schema":"keddeh.tot-process-election-certificate.v1","term":term,"candidate":candidate,"voters":list(voters),"groups":quorum_shape(voters),"global_quorum":is_global_quorum(voters)}
        body["certificate_root"] = h(body)
        return body

    @staticmethod
    def _commit_cert(term: int, index: int, proposal_root: str, voters: Iterable[str]) -> dict[str, Any]:
        voters = tuple(sorted(set(voters)))
        body = {"schema":"keddeh.tot-process-commit-certificate.v1","kind":"COMMIT","term":term,"index":index,"subject":proposal_root,"voters":list(voters),"groups":quorum_shape(voters),"global_quorum":is_global_quorum(voters)}
        body["certificate_root"] = h(body)
        return body

    def elect(self, *, term: int, candidate: str, reachable: Iterable[str] = VOTERS, fault: FaultPlan | None = None) -> dict[str, Any]:
        if candidate not in self.ports:
            raise TransportFault("CANDIDATE_DOWN")
        candidate_roots = [e["entry_root"] for e in self.log(candidate, committed_only=True)]
        yes = []
        reasons = {}
        for voter in sorted(set(reachable)):
            try:
                r = self._rpc(voter, {"op":"VOTE","term":term,"candidate":candidate,"candidate_committed_roots":candidate_roots}, sender=candidate, phase="VOTE", fault=fault)
                if r.get("vote"): yes.append(voter)
                else: reasons[voter] = r.get("reason")
            except TransportFault as exc:
                reasons[voter] = str(exc)
        if not is_global_quorum(yes):
            raise NoQuorum(canonical({"phase":"ELECTION","yes":yes,"reasons":reasons}))
        self.term = term
        self.leader = candidate
        self.election_certificate = self._election_cert(term, candidate, yes)
        return {"state":"PROCESS_LEADER_ELECTED","term":term,"leader":candidate,"yes":yes,"certificate":self.election_certificate,"rejections":reasons}

    def transition(self, operation: str, payload: dict[str, Any], *, reachable: Iterable[str] = VOTERS, fault: FaultPlan | None = None) -> dict[str, Any]:
        if not self.leader or not self.election_certificate:
            raise SafetyViolation("PROCESS_LEADER_REQUIRED")
        leader_state = self.state(self.leader)
        proposal = Proposal.create(term=self.term,index=int(leader_state["commit_index"])+1,leader=self.leader,previous_root=leader_state["committed_root"],operation=operation,payload=payload)
        pd = asdict(proposal)
        prepared = []
        prepare_rejections = {}
        for voter in sorted(set(reachable)):
            try:
                r = self._rpc(voter, {"op":"APPEND","proposal":pd,"election_certificate":self.election_certificate}, sender=self.leader, phase="APPEND", fault=fault)
                if r.get("accepted"): prepared.append(voter)
                else: prepare_rejections[voter]=r.get("reason")
            except TransportFault as exc:
                prepare_rejections[voter]=str(exc)
        if not is_global_quorum(prepared):
            raise NoQuorum(canonical({"phase":"APPEND","prepared":prepared,"rejections":prepare_rejections}))
        cert = self._commit_cert(self.term, proposal.index, proposal.proposal_root, prepared)
        entry = {
            "term":proposal.term,"index":proposal.index,"leader":proposal.leader,"previous_root":proposal.previous_root,
            "operation":proposal.operation,"payload":proposal.payload,"payload_root":proposal.payload_root,"proposal_root":proposal.proposal_root,
            "certificate":cert,
        }
        entry["entry_root"] = h(entry)
        committed = []
        commit_rejections = {}
        for voter in prepared:
            try:
                r = self._rpc(voter, {"op":"COMMIT","entry":entry}, sender=self.leader, phase="COMMIT", fault=fault)
                if r.get("committed"): committed.append(voter)
                else: commit_rejections[voter]=r.get("reason")
            except TransportFault as exc:
                commit_rejections[voter]=str(exc)
        if not is_global_quorum(committed):
            raise IndeterminateCommit(entry, tuple(committed))
        return {"state":"PROCESS_REPLICATED_COMMIT","entry":entry,"prepared":prepared,"committed":committed,"prepare_rejections":prepare_rejections,"commit_rejections":commit_rejections}

    def recover_indeterminate(self, entry: dict[str, Any], *, fault: FaultPlan | None = None) -> dict[str, Any]:
        holders = []
        committed_already = []
        for v in VOTERS:
            if v not in self.ports: continue
            try:
                entries = self.log(v, committed_only=False)
            except TransportFault:
                continue
            match = next((e for e in entries if e["index"] == entry["index"] and e["proposal_root"] == entry["proposal_root"]), None)
            if match:
                holders.append(v)
                if match.get("committed"): committed_already.append(v)
        cert_voters = set(entry.get("certificate", {}).get("voters", []))
        qualified_holders = sorted(cert_voters.intersection(holders))
        if not is_global_quorum(qualified_holders):
            return {"state":"RECOVERY_CANNOT_PROVE_PREPARE_QUORUM","holders":holders,"qualified_holders":qualified_holders}
        committed = []
        for v in qualified_holders:
            try:
                r = self._rpc(v, {"op":"COMMIT","entry":entry}, sender=entry["leader"], phase="RECOVER_COMMIT", fault=fault)
                if r.get("committed"): committed.append(v)
            except TransportFault:
                pass
        if not is_global_quorum(committed):
            return {"state":"RECOVERY_COMMIT_QUORUM_NOT_REACHED","holders":holders,"committed":committed}
        return {"state":"RECOVERED_COMMITTED_ENTRY","holders":holders,"committed":committed,"entry_root":entry["entry_root"]}

    def canonical_committed_log(self) -> list[dict[str, Any]]:
        """Read a committed chain supported by a structural global quorum per index."""
        logs: dict[str,list[dict[str,Any]]] = {}
        for v in VOTERS:
            if v in self.ports:
                try: logs[v] = self.log(v, committed_only=True)
                except TransportFault: pass
        result = []
        index = 1
        prev = GENESIS_ROOT
        while True:
            candidates: dict[str, list[str]] = {}
            entries: dict[str, dict[str, Any]] = {}
            for voter, log in logs.items():
                if len(log) >= index:
                    e = log[index-1]
                    if e["index"] == index and e["previous_root"] == prev:
                        candidates.setdefault(e["entry_root"], []).append(voter)
                        entries[e["entry_root"]] = e
            qualified = [(root,voters) for root,voters in candidates.items() if is_global_quorum(voters)]
            if not qualified: break
            if len(qualified) != 1:
                raise SafetyViolation("MULTIPLE_COMMITTED_ROOTS_HAVE_GLOBAL_SUPPORT")
            root, _ = qualified[0]
            result.append(entries[root])
            prev = root
            index += 1
        return result

    def catch_up(self, voter: str) -> dict[str, Any]:
        entries = self.canonical_committed_log()
        return self._rpc(voter, {"op":"INSTALL_COMMITTED","entries":entries}, sender="RECOVERY", phase="INSTALL", fault=None)

    def verify_all(self) -> dict[str, Any]:
        states = {}
        for v in VOTERS:
            if v not in self.ports: continue
            states[v] = self._rpc(v, {"op":"VERIFY"}, sender="OBSERVER", phase="VERIFY", fault=None)
        return {"state":"ALL_LIVE_REPLICAS_VERIFIED","replicas":states}