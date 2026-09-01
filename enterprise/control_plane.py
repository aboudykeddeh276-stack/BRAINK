from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

PROOF_ORDER = [
    "DESIGNED","ENCODED","LOCALLY_EXECUTED","MUTATING","PERSISTED",
    "HOST_INTEGRATED","DEPLOYED","PUBLICLY_PROJECTED","EXTERNALLY_READ_BACK"
]

@dataclass(frozen=True)
class Evidence:
    kind: str
    scope: str
    evidence_id: str
    verified: bool = True

@dataclass(frozen=True)
class Obligation:
    id: str
    executable: bool
    dependency_ready: bool
    evidence_gap: float
    risk: float
    information_gain: float
    unlock_value: float
    effort: float

def select(obligations: Iterable[Obligation]):
    frontier=[o for o in obligations if o.executable and o.dependency_ready]
    if not frontier:
        return None
    def score(o):
        return (
            0.24*o.evidence_gap + 0.22*o.risk + 0.24*o.information_gain +
            0.20*o.unlock_value - 0.18*o.effort
        )
    return max(frontier, key=lambda o:(score(o), o.id))

def can_promote(current: str, target: str, evidence: Evidence, scope: str):
    if current not in PROOF_ORDER or target not in PROOF_ORDER:
        return False, "UNKNOWN_STATE"
    if PROOF_ORDER.index(target) != PROOF_ORDER.index(current)+1:
        return False, "SKIPPED_PROOF_LAYER"
    if evidence.scope != scope:
        return False, "CROSS_SCOPE_EVIDENCE"
    if not evidence.verified or not evidence.evidence_id:
        return False, "UNVERIFIED_EVIDENCE"
    return True, "PROMOTABLE"
