#!/usr/bin/env python3
"""KEDDEH Triad-of-Triads accepted-state safety kernel.

This is a deterministic crash/partition-fault reference kernel for the fixed
3 x 3 virtual ToT topology. It does NOT claim Byzantine fault tolerance or
independent multi-site validation.

Safety model:
- nine stable virtual voter coordinates, grouped as 3 triads of 3;
- local quorum = any 2 of 3 voters in a triad;
- global quorum certificate = local quorum in any 2 of 3 triads;
- every committed transition extends the current committed root at index+1;
- a virtual voter can approve at most one value for a given (term,index);
- stale terms are fenced;
- commit certificates are deterministic and hash-bound.

Quorum-intersection consequence:
Any two global certificates contain >=2 triads, therefore share >=1 triad.
Any two 2-of-3 local quorums in that shared triad intersect in >=1 voter.
Thus two valid commit certificates necessarily share at least one virtual
voter. With vote-once-per-(term,index) and append-only committed indexing,
conflicting values cannot both commit at the same index in this model.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable
import hashlib
import json
import os

SCHEMA = "keddeh.tot-safety-kernel.v1"
KERNEL_ID = "KEX://SAFETY/TOT/DOMAIN-FABRIC/V1"
GROUPS = ("TRIAD_ALPHA", "TRIAD_BETA", "TRIAD_GAMMA")
LOOPS = ("A", "B", "C")
VOTERS = tuple(f"{g}:{l}" for g in GROUPS for l in LOOPS)
GENESIS_ROOT = "0" * 64


def canonical(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def h(v: Any) -> str:
    if isinstance(v, bytes):
        b = v
    elif isinstance(v, str):
        b = v.encode("utf-8")
    else:
        b = canonical(v).encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def voter_group(voter: str) -> str:
    if voter not in VOTERS:
        raise ValueError("UNKNOWN_TOT_VOTER")
    return voter.split(":", 1)[0]


def quorum_shape(voters: Iterable[str]) -> dict[str, list[str]]:
    by_group = {g: [] for g in GROUPS}
    for voter in sorted(set(voters)):
        by_group[voter_group(voter)].append(voter)
    return by_group


def is_local_quorum(voters: Iterable[str], group: str) -> bool:
    return len(quorum_shape(voters).get(group, [])) >= 2


def is_global_quorum(voters: Iterable[str]) -> bool:
    shape = quorum_shape(voters)
    return sum(1 for g in GROUPS if len(shape[g]) >= 2) >= 2


def quorum_intersection_minimum() -> dict[str, int]:
    # For 2/3 groups and 2/3 voters within each selected group.
    return {"shared_groups": 1, "shared_voters": 1, "minimum_approvals_per_certificate": 4}


@dataclass(frozen=True)
class Proposal:
    schema: str
    kernel_id: str
    term: int
    index: int
    leader: str
    previous_root: str
    operation: str
    payload: dict[str, Any]
    payload_root: str
    proposal_root: str

    @staticmethod
    def create(*, term: int, index: int, leader: str, previous_root: str, operation: str, payload: dict[str, Any]) -> "Proposal":
        if term < 1:
            raise ValueError("TERM_MUST_BE_POSITIVE")
        if index < 1:
            raise ValueError("INDEX_MUST_BE_POSITIVE")
        if leader not in VOTERS:
            raise ValueError("UNKNOWN_TOT_LEADER")
        payload_root = h(payload)
        body = {
            "schema": "keddeh.tot-proposal.v1",
            "kernel_id": KERNEL_ID,
            "term": term,
            "index": index,
            "leader": leader,
            "previous_root": previous_root,
            "operation": operation,
            "payload_root": payload_root,
        }
        return Proposal(
            schema=body["schema"], kernel_id=KERNEL_ID, term=term, index=index, leader=leader,
            previous_root=previous_root, operation=operation, payload=payload,
            payload_root=payload_root, proposal_root=h(body),
        )


class SafetyViolation(RuntimeError):
    pass


class ToTSafetyKernel:
    def __init__(self, state_path: str | Path | None = None):
        self.state_path = Path(state_path) if state_path else None
        self.term = 0
        self.leader: str | None = None
        self.commit_index = 0
        self.committed_root = GENESIS_ROOT
        self.log: list[dict[str, Any]] = []
        self.voter_terms = {v: 0 for v in VOTERS}
        self.votes: dict[str, str] = {}  # "term:index:voter" -> proposal_root
        self.leader_votes: dict[str, str] = {}  # "term:voter" -> candidate
        if self.state_path and self.state_path.exists():
            self._load()

    def snapshot(self) -> dict[str, Any]:
        body = {
            "schema": SCHEMA,
            "kernel_id": KERNEL_ID,
            "fault_model": "CRASH_PARTITION_REFERENCE_MODEL_NOT_BYZANTINE",
            "topology": {"groups": list(GROUPS), "loops": list(LOOPS), "voters": list(VOTERS)},
            "quorum": {
                "local": "2_OF_3_WITHIN_TRIAD",
                "global": "2_OF_3_TRIADS_EACH_WITH_LOCAL_QUORUM",
                "intersection": quorum_intersection_minimum(),
            },
            "term": self.term,
            "leader": self.leader,
            "commit_index": self.commit_index,
            "committed_root": self.committed_root,
            "log": self.log,
            "voter_terms": self.voter_terms,
            "votes": self.votes,
            "leader_votes": self.leader_votes,
        }
        body["state_root"] = h(body)
        return body

    def _persist(self) -> None:
        if not self.state_path:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.snapshot(), indent=2, sort_keys=True) + "\n")
        os.replace(tmp, self.state_path)

    def _load(self) -> None:
        data = json.loads(self.state_path.read_text())
        expected = data.pop("state_root", None)
        if expected != h(data):
            raise SafetyViolation("KERNEL_STATE_ROOT_MISMATCH")
        self.term = int(data["term"])
        self.leader = data["leader"]
        self.commit_index = int(data["commit_index"])
        self.committed_root = data["committed_root"]
        self.log = list(data["log"])
        self.voter_terms = dict(data["voter_terms"])
        self.votes = dict(data["votes"])
        self.leader_votes = dict(data["leader_votes"])
        self.verify_log()

    def observe_term(self, voter: str, term: int) -> None:
        if voter not in VOTERS:
            raise ValueError("UNKNOWN_TOT_VOTER")
        if term < self.voter_terms[voter]:
            raise SafetyViolation("TERM_REGRESSION_FORBIDDEN")
        self.voter_terms[voter] = term
        if term > self.term:
            self.term = term
            self.leader = None
        self._persist()

    def elect(self, *, term: int, candidate: str, voters: Iterable[str]) -> dict[str, Any]:
        voters = tuple(sorted(set(voters)))
        if candidate not in VOTERS:
            raise ValueError("UNKNOWN_TOT_CANDIDATE")
        if term <= self.term:
            raise SafetyViolation("ELECTION_TERM_NOT_MONOTONIC")
        if not is_global_quorum(voters):
            raise SafetyViolation("GLOBAL_ELECTION_QUORUM_REQUIRED")
        for voter in voters:
            prior = self.leader_votes.get(f"{term}:{voter}")
            if prior and prior != candidate:
                raise SafetyViolation("VOTER_ALREADY_VOTED_DIFFERENT_CANDIDATE")
        for voter in voters:
            self.leader_votes[f"{term}:{voter}"] = candidate
            self.voter_terms[voter] = max(self.voter_terms[voter], term)
        self.term = term
        self.leader = candidate
        self._persist()
        return {
            "state": "LEADER_ELECTED",
            "term": term,
            "leader": candidate,
            "certificate": self._certificate("ELECTION", term, 0, candidate, voters),
        }

    def propose(self, operation: str, payload: dict[str, Any]) -> Proposal:
        if self.term < 1 or not self.leader:
            raise SafetyViolation("LEADER_REQUIRED")
        return Proposal.create(
            term=self.term, index=self.commit_index + 1, leader=self.leader,
            previous_root=self.committed_root, operation=operation, payload=payload,
        )

    def approve(self, proposal: Proposal, voter: str) -> dict[str, Any]:
        if voter not in VOTERS:
            raise ValueError("UNKNOWN_TOT_VOTER")
        if proposal.term != self.term or proposal.term < self.voter_terms[voter]:
            raise SafetyViolation("STALE_PROPOSAL_TERM")
        if proposal.leader != self.leader:
            raise SafetyViolation("PROPOSAL_LEADER_NOT_CURRENT")
        if proposal.index != self.commit_index + 1:
            raise SafetyViolation("PROPOSAL_INDEX_NOT_NEXT")
        if proposal.previous_root != self.committed_root:
            raise SafetyViolation("PROPOSAL_DOES_NOT_EXTEND_COMMITTED_ROOT")
        key = f"{proposal.term}:{proposal.index}:{voter}"
        prior = self.votes.get(key)
        if prior and prior != proposal.proposal_root:
            raise SafetyViolation("VOTER_CONFLICTING_VALUE_SAME_TERM_INDEX")
        self.votes[key] = proposal.proposal_root
        self.voter_terms[voter] = max(self.voter_terms[voter], proposal.term)
        self._persist()
        return {"state": "APPROVED", "voter": voter, "proposal_root": proposal.proposal_root}

    def commit(self, proposal: Proposal, voters: Iterable[str]) -> dict[str, Any]:
        voters = tuple(sorted(set(voters)))
        if proposal.term != self.term or proposal.leader != self.leader:
            raise SafetyViolation("CURRENT_AUTHORITY_REQUIRED_FOR_COMMIT")
        if proposal.index != self.commit_index + 1 or proposal.previous_root != self.committed_root:
            raise SafetyViolation("COMMIT_MUST_APPEND_CURRENT_ROOT")
        if not is_global_quorum(voters):
            raise SafetyViolation("GLOBAL_COMMIT_QUORUM_REQUIRED")
        missing = [v for v in voters if self.votes.get(f"{proposal.term}:{proposal.index}:{v}") != proposal.proposal_root]
        if missing:
            raise SafetyViolation("COMMIT_CERTIFICATE_CONTAINS_UNAPPROVED_VOTER")
        cert = self._certificate("COMMIT", proposal.term, proposal.index, proposal.proposal_root, voters)
        entry_body = {
            "term": proposal.term,
            "index": proposal.index,
            "leader": proposal.leader,
            "previous_root": proposal.previous_root,
            "operation": proposal.operation,
            "payload": proposal.payload,
            "payload_root": proposal.payload_root,
            "proposal_root": proposal.proposal_root,
            "certificate": cert,
        }
        entry_body["entry_root"] = h(entry_body)
        self.log.append(entry_body)
        self.commit_index = proposal.index
        self.committed_root = entry_body["entry_root"]
        self._persist()
        return {"state": "COMMITTED", "commit_index": self.commit_index, "committed_root": self.committed_root, "certificate": cert}

    def transition(self, operation: str, payload: dict[str, Any], voters: Iterable[str]) -> dict[str, Any]:
        p = self.propose(operation, payload)
        voters = tuple(sorted(set(voters)))
        for voter in voters:
            self.approve(p, voter)
        out = self.commit(p, voters)
        out["proposal"] = asdict(p)
        return out

    def _certificate(self, kind: str, term: int, index: int, subject: str, voters: Iterable[str]) -> dict[str, Any]:
        voters = tuple(sorted(set(voters)))
        shape = quorum_shape(voters)
        body = {
            "schema": "keddeh.tot-quorum-certificate.v1",
            "kind": kind,
            "kernel_id": KERNEL_ID,
            "term": term,
            "index": index,
            "subject": subject,
            "voters": list(voters),
            "groups": shape,
            "global_quorum": is_global_quorum(voters),
        }
        body["certificate_root"] = h(body)
        return body

    def verify_log(self) -> dict[str, Any]:
        prev = GENESIS_ROOT
        expected_index = 1
        for entry in self.log:
            if entry["index"] != expected_index:
                raise SafetyViolation("LOG_INDEX_DISCONTINUITY")
            if entry["previous_root"] != prev:
                raise SafetyViolation("LOG_PREVIOUS_ROOT_MISMATCH")
            cert = entry["certificate"]
            if not cert.get("global_quorum") or not is_global_quorum(cert.get("voters", [])):
                raise SafetyViolation("LOG_COMMIT_CERTIFICATE_INVALID")
            body = dict(entry)
            root = body.pop("entry_root")
            if root != h(body):
                raise SafetyViolation("LOG_ENTRY_ROOT_MISMATCH")
            prev = root
            expected_index += 1
        if self.log:
            if self.committed_root != prev or self.commit_index != len(self.log):
                raise SafetyViolation("KERNEL_COMMIT_HEAD_MISMATCH")
        elif self.committed_root != GENESIS_ROOT or self.commit_index != 0:
            raise SafetyViolation("GENESIS_HEAD_MISMATCH")
        return {"state": "LOG_VERIFIED", "entries": len(self.log), "committed_root": self.committed_root}


DEFAULT_QUORUM = ("TRIAD_ALPHA:A", "TRIAD_ALPHA:B", "TRIAD_BETA:A", "TRIAD_BETA:B")