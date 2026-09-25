from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import math
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set


class GraphValidationError(Exception):
    """Raised when theorem-graph state or routing input is invalid."""


class ParentTheoremNotFoundError(GraphValidationError):
    """Raised when a theorem references a parent that is not registered."""


class TensorViolationError(GraphValidationError):
    """Raised when a theorem violates the minimum tensor constraint."""


@dataclass(frozen=True)
class TheoremNode:
    theorem_id: str
    constraints: Mapping[str, Any]
    parent_ids: tuple[str, ...] = field(default_factory=tuple)
    operators: frozenset[str] = field(default_factory=frozenset)


class MasterTheoremGraphRegistry:
    """Strict in-memory theorem registry with validated parent/operator inheritance."""

    MIN_TENSOR = 7.0

    def __init__(self) -> None:
        self._nodes: Dict[str, TheoremNode] = {}

    def register(
        self,
        theorem_id: str,
        constraints: Mapping[str, Any],
        parent_ids: Optional[Sequence[str]] = None,
        parent_operators: Optional[Sequence[str]] = None,
    ) -> TheoremNode:
        theorem_id = self._validate_theorem_id(theorem_id)
        if theorem_id in self._nodes:
            raise GraphValidationError(f"Theorem already registered: {theorem_id}")

        if not isinstance(constraints, Mapping):
            raise GraphValidationError("constraints must be a mapping")

        parent_ids = tuple(parent_ids or ())
        direct_operators = tuple(parent_operators or ())

        missing = [parent_id for parent_id in parent_ids if parent_id not in self._nodes]
        if missing:
            raise ParentTheoremNotFoundError(
                f"Missing parent theorem(s) for {theorem_id}: {', '.join(missing)}"
            )

        tensor_min = constraints.get("tensor_min")
        if isinstance(tensor_min, bool) or not isinstance(tensor_min, (int, float)):
            raise TensorViolationError(
                f"{theorem_id} requires numeric tensor_min >= {self.MIN_TENSOR}"
            )
        tensor_min = float(tensor_min)
        if not math.isfinite(tensor_min) or tensor_min < self.MIN_TENSOR:
            raise TensorViolationError(
                f"{theorem_id} tensor_min={tensor_min!r} violates minimum {self.MIN_TENSOR}"
            )

        inherited: Set[str] = set()
        for parent_id in parent_ids:
            inherited.update(self._nodes[parent_id].operators)

        for operator in direct_operators:
            if not isinstance(operator, str) or not operator.strip():
                raise GraphValidationError("operators must be non-empty strings")
            inherited.add(operator.strip())

        node = TheoremNode(
            theorem_id=theorem_id,
            constraints=dict(constraints),
            parent_ids=parent_ids,
            operators=frozenset(inherited),
        )
        self._nodes[theorem_id] = node
        return node

    def get(self, theorem_id: str) -> TheoremNode:
        try:
            return self._nodes[theorem_id]
        except KeyError as exc:
            raise GraphValidationError(f"Unregistered theorem: {theorem_id}") from exc

    def theorem_ids(self) -> tuple[str, ...]:
        return tuple(self._nodes.keys())

    def children_of(self, theorem_id: str) -> tuple[str, ...]:
        self.get(theorem_id)
        return tuple(
            node.theorem_id
            for node in self._nodes.values()
            if theorem_id in node.parent_ids
        )

    def __contains__(self, theorem_id: object) -> bool:
        return theorem_id in self._nodes

    @staticmethod
    def _validate_theorem_id(theorem_id: str) -> str:
        if not isinstance(theorem_id, str) or not theorem_id.strip():
            raise GraphValidationError("theorem_id must be a non-empty string")
        value = theorem_id.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.:-]+", value):
            raise GraphValidationError(
                "theorem_id may contain only letters, digits, _, ., :, and -"
            )
        return value


class StrictBranchRouter:
    """Routes only registered theorem objects through explicitly supported sectors."""

    ALLOWED_SECTORS = frozenset(
        {
            "cosmology",
            "semitic_decode",
            "governance",
            "runtime_architecture",
            "proof_systems",
            "observer_state",
            "motif_registry",
        }
    )

    def __init__(self, registry: MasterTheoremGraphRegistry) -> None:
        if not isinstance(registry, MasterTheoremGraphRegistry):
            raise GraphValidationError("registry must be a MasterTheoremGraphRegistry")
        self._registry = registry

    def route(self, theorem_id: str, context: Mapping[str, Any]) -> Dict[str, Any]:
        node = self._registry.get(theorem_id)
        if not isinstance(context, Mapping):
            raise GraphValidationError("route context must be a mapping")

        sector = context.get("sector")
        if sector not in self.ALLOWED_SECTORS:
            raise GraphValidationError(f"Unregistered sector: {sector!r}")

        resonance = context.get("resonance")
        if isinstance(resonance, bool) or not isinstance(resonance, (int, float)):
            raise GraphValidationError("resonance must be a finite numeric value")
        resonance = float(resonance)
        if not math.isfinite(resonance) or resonance <= 0:
            raise GraphValidationError("resonance must be finite and > 0")

        tensor_min = float(node.constraints["tensor_min"])
        operator_factor = max(1, len(node.operators))
        parent_factor = 1.0 + (0.125 * len(node.parent_ids))

        computed_metric = round(
            tensor_min * resonance * operator_factor * parent_factor,
            12,
        )

        route_material = (
            f"{node.theorem_id}|{sector}|{resonance:.12g}|{tensor_min:.12g}|"
            f"{','.join(sorted(node.operators))}|{','.join(node.parent_ids)}"
        )
        route_receipt = sha256(route_material.encode("utf-8")).hexdigest()

        return {
            "status": "VALIDATED_AND_ROUTED",
            "theorem_id": node.theorem_id,
            "sector": sector,
            "computed_metric": computed_metric,
            "operators": sorted(node.operators),
            "parent_ids": list(node.parent_ids),
            "route_receipt": route_receipt,
        }


class BilateralCompressor:
    """Produces a deterministic structural reduction while preserving a claim fingerprint."""

    _word_re = re.compile(r"[A-Za-z0-9']+")
    _stop_words = frozenset(
        {
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "be",
            "by",
            "for",
            "from",
            "in",
            "is",
            "it",
            "of",
            "on",
            "or",
            "that",
            "the",
            "this",
            "to",
            "with",
        }
    )

    def compress(self, text: str) -> Dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            raise GraphValidationError("compress expects non-empty text")

        words = self._word_re.findall(text)
        if not words:
            raise GraphValidationError("compress input contains no structural tokens")

        canonical = " ".join(word.lower() for word in words)
        fingerprint = sha256(canonical.encode("utf-8")).hexdigest()[:16]

        structural_tokens: List[str] = []
        seen: Set[str] = set()
        for word in words:
            token = word.lower()
            if token in self._stop_words or token in seen:
                continue
            seen.add(token)
            structural_tokens.append(token)

        compressed_form = (
            f"CLAIM[{fingerprint}]::TOKENS["
            + ",".join(structural_tokens)
            + "]"
        )

        return {
            "compressed_form": compressed_form,
            "input_word_count": len(words),
            "structural_token_count": len(structural_tokens),
            "input_char_count": len(text),
            "compressed_char_count": len(compressed_form),
            "reduction_ratio": round(len(compressed_form) / len(text), 6),
            "claim_fingerprint": fingerprint,
            "structural_tokens": structural_tokens,
        }
