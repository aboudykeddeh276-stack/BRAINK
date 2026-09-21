from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Dict, List

from theorem_graph import GraphValidationError, MasterTheoremGraphRegistry


class ProofStateTransitionError(GraphValidationError):
    """Raised when a proof-state transition lacks required evidence or receipt data."""


@dataclass(frozen=True)
class ProofEvent:
    event_type: str
    receipt_id: str
    evidence_hash: str = ""
    reason: str = ""


@dataclass(frozen=True)
class ProofState:
    theorem_id: str
    status: str = "UNVERIFIED"
    history: tuple[ProofEvent, ...] = field(default_factory=tuple)


class RuntimeProofPropagationEngine:
    """Propagates proof and falsification state through theorem dependencies."""

    CONTINUABLE_STATES = frozenset({"PROVEN"})

    def __init__(self, registry: MasterTheoremGraphRegistry) -> None:
        if not isinstance(registry, MasterTheoremGraphRegistry):
            raise GraphValidationError("registry must be a MasterTheoremGraphRegistry")
        self._registry = registry
        self._states: Dict[str, ProofState] = {}

    def state(self, theorem_id: str) -> ProofState:
        self._registry.get(theorem_id)
        return self._states.get(theorem_id, ProofState(theorem_id=theorem_id))

    def can_continue(self, theorem_id: str) -> bool:
        return self.state(theorem_id).status in self.CONTINUABLE_STATES

    def mark_proven(self, theorem_id: str, receipt_id: str, evidence_hash: str) -> ProofState:
        self._registry.get(theorem_id)
        receipt_id = self._require_nonempty("receipt_id", receipt_id)
        evidence_hash = self._require_nonempty("evidence_hash", evidence_hash)

        current = self.state(theorem_id)
        if current.status == "FALSIFIED":
            raise ProofStateTransitionError(
                f"Cannot mark falsified theorem {theorem_id} PROVEN without a separate recovery transition"
            )

        event = ProofEvent(
            event_type="PROVEN",
            receipt_id=receipt_id,
            evidence_hash=evidence_hash,
        )
        next_state = ProofState(
            theorem_id=theorem_id,
            status="PROVEN",
            history=current.history + (event,),
        )
        self._states[theorem_id] = next_state
        return next_state

    def invalidate(self, theorem_id: str, reason: str, receipt_id: str) -> dict:
        self._registry.get(theorem_id)
        reason = self._require_nonempty("reason", reason)
        receipt_id = self._require_nonempty("receipt_id", receipt_id)

        target_current = self.state(theorem_id)
        target_event = ProofEvent(
            event_type="FALSIFIED",
            receipt_id=receipt_id,
            reason=reason,
        )
        self._states[theorem_id] = ProofState(
            theorem_id=theorem_id,
            status="FALSIFIED",
            history=target_current.history + (target_event,),
        )

        affected: List[str] = []
        queue = list(self._registry.children_of(theorem_id))
        seen = set()

        while queue:
            child_id = queue.pop(0)
            if child_id in seen:
                continue
            seen.add(child_id)

            current = self.state(child_id)
            if current.status != "FALSIFIED":
                review_event = ProofEvent(
                    event_type="DOWNSTREAM_REVIEW_REQUIRED",
                    receipt_id=receipt_id,
                    reason=f"upstream:{theorem_id}:{reason}",
                )
                self._states[child_id] = ProofState(
                    theorem_id=child_id,
                    status="DOWNSTREAM_REVIEW_REQUIRED",
                    history=current.history + (review_event,),
                )
                affected.append(child_id)

            queue.extend(self._registry.children_of(child_id))

        material = "|".join(
            [theorem_id, reason, receipt_id, *sorted(affected)]
        )
        propagation_receipt = sha256(material.encode("utf-8")).hexdigest()

        return {
            "status": "PROPAGATED",
            "theorem_id": theorem_id,
            "affected": sorted(affected),
            "propagation_receipt": propagation_receipt,
        }

    @staticmethod
    def _require_nonempty(name: str, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ProofStateTransitionError(f"{name} must be a non-empty string")
        return value.strip()
