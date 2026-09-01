from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Set, Tuple

ZERO = "0" * 64

def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def sha(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()

@dataclass(frozen=True)
class Membership:
    epoch: int
    members: Tuple[str, ...]
    root: str

    @classmethod
    def create(cls, epoch: int, members: Iterable[str]) -> "Membership":
        ordered = tuple(sorted(set(members)))
        if len(ordered) < 3:
            raise ValueError("membership requires at least three unique nodes")
        body = {"epoch": int(epoch), "members": ordered}
        return cls(int(epoch), ordered, sha(body))

    @property
    def quorum(self) -> int:
        return len(self.members) // 2 + 1

@dataclass(frozen=True)
class FenceProposal:
    resource: str
    generation: int
    previous_generation: int
    owner: str
    nonce: str
    membership_epoch: int
    membership_root: str
    proposal_root: str

    @classmethod
    def create(cls, *, resource: str, generation: int, previous_generation: int,
               owner: str, membership: Membership, nonce: Optional[str] = None):
        nonce = nonce or uuid.uuid4().hex
        body = {
            "schema": "kex.mesh.fence.proposal/v1",
            "resource": resource,
            "generation": int(generation),
            "previous_generation": int(previous_generation),
            "owner": owner,
            "nonce": nonce,
            "membership_epoch": membership.epoch,
            "membership_root": membership.root,
        }
        return cls(
            resource=resource,
            generation=int(generation),
            previous_generation=int(previous_generation),
            owner=owner,
            nonce=nonce,
            membership_epoch=membership.epoch,
            membership_root=membership.root,
            proposal_root=sha(body),
        )

@dataclass(frozen=True)
class FenceVote:
    voter: str
    generation: int
    proposal_root: str
    vote_root: str

@dataclass(frozen=True)
class FenceCertificate:
    resource: str
    generation: int
    previous_generation: int
    owner: str
    nonce: str
    membership_epoch: int
    membership_root: str
    proposal_root: str
    voters: Tuple[str, ...]
    vote_roots: Tuple[str, ...]
    certificate_root: str

    @classmethod
    def build(cls, proposal: FenceProposal, votes: Iterable[FenceVote], membership: Membership):
        votes = tuple(sorted(votes, key=lambda v: v.voter))
        voters = tuple(v.voter for v in votes)
        if proposal.membership_epoch != membership.epoch or proposal.membership_root != membership.root:
            raise ValueError("proposal membership mismatch")
        if len(set(voters)) != len(voters):
            raise ValueError("duplicate voters")
        if len(voters) < membership.quorum:
            raise ValueError("insufficient quorum")
        if any(v.voter not in membership.members for v in votes):
            raise ValueError("untrusted voter")
        if any(v.generation != proposal.generation or v.proposal_root != proposal.proposal_root for v in votes):
            raise ValueError("vote mismatch")
        core = {
            "schema": "kex.mesh.fence.certificate/v1",
            "resource": proposal.resource,
            "generation": proposal.generation,
            "previous_generation": proposal.previous_generation,
            "owner": proposal.owner,
            "nonce": proposal.nonce,
            "membership_epoch": proposal.membership_epoch,
            "membership_root": proposal.membership_root,
            "proposal_root": proposal.proposal_root,
            "voters": voters,
            "vote_roots": tuple(v.vote_root for v in votes),
        }
        return cls(**{k: core[k] for k in (
            "resource","generation","previous_generation","owner","nonce",
            "membership_epoch","membership_root","proposal_root","voters","vote_roots"
        )}, certificate_root=sha(core))

class DurableFenceNode:
    """One node's durable one-vote-per-resource+generation authority state."""

    def __init__(self, node_id: str, db_path: Path, membership: Membership):
        if node_id not in membership.members:
            raise ValueError("node not in membership")
        self.node_id = node_id
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.membership = membership
        self._bootstrap()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=5, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _bootstrap(self):
        with self._connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS fence_votes(
              resource TEXT NOT NULL,
              generation INTEGER NOT NULL,
              proposal_root TEXT NOT NULL,
              voter TEXT NOT NULL,
              vote_root TEXT NOT NULL,
              membership_epoch INTEGER NOT NULL,
              membership_root TEXT NOT NULL,
              created_ns INTEGER NOT NULL,
              PRIMARY KEY(resource, generation)
            );
            CREATE TABLE IF NOT EXISTS high_water(
              resource TEXT PRIMARY KEY,
              committed_generation INTEGER NOT NULL,
              certificate_root TEXT NOT NULL,
              updated_ns INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS replay_high_water(
              origin TEXT PRIMARY KEY,
              counter INTEGER NOT NULL
            );
            """)

    def observe_counter(self, origin: str, counter: int) -> bool:
        """Persistent monotonic replay guard."""
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT counter FROM replay_high_water WHERE origin=?", (origin,)).fetchone()
            prior = -1 if row is None else int(row[0])
            if int(counter) <= prior:
                c.rollback()
                return False
            c.execute("""
              INSERT INTO replay_high_water(origin,counter) VALUES(?,?)
              ON CONFLICT(origin) DO UPDATE SET counter=excluded.counter
            """, (origin, int(counter)))
            c.commit()
            return True

    def vote(self, proposal: FenceProposal) -> FenceVote:
        if proposal.membership_epoch != self.membership.epoch or proposal.membership_root != self.membership.root:
            raise ValueError("membership epoch/root mismatch")
        if proposal.owner not in self.membership.members:
            raise ValueError("owner not trusted")
        body = {
            "schema": "kex.mesh.fence.vote/v1",
            "voter": self.node_id,
            "resource": proposal.resource,
            "generation": proposal.generation,
            "proposal_root": proposal.proposal_root,
            "membership_epoch": proposal.membership_epoch,
            "membership_root": proposal.membership_root,
        }
        vr = sha(body)
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            existing = c.execute(
                "SELECT proposal_root,vote_root FROM fence_votes WHERE resource=? AND generation=?",
                (proposal.resource, proposal.generation)
            ).fetchone()
            if existing is not None:
                if existing[0] != proposal.proposal_root:
                    c.rollback()
                    raise RuntimeError("CONFLICTING_VOTE_REJECTED")
                c.commit()
                return FenceVote(self.node_id, proposal.generation, proposal.proposal_root, existing[1])
            c.execute("""
              INSERT INTO fence_votes(resource,generation,proposal_root,voter,vote_root,membership_epoch,membership_root,created_ns)
              VALUES(?,?,?,?,?,?,?,?)
            """, (
                proposal.resource, proposal.generation, proposal.proposal_root, self.node_id, vr,
                proposal.membership_epoch, proposal.membership_root, time.time_ns()
            ))
            c.commit()
        return FenceVote(self.node_id, proposal.generation, proposal.proposal_root, vr)

    def commit_certificate(self, cert: FenceCertificate):
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT committed_generation FROM high_water WHERE resource=?", (cert.resource,)).fetchone()
            prior = 0 if row is None else int(row[0])
            if cert.previous_generation != prior or cert.generation != prior + 1:
                c.rollback()
                raise RuntimeError("NON_CONTIGUOUS_FENCE_COMMIT")
            c.execute("""
              INSERT INTO high_water(resource,committed_generation,certificate_root,updated_ns)
              VALUES(?,?,?,?)
              ON CONFLICT(resource) DO UPDATE SET
                committed_generation=excluded.committed_generation,
                certificate_root=excluded.certificate_root,
                updated_ns=excluded.updated_ns
            """, (cert.resource, cert.generation, cert.certificate_root, time.time_ns()))
            c.commit()

    def committed_generation(self, resource: str) -> int:
        with self._connect() as c:
            row = c.execute("SELECT committed_generation FROM high_water WHERE resource=?", (resource,)).fetchone()
            return 0 if row is None else int(row[0])

class ResourceFenceGate:
    """The protected resource, not the lock service, rejects stale fences."""

    def __init__(self):
        self._accepted_generation: Dict[str, int] = {}
        self._state: Dict[str, dict] = {}

    def mutate(self, cert: FenceCertificate, payload: dict, membership: Membership) -> dict:
        if cert.membership_epoch != membership.epoch or cert.membership_root != membership.root:
            raise RuntimeError("STALE_MEMBERSHIP_CERTIFICATE")
        if len(set(cert.voters)) < membership.quorum:
            raise RuntimeError("NO_QUORUM")
        if any(v not in membership.members for v in cert.voters):
            raise RuntimeError("UNTRUSTED_CERTIFICATE_VOTER")
        prior = self._accepted_generation.get(cert.resource, 0)
        if cert.generation <= prior:
            raise RuntimeError("STALE_FENCE_REJECTED")
        if cert.previous_generation != prior:
            raise RuntimeError("FENCE_GAP_REJECTED")
        self._accepted_generation[cert.resource] = cert.generation
        state = {
            "resource": cert.resource,
            "generation": cert.generation,
            "owner": cert.owner,
            "certificate_root": cert.certificate_root,
            "payload": payload,
            "state_root": sha({
                "resource": cert.resource,
                "generation": cert.generation,
                "owner": cert.owner,
                "certificate_root": cert.certificate_root,
                "payload": payload,
            })
        }
        self._state[cert.resource] = state
        return state

    def generation(self, resource: str) -> int:
        return self._accepted_generation.get(resource, 0)

class PartitionedFenceCluster:
    """Deterministic crash-fault/partition model for the fixed-membership KEX mesh."""

    def __init__(self, nodes: Dict[str, DurableFenceNode], membership: Membership):
        self.nodes = nodes
        self.membership = membership
        self.links: Set[Tuple[str,str]] = set()
        for a in membership.members:
            for b in membership.members:
                if a != b:
                    self.links.add((a,b))

    def partition(self, groups: Iterable[Iterable[str]]):
        gs = [set(g) for g in groups]
        self.links.clear()
        for g in gs:
            for a in g:
                for b in g:
                    if a != b:
                        self.links.add((a,b))

    def heal(self):
        self.links.clear()
        for a in self.membership.members:
            for b in self.membership.members:
                if a != b:
                    self.links.add((a,b))

    def reachable(self, proposer: str, voter: str) -> bool:
        return proposer == voter or (proposer, voter) in self.links

    def acquire(self, proposer: str, resource: str, previous_generation: int, nonce: Optional[str] = None) -> FenceCertificate:
        proposal = FenceProposal.create(
            resource=resource,
            generation=previous_generation + 1,
            previous_generation=previous_generation,
            owner=proposer,
            membership=self.membership,
            nonce=nonce,
        )
        votes = []
        for voter in self.membership.members:
            if self.reachable(proposer, voter):
                try:
                    votes.append(self.nodes[voter].vote(proposal))
                except RuntimeError:
                    pass
        cert = FenceCertificate.build(proposal, votes, self.membership)
        for node_id in self.membership.members:
            if self.reachable(proposer, node_id):
                self.nodes[node_id].commit_certificate(cert)
        return cert
