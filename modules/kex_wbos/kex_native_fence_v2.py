from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Set, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def unb64(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


@dataclass(frozen=True)
class Member:
    node_id: str
    public_key_b64: str


@dataclass(frozen=True)
class Membership:
    epoch: int
    members: Tuple[Member, ...]
    root: str

    @classmethod
    def create(cls, epoch: int, members: Iterable[Member]) -> "Membership":
        ordered = tuple(sorted(members, key=lambda m: m.node_id))
        if len({m.node_id for m in ordered}) != len(ordered):
            raise ValueError("duplicate member")
        if len(ordered) < 3:
            raise ValueError("membership requires at least three nodes")
        body = {
            "epoch": int(epoch),
            "members": [{"node_id": m.node_id, "public_key_b64": m.public_key_b64} for m in ordered],
        }
        return cls(int(epoch), ordered, sha(body))

    @property
    def quorum(self) -> int:
        return len(self.members) // 2 + 1

    def public_key(self, node_id: str) -> Ed25519PublicKey:
        for m in self.members:
            if m.node_id == node_id:
                return Ed25519PublicKey.from_public_bytes(unb64(m.public_key_b64))
        raise KeyError(node_id)

    def contains(self, node_id: str) -> bool:
        return any(m.node_id == node_id for m in self.members)


@dataclass(frozen=True)
class NodeKey:
    node_id: str
    private: Ed25519PrivateKey

    @classmethod
    def generate(cls, node_id: str) -> "NodeKey":
        return cls(node_id, Ed25519PrivateKey.generate())

    def member(self) -> Member:
        raw = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return Member(self.node_id, b64(raw))


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
    owner_signature_b64: str

    @classmethod
    def create(cls, *, resource: str, generation: int, previous_generation: int,
               owner_key: NodeKey, membership: Membership, nonce: Optional[str] = None):
        if not membership.contains(owner_key.node_id):
            raise ValueError("owner not trusted")
        nonce = nonce or uuid.uuid4().hex
        core = {
            "schema": "kex.mesh.fence.proposal/v2",
            "resource": resource,
            "generation": int(generation),
            "previous_generation": int(previous_generation),
            "owner": owner_key.node_id,
            "nonce": nonce,
            "membership_epoch": membership.epoch,
            "membership_root": membership.root,
        }
        root = sha(core)
        sig = owner_key.private.sign(canonical({"proposal_root": root}))
        return cls(resource, int(generation), int(previous_generation), owner_key.node_id, nonce,
                   membership.epoch, membership.root, root, b64(sig))

    def verify(self, membership: Membership) -> None:
        if self.membership_epoch != membership.epoch or self.membership_root != membership.root:
            raise RuntimeError("PROPOSAL_MEMBERSHIP_MISMATCH")
        core = {
            "schema": "kex.mesh.fence.proposal/v2",
            "resource": self.resource,
            "generation": self.generation,
            "previous_generation": self.previous_generation,
            "owner": self.owner,
            "nonce": self.nonce,
            "membership_epoch": self.membership_epoch,
            "membership_root": self.membership_root,
        }
        if sha(core) != self.proposal_root:
            raise RuntimeError("PROPOSAL_ROOT_INVALID")
        membership.public_key(self.owner).verify(unb64(self.owner_signature_b64), canonical({"proposal_root": self.proposal_root}))


@dataclass(frozen=True)
class FenceVote:
    voter: str
    resource: str
    generation: int
    proposal_root: str
    membership_epoch: int
    membership_root: str
    vote_root: str
    signature_b64: str

    def verify(self, membership: Membership) -> None:
        core = {
            "schema": "kex.mesh.fence.vote/v2",
            "voter": self.voter,
            "resource": self.resource,
            "generation": self.generation,
            "proposal_root": self.proposal_root,
            "membership_epoch": self.membership_epoch,
            "membership_root": self.membership_root,
        }
        if sha(core) != self.vote_root:
            raise RuntimeError("VOTE_ROOT_INVALID")
        membership.public_key(self.voter).verify(unb64(self.signature_b64), canonical({"vote_root": self.vote_root}))


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
    owner_signature_b64: str
    votes: Tuple[FenceVote, ...]
    certificate_root: str

    @classmethod
    def build(cls, proposal: FenceProposal, votes: Iterable[FenceVote], membership: Membership):
        proposal.verify(membership)
        votes = tuple(sorted(votes, key=lambda v: v.voter))
        if len(votes) < membership.quorum:
            raise ValueError("insufficient quorum")
        if len({v.voter for v in votes}) != len(votes):
            raise ValueError("duplicate voters")
        for v in votes:
            v.verify(membership)
            if v.resource != proposal.resource or v.generation != proposal.generation or v.proposal_root != proposal.proposal_root:
                raise ValueError("vote mismatch")
            if v.membership_epoch != membership.epoch or v.membership_root != membership.root:
                raise ValueError("vote membership mismatch")
        core = {
            "schema": "kex.mesh.fence.certificate/v2",
            "resource": proposal.resource,
            "generation": proposal.generation,
            "previous_generation": proposal.previous_generation,
            "owner": proposal.owner,
            "nonce": proposal.nonce,
            "membership_epoch": proposal.membership_epoch,
            "membership_root": proposal.membership_root,
            "proposal_root": proposal.proposal_root,
            "owner_signature_b64": proposal.owner_signature_b64,
            "votes": [v.__dict__ for v in votes],
        }
        return cls(proposal.resource, proposal.generation, proposal.previous_generation, proposal.owner,
                   proposal.nonce, proposal.membership_epoch, proposal.membership_root, proposal.proposal_root,
                   proposal.owner_signature_b64, votes, sha(core))

    def verify(self, membership: Membership) -> None:
        if self.membership_epoch != membership.epoch or self.membership_root != membership.root:
            raise RuntimeError("STALE_MEMBERSHIP_CERTIFICATE")
        proposal = FenceProposal(self.resource, self.generation, self.previous_generation, self.owner, self.nonce,
                                 self.membership_epoch, self.membership_root, self.proposal_root, self.owner_signature_b64)
        proposal.verify(membership)
        if len(self.votes) < membership.quorum:
            raise RuntimeError("NO_QUORUM")
        if len({v.voter for v in self.votes}) != len(self.votes):
            raise RuntimeError("DUPLICATE_VOTER")
        for v in self.votes:
            v.verify(membership)
            if v.resource != self.resource or v.generation != self.generation or v.proposal_root != self.proposal_root:
                raise RuntimeError("CERTIFICATE_VOTE_MISMATCH")
        core = {
            "schema": "kex.mesh.fence.certificate/v2",
            "resource": self.resource,
            "generation": self.generation,
            "previous_generation": self.previous_generation,
            "owner": self.owner,
            "nonce": self.nonce,
            "membership_epoch": self.membership_epoch,
            "membership_root": self.membership_root,
            "proposal_root": self.proposal_root,
            "owner_signature_b64": self.owner_signature_b64,
            "votes": [v.__dict__ for v in self.votes],
        }
        if sha(core) != self.certificate_root:
            raise RuntimeError("CERTIFICATE_ROOT_INVALID")


class DurableFenceNode:
    def __init__(self, node_key: NodeKey, db_path: Path, membership: Membership):
        if not membership.contains(node_key.node_id):
            raise ValueError("node not in membership")
        self.node_key = node_key
        self.node_id = node_key.node_id
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.membership = membership
        self._bootstrap()

    @contextmanager
    def _connect(self):
        c = sqlite3.connect(self.db_path, timeout=5, isolation_level=None)
        try:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=FULL")
            c.execute("PRAGMA busy_timeout=5000")
            yield c
        finally:
            c.close()

    def _bootstrap(self):
        with self._connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS fence_votes(resource TEXT NOT NULL,generation INTEGER NOT NULL,proposal_root TEXT NOT NULL,vote_json TEXT NOT NULL,PRIMARY KEY(resource,generation));
            CREATE TABLE IF NOT EXISTS high_water(resource TEXT PRIMARY KEY,generation INTEGER NOT NULL,certificate_root TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS replay_high_water(origin TEXT PRIMARY KEY,counter INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS certificate_history(resource TEXT NOT NULL,generation INTEGER NOT NULL,certificate_root TEXT NOT NULL,certificate_json TEXT NOT NULL,PRIMARY KEY(resource,generation));
            """)

    def observe_counter(self, origin: str, counter: int) -> bool:
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT counter FROM replay_high_water WHERE origin=?", (origin,)).fetchone()
            prior = -1 if row is None else int(row[0])
            if counter <= prior:
                c.rollback(); return False
            c.execute("INSERT INTO replay_high_water(origin,counter) VALUES(?,?) ON CONFLICT(origin) DO UPDATE SET counter=excluded.counter", (origin, int(counter)))
            c.commit(); return True

    def vote(self, proposal: FenceProposal) -> FenceVote:
        proposal.verify(self.membership)
        core = {"schema":"kex.mesh.fence.vote/v2","voter":self.node_id,"resource":proposal.resource,
                "generation":proposal.generation,"proposal_root":proposal.proposal_root,
                "membership_epoch":proposal.membership_epoch,"membership_root":proposal.membership_root}
        vote_root = sha(core)
        vote = FenceVote(self.node_id, proposal.resource, proposal.generation, proposal.proposal_root,
                         proposal.membership_epoch, proposal.membership_root, vote_root,
                         b64(self.node_key.private.sign(canonical({"vote_root": vote_root}))))
        vote_json = json.dumps(vote.__dict__, sort_keys=True)
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT proposal_root,vote_json FROM fence_votes WHERE resource=? AND generation=?", (proposal.resource,proposal.generation)).fetchone()
            if row is not None:
                if row[0] != proposal.proposal_root:
                    c.rollback(); raise RuntimeError("CONFLICTING_VOTE_REJECTED")
                c.commit(); return FenceVote(**json.loads(row[1]))
            c.execute("INSERT INTO fence_votes(resource,generation,proposal_root,vote_json) VALUES(?,?,?,?)", (proposal.resource,proposal.generation,proposal.proposal_root,vote_json))
            c.commit()
        return vote

    def commit_certificate(self, cert: FenceCertificate):
        cert.verify(self.membership)
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT generation FROM high_water WHERE resource=?", (cert.resource,)).fetchone()
            prior = 0 if row is None else int(row[0])
            if cert.previous_generation != prior or cert.generation != prior + 1:
                c.rollback(); raise RuntimeError("NON_CONTIGUOUS_FENCE_COMMIT")
            cert_json=json.dumps({**{k:getattr(cert,k) for k in ("resource","generation","previous_generation","owner","nonce","membership_epoch","membership_root","proposal_root","owner_signature_b64","certificate_root")},"votes":[v.__dict__ for v in cert.votes]},sort_keys=True)
            c.execute("INSERT INTO high_water(resource,generation,certificate_root) VALUES(?,?,?) ON CONFLICT(resource) DO UPDATE SET generation=excluded.generation,certificate_root=excluded.certificate_root", (cert.resource,cert.generation,cert.certificate_root))
            c.execute("INSERT INTO certificate_history(resource,generation,certificate_root,certificate_json) VALUES(?,?,?,?)", (cert.resource,cert.generation,cert.certificate_root,cert_json))
            c.commit()


class ResourceFenceGate:
    def __init__(self):
        self._generation: Dict[str,int] = {}
        self._state: Dict[str,dict] = {}

    def mutate(self, cert: FenceCertificate, payload: dict, membership: Membership) -> dict:
        cert.verify(membership)
        prior=self._generation.get(cert.resource,0)
        if cert.generation <= prior: raise RuntimeError("STALE_FENCE_REJECTED")
        if cert.previous_generation != prior: raise RuntimeError("FENCE_GAP_REJECTED")
        state={"resource":cert.resource,"generation":cert.generation,"owner":cert.owner,"certificate_root":cert.certificate_root,"payload":payload}
        state["state_root"]=sha(state)
        self._generation[cert.resource]=cert.generation
        self._state[cert.resource]=state
        return state


class PartitionedFenceCluster:
    def __init__(self,nodes:Dict[str,DurableFenceNode],keys:Dict[str,NodeKey],membership:Membership):
        self.nodes=nodes; self.keys=keys; self.membership=membership; self.links:Set[Tuple[str,str]]=set(); self.heal()
    def partition(self,groups:Iterable[Iterable[str]]):
        self.links.clear()
        for group in map(set,groups):
            for a in group:
                for b in group:
                    if a!=b:self.links.add((a,b))
    def heal(self):
        self.links.clear(); ids=[m.node_id for m in self.membership.members]
        for a in ids:
            for b in ids:
                if a!=b:self.links.add((a,b))
    def reachable(self,a:str,b:str)->bool:return a==b or (a,b) in self.links
    def acquire(self,proposer:str,resource:str,previous_generation:int,nonce:Optional[str]=None)->FenceCertificate:
        proposal=FenceProposal.create(resource=resource,generation=previous_generation+1,previous_generation=previous_generation,owner_key=self.keys[proposer],membership=self.membership,nonce=nonce)
        votes=[]
        for m in self.membership.members:
            if self.reachable(proposer,m.node_id):
                try:votes.append(self.nodes[m.node_id].vote(proposal))
                except RuntimeError:pass
        cert=FenceCertificate.build(proposal,votes,self.membership)
        for m in self.membership.members:
            if self.reachable(proposer,m.node_id):self.nodes[m.node_id].commit_certificate(cert)
        return cert
