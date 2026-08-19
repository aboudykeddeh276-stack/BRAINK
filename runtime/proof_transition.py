"""BRAINK proof-bearing state transition contract.

This module does not decide whether a subsystem is successful.  It constrains
how evidence is allowed to change system state so that blocked execution,
stale evidence, and unchanged-precondition retries cannot silently become
stronger claims.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional


class EvidenceClass(str, Enum):
    OBSERVED = "OBSERVED"
    SOURCE_VERIFIED = "SOURCE_VERIFIED"
    TESTED = "TESTED"
    INFERRED = "INFERRED"
    UNTESTED = "UNTESTED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    UNOBSERVED = "UNOBSERVED"
    SUPERSEDED = "SUPERSEDED"


class TransitionDecision(str, Enum):
    RETRY_ALLOWED = "RETRY_ALLOWED"
    NO_RETRY_UNCHANGED_PRECONDITION = "NO_RETRY_UNCHANGED_PRECONDITION"


@dataclass(frozen=True)
class Transition:
    operation_id: str
    subject: str
    subject_revision: str
    evidence_revision: str
    evidence_class: EvidenceClass
    prior_state: str
    resulting_state: str
    failure_scope: Optional[str] = None


@dataclass(frozen=True)
class Qualification:
    accepted: bool
    reason: str
    preserved_prior_state: str


def decide_retry(
    *,
    operation_fingerprint: str,
    previous_failure: str,
    previous_prerequisites: Mapping[str, str],
    current_prerequisites: Mapping[str, str],
) -> TransitionDecision:
    """Permit retry only when at least one prerequisite changed.

    The operation/failure arguments are intentionally explicit even though v1
    needs only prerequisite equality.  They make each decision traceable to a
    concrete attempted operation rather than a generic retry loop.
    """
    if not operation_fingerprint or not previous_failure:
        raise ValueError("operation_fingerprint and previous_failure are required")
    if dict(previous_prerequisites) == dict(current_prerequisites):
        return TransitionDecision.NO_RETRY_UNCHANGED_PRECONDITION
    return TransitionDecision.RETRY_ALLOWED


def qualify_transition(transition: Transition) -> Qualification:
    """Validate whether evidence may produce the requested state transition."""
    if not transition.operation_id or not transition.subject:
        return Qualification(False, "MISSING_OPERATION_OR_SUBJECT", transition.prior_state)

    if transition.subject_revision != transition.evidence_revision:
        return Qualification(
            False,
            "SUBJECT_EVIDENCE_REVISION_MISMATCH",
            transition.prior_state,
        )

    if (
        transition.evidence_class is EvidenceClass.BLOCKED
        and transition.failure_scope == "CARRIER_BEFORE_EXECUTION"
        and transition.resulting_state == "FAILED"
    ):
        return Qualification(
            False,
            "CARRIER_BLOCK_CANNOT_CLASSIFY_SOURCE_FAILED",
            transition.prior_state,
        )

    # A downstream block is evidence about the attempted transition, not a
    # revocation of an already-qualified upstream state.
    if transition.evidence_class is EvidenceClass.BLOCKED:
        return Qualification(True, "BLOCK_RECORDED_PRIOR_STATE_PRESERVED", transition.prior_state)

    return Qualification(True, "TRANSITION_EVIDENCE_BOUND", transition.prior_state)
