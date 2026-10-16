#!/usr/bin/env python3
"""Topology-native execution/evidence controller.

This controller does not impose funding, procurement, vendor or strategic gates.
It only answers a technical question:

    What is this logical object, what implementation/carrier represents it,
    what has actually been observed, and what claim level is justified?

Development remains possible at every state. Promotion of a CLAIM is evidence-bound.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


EVIDENCE_LEVELS = (
    "DECLARED",
    "RESOLVED",
    "IMPLEMENTED",
    "EXECUTED",
    "READBACK_VERIFIED",
    "EXTERNALLY_PROVEN",
)


@dataclass
class Carrier:
    carrier_id: str
    logical_identity: str
    kind: str
    source_ref: str
    bytes: int | None = None
    sha256: str | None = None
    roles: list[str] = field(default_factory=list)
    state: str = "PRESENT"


@dataclass
class Evidence:
    evidence_id: str
    logical_identity: str
    evidence_type: str
    level: str
    observed: bool
    source: str
    details: dict[str, Any]
    created_at: float = field(default_factory=time.time)


@dataclass
class Claim:
    claim_id: str
    logical_identity: str
    claimed_level: str
    supported_level: str
    status: str
    evidence_ids: list[str]
    created_at: float = field(default_factory=time.time)


class TopologyController:
    def __init__(self, registry_path: Path):
        self.registry_path = Path(registry_path)
        self.registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        self.objects = self.registry["logical_objects"]
        self.carriers: dict[str, Carrier] = {}
        self.evidence: dict[str, Evidence] = {}
        self.claims: dict[str, Claim] = {}

    def resolve_identity(self, logical_identity: str) -> dict[str, Any]:
        if logical_identity not in self.objects:
            raise KeyError(f"UNRESOLVED_LOGICAL_IDENTITY:{logical_identity}")
        return {
            "logical_identity": logical_identity,
            "surface_class": self.objects[logical_identity]["surface_class"],
        }

    def register_carrier(
        self,
        logical_identity: str,
        carrier_id: str,
        kind: str,
        source_ref: str,
        *,
        bytes: int | None = None,
        sha256: str | None = None,
        roles: list[str] | None = None,
    ) -> Carrier:
        self.resolve_identity(logical_identity)
        if carrier_id in self.carriers:
            existing = self.carriers[carrier_id]
            if existing.logical_identity != logical_identity:
                raise ValueError(
                    f"CARRIER_ID_REBOUND:{carrier_id}:"
                    f"{existing.logical_identity}->{logical_identity}"
                )
            return existing

        carrier = Carrier(
            carrier_id=carrier_id,
            logical_identity=logical_identity,
            kind=kind,
            source_ref=source_ref,
            bytes=bytes,
            sha256=sha256,
            roles=list(roles or []),
        )
        self.carriers[carrier_id] = carrier
        return carrier

    def record_evidence(
        self,
        logical_identity: str,
        evidence_type: str,
        level: str,
        source: str,
        *,
        observed: bool = True,
        details: dict[str, Any] | None = None,
    ) -> Evidence:
        self.resolve_identity(logical_identity)
        if level not in EVIDENCE_LEVELS:
            raise ValueError(f"UNKNOWN_EVIDENCE_LEVEL:{level}")
        if level in {"EXECUTED", "READBACK_VERIFIED", "EXTERNALLY_PROVEN"} and not observed:
            raise ValueError("EXECUTION_EVIDENCE_MUST_BE_OBSERVED")

        eid = f"evidence://{uuid.uuid4()}"
        ev = Evidence(
            evidence_id=eid,
            logical_identity=logical_identity,
            evidence_type=evidence_type,
            level=level,
            observed=observed,
            source=source,
            details=dict(details or {}),
        )
        self.evidence[eid] = ev
        return ev

    def supported_level(self, logical_identity: str) -> str:
        self.resolve_identity(logical_identity)
        order = {level: i for i, level in enumerate(EVIDENCE_LEVELS)}
        best = "DECLARED"
        for ev in self.evidence.values():
            if ev.logical_identity != logical_identity or not ev.observed:
                continue
            if order[ev.level] > order[best]:
                best = ev.level
        return best

    def make_claim(
        self,
        logical_identity: str,
        claimed_level: str,
        evidence_ids: list[str],
    ) -> Claim:
        self.resolve_identity(logical_identity)
        if claimed_level not in EVIDENCE_LEVELS:
            raise ValueError(f"UNKNOWN_CLAIM_LEVEL:{claimed_level}")

        selected = []
        for eid in evidence_ids:
            ev = self.evidence.get(eid)
            if ev is None:
                raise KeyError(f"UNKNOWN_EVIDENCE:{eid}")
            if ev.logical_identity != logical_identity:
                raise ValueError(f"EVIDENCE_IDENTITY_MISMATCH:{eid}")
            if not ev.observed:
                raise ValueError(f"UNOBSERVED_EVIDENCE:{eid}")
            selected.append(ev)

        supported = self.supported_level(logical_identity)
        order = {level: i for i, level in enumerate(EVIDENCE_LEVELS)}
        status = "SUPPORTED" if order[supported] >= order[claimed_level] else "UNSUPPORTED"

        claim = Claim(
            claim_id=f"claim://{uuid.uuid4()}",
            logical_identity=logical_identity,
            claimed_level=claimed_level,
            supported_level=supported,
            status=status,
            evidence_ids=list(evidence_ids),
        )
        self.claims[claim.claim_id] = claim
        return claim

    def readback(self, logical_identity: str) -> dict[str, Any]:
        self.resolve_identity(logical_identity)
        carriers = [
            asdict(c)
            for c in self.carriers.values()
            if c.logical_identity == logical_identity
        ]
        evidence = [
            asdict(e)
            for e in self.evidence.values()
            if e.logical_identity == logical_identity
        ]
        claims = [
            asdict(c)
            for c in self.claims.values()
            if c.logical_identity == logical_identity
        ]
        payload = {
            "schema": "keddeh.kex.topology.readback.v1",
            "logical_identity": logical_identity,
            "surface_class": self.objects[logical_identity]["surface_class"],
            "carriers": carriers,
            "evidence": evidence,
            "claims": claims,
            "supported_level": self.supported_level(logical_identity),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        payload["readback_sha256"] = hashlib.sha256(canonical).hexdigest()
        return payload

    def export_state(self) -> dict[str, Any]:
        return {
            "schema": "keddeh.kex.topology.state.v1",
            "registry_source": self.registry_path.as_posix(),
            "logical_object_count": len(self.objects),
            "carrier_count": len(self.carriers),
            "evidence_count": len(self.evidence),
            "claim_count": len(self.claims),
            "supported_levels": {
                identity: self.supported_level(identity)
                for identity in sorted(self.objects)
            },
        }


def load_default() -> TopologyController:
    return TopologyController(Path(__file__).with_name("kex_topology_registry.json"))


if __name__ == "__main__":
    controller = load_default()
    print(json.dumps(controller.export_state(), indent=2, sort_keys=True))
