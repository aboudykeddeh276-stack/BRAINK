from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


class EpicViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    subject: str
    predicate: str
    value: Any
    source: str
    receipt: str | None = None
    executor: str | None = None
    router: str | None = None
    validator: str | None = None
    originator: str | None = None
    lineage_parent: str | None = None
    observed: bool = True


@dataclass(frozen=True)
class Claim:
    claim_id: str
    subject: str
    predicate: str
    expected: Any
    required_evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    requires_observation: bool = True
    requires_receipt: bool = False
    asserted_executor: str | None = None


@dataclass(frozen=True)
class ClaimDecision:
    claim_id: str
    status: str
    reasons: tuple[str, ...]
    matched_evidence_ids: tuple[str, ...]


class EpicGate:
    """EPIC evidence/claim gate.

    EPIC maps facts, evaluates invariants, and qualifies claims. It does not
    mutate runtime state, choose executors, assign authority, or infer execution
    from lineage/routing/provisioning relationships.
    """

    QUALIFIED = "QUALIFIED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    UNOBSERVED = "UNOBSERVED"

    def __init__(self, evidence: Iterable[EvidenceRef] = ()) -> None:
        self._evidence = {item.evidence_id: item for item in evidence}

    def add_evidence(self, item: EvidenceRef) -> None:
        if not item.evidence_id:
            raise EpicViolation("EVIDENCE_ID_REQUIRED")
        self._evidence[item.evidence_id] = item

    def decide(self, claim: Claim) -> ClaimDecision:
        selected = []
        reasons: list[str] = []

        if claim.required_evidence_ids:
            missing = [eid for eid in claim.required_evidence_ids if eid not in self._evidence]
            if missing:
                return ClaimDecision(
                    claim.claim_id,
                    self.UNOBSERVED,
                    tuple(f"MISSING_EVIDENCE:{eid}" for eid in missing),
                    tuple(),
                )
            selected = [self._evidence[eid] for eid in claim.required_evidence_ids]
        else:
            selected = [
                item for item in self._evidence.values()
                if item.subject == claim.subject and item.predicate == claim.predicate
            ]

        if not selected:
            return ClaimDecision(claim.claim_id, self.UNOBSERVED, ("NO_SUPPORTING_EVIDENCE",), tuple())

        if claim.requires_observation:
            unobserved = [item.evidence_id for item in selected if not item.observed]
            if unobserved:
                return ClaimDecision(
                    claim.claim_id,
                    self.UNOBSERVED,
                    tuple(f"UNOBSERVED:{eid}" for eid in unobserved),
                    tuple(item.evidence_id for item in selected),
                )

        matching = [item for item in selected if item.value == claim.expected]
        if not matching:
            return ClaimDecision(
                claim.claim_id,
                self.REJECTED,
                ("EVIDENCE_VALUE_MISMATCH",),
                tuple(item.evidence_id for item in selected),
            )

        if claim.requires_receipt:
            no_receipt = [item.evidence_id for item in matching if not item.receipt]
            if no_receipt:
                return ClaimDecision(
                    claim.claim_id,
                    self.PARTIAL,
                    tuple(f"RECEIPT_REQUIRED:{eid}" for eid in no_receipt),
                    tuple(item.evidence_id for item in matching),
                )

        if claim.asserted_executor is not None:
            executor_mismatch = [
                item.evidence_id for item in matching
                if item.executor != claim.asserted_executor
            ]
            if executor_mismatch:
                return ClaimDecision(
                    claim.claim_id,
                    self.REJECTED,
                    tuple(f"EXECUTOR_MISMATCH:{eid}" for eid in executor_mismatch),
                    tuple(item.evidence_id for item in matching),
                )

        # A parent/router/originator/validator relationship never substitutes for
        # executor evidence. If the claim names an executor, only executor does.
        return ClaimDecision(
            claim.claim_id,
            self.QUALIFIED,
            tuple(reasons),
            tuple(item.evidence_id for item in matching),
        )


def assert_epic_non_mutating() -> dict[str, bool]:
    """Machine-readable EPIC authority boundary."""
    return {
        "runtime_mutation": False,
        "authority_assignment": False,
        "executor_selection": False,
        "state_promotion": False,
        "evidence_mapping": True,
        "invariant_evaluation": True,
        "claim_gating": True,
        "provenance_mapping": True,
    }
