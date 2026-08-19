"""BRAINK Proof-Bearing Transition Contract v20.

State may advance only when evidence is bound to the exact subject revision,
attempt, environment, operation, provenance and legal transition. Retry is a
new transition, never a generic recovery loop.
"""
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import FrozenSet, Mapping, Optional, Tuple


class EvidenceClass(IntEnum):
    UNOBSERVED = 0
    INFERRED = 10
    UNTESTED = 20
    OBSERVED = 30
    SOURCE_VERIFIED = 40
    TESTED = 50
    BLOCKED = 60
    FAILED = 70
    SUPERSEDED = 80


class TransitionDecision(str, Enum):
    RETRY_ALLOWED = "RETRY_ALLOWED"
    NO_RETRY_UNCHANGED_PRECONDITION = "NO_RETRY_UNCHANGED_PRECONDITION"
    NO_RETRY_IRRELEVANT_DELTA = "NO_RETRY_IRRELEVANT_DELTA"
    NO_RETRY_OPERATION_MISMATCH = "NO_RETRY_OPERATION_MISMATCH"
    NO_RETRY_FAILURE_MISMATCH = "NO_RETRY_FAILURE_MISMATCH"
    NO_RETRY_BUDGET_EXHAUSTED = "NO_RETRY_BUDGET_EXHAUSTED"


LEGAL_TRANSITIONS = {
    "UNOBSERVED": frozenset({"CANDIDATE", "BLOCKED"}),
    "CANDIDATE": frozenset({"TESTED", "BLOCKED", "FAILED", "SUPERSEDED"}),
    "TESTED": frozenset({"QUALIFIED", "BLOCKED", "FAILED", "SUPERSEDED"}),
    "QUALIFIED": frozenset({"BLOCKED", "SUPERSEDED"}),
    "BITCOIN_CORE_QUALIFIED": frozenset({"BLOCKED", "TEMPLATE_ACQUIRED", "SUPERSEDED"}),
    "TEMPLATE_ACQUIRED": frozenset({"MINING_ACTIVE", "BLOCKED", "FAILED", "SUPERSEDED"}),
    "MINING_ACTIVE": frozenset({"CANDIDATE_FOUND", "BLOCKED", "FAILED", "SUPERSEDED"}),
    "CANDIDATE_FOUND": frozenset({"SUBMISSION_ACCEPTED", "SUBMISSION_REJECTED", "BLOCKED"}),
}


@dataclass(frozen=True)
class EvidenceProvenance:
    producer: str
    method: str
    reference: str
    scope: str


@dataclass(frozen=True)
class Transition:
    operation_id: str
    operation_fingerprint: str
    subject: str
    subject_revision: str
    evidence_revision: str
    environment_id: str
    evidence_class: EvidenceClass
    prior_state: str
    resulting_state: str
    provenance: EvidenceProvenance
    attempt_id: str
    evidence_attempt_id: str
    attempt_sequence: int
    evidence_sequence: int
    failure_scope: Optional[str] = None


@dataclass(frozen=True)
class Qualification:
    accepted: bool
    reason: str
    preserved_prior_state: str


@dataclass(frozen=True)
class RetryContext:
    operation_fingerprint: str
    failure_fingerprint: str
    prerequisites: Mapping[str, str]
    relevant_prerequisites: FrozenSet[str] = field(default_factory=frozenset)
    retry_count: int = 0
    retry_budget: int = 1


def decide_retry(previous: RetryContext, current: RetryContext) -> TransitionDecision:
    if previous.operation_fingerprint != current.operation_fingerprint:
        return TransitionDecision.NO_RETRY_OPERATION_MISMATCH
    if previous.failure_fingerprint != current.failure_fingerprint:
        return TransitionDecision.NO_RETRY_FAILURE_MISMATCH
    if previous.retry_count >= previous.retry_budget:
        return TransitionDecision.NO_RETRY_BUDGET_EXHAUSTED
    changed = {k for k in set(previous.prerequisites) | set(current.prerequisites)
               if previous.prerequisites.get(k) != current.prerequisites.get(k)}
    if not changed:
        return TransitionDecision.NO_RETRY_UNCHANGED_PRECONDITION
    relevant_changed = changed & previous.relevant_prerequisites & current.relevant_prerequisites
    if not relevant_changed:
        return TransitionDecision.NO_RETRY_IRRELEVANT_DELTA
    return TransitionDecision.RETRY_ALLOWED


def qualify_transition(t: Transition) -> Qualification:
    preserve = t.prior_state
    required = (t.operation_id, t.operation_fingerprint, t.subject, t.subject_revision,
                t.evidence_revision, t.environment_id, t.attempt_id,
                t.evidence_attempt_id, t.provenance.producer, t.provenance.method,
                t.provenance.reference, t.provenance.scope)
    if any(not value for value in required):
        return Qualification(False, "INCOMPLETE_PROVENANCE_ENVELOPE", preserve)
    if t.subject_revision != t.evidence_revision:
        return Qualification(False, "SUBJECT_EVIDENCE_REVISION_MISMATCH", preserve)
    if t.attempt_id != t.evidence_attempt_id:
        return Qualification(False, "EVIDENCE_ATTEMPT_REPLAY_OR_MISBIND", preserve)
    if t.evidence_sequence < t.attempt_sequence:
        return Qualification(False, "EVIDENCE_PRECEDES_ATTEMPT", preserve)
    legal = LEGAL_TRANSITIONS.get(t.prior_state)
    if legal is not None and t.resulting_state not in legal:
        return Qualification(False, "ILLEGAL_STATE_TRANSITION", preserve)
    if (t.evidence_class is EvidenceClass.BLOCKED
            and t.failure_scope == "CARRIER_BEFORE_EXECUTION"
            and t.resulting_state == "FAILED"):
        return Qualification(False, "CARRIER_BLOCK_CANNOT_CLASSIFY_SOURCE_FAILED", preserve)
    if t.evidence_class is EvidenceClass.BLOCKED:
        return Qualification(True, "BLOCK_RECORDED_PRIOR_STATE_PRESERVED", preserve)
    return Qualification(True, "TRANSITION_EVIDENCE_BOUND", preserve)


def audit_key(t: Transition) -> Tuple[str, str, str, str, str]:
    """Stable reconstruction key for cross-surface ledgers."""
    return (t.subject, t.subject_revision, t.environment_id, t.operation_id, t.attempt_id)
