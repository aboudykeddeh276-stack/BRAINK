from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable, Mapping, Optional
import hashlib
import json
import time


def root(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FunctionRequirement:
    requirement_id: str
    capability: str
    statement: str
    acceptance_test_ids: tuple[str, ...]
    risk_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class GeneratedFunctionRecord:
    function_id: str
    capability: str
    source_root: str
    contract_root: str
    generator_id: str
    generator_group: str
    requirement_ids: tuple[str, ...]
    test_ids: tuple[str, ...]
    dependency_roots: tuple[str, ...]
    created_at_ns: int

    @property
    def provenance_root(self) -> str:
        return root(asdict(self))


@dataclass(frozen=True)
class VerificationRecord:
    verification_id: str
    function_id: str
    verifier_id: str
    verifier_group: str
    test_results_root: str
    static_analysis_root: str
    security_analysis_root: str
    approved: bool
    produced_at_ns: int


@dataclass(frozen=True)
class PromotionRecord:
    promotion_id: str
    function_id: str
    promoter_id: str
    promoter_group: str
    target_registry: str
    prior_registry_root: str
    successor_registry_root: str
    rollback_ref: str
    produced_at_ns: int


class SelfCodingGovernance:
    """Change-control and segregation-of-duties layer for generated functions."""

    def __init__(self):
        self.requirements: dict[str, FunctionRequirement] = {}
        self.generated: dict[str, GeneratedFunctionRecord] = {}
        self.verifications: list[VerificationRecord] = []
        self.promotions: list[PromotionRecord] = []
        self.revoked_functions: dict[str, str] = {}

    def add_requirement(self, requirement: FunctionRequirement) -> None:
        self.requirements[requirement.requirement_id] = requirement

    def record_generation(self, record: GeneratedFunctionRecord) -> None:
        missing = [rid for rid in record.requirement_ids if rid not in self.requirements]
        if missing:
            raise KeyError(f"UNKNOWN_REQUIREMENTS:{missing}")
        required_tests = set()
        for rid in record.requirement_ids:
            required_tests.update(self.requirements[rid].acceptance_test_ids)
        if not required_tests.issubset(set(record.test_ids)):
            raise RuntimeError("GENERATED_FUNCTION_MISSING_REQUIRED_ACCEPTANCE_TESTS")
        self.generated[record.function_id] = record

    def record_verification(self, record: VerificationRecord) -> None:
        generated = self.generated.get(record.function_id)
        if generated is None:
            raise KeyError(record.function_id)
        if record.verifier_id == generated.generator_id or record.verifier_group == generated.generator_group:
            raise RuntimeError("SEGREGATION_OF_DUTIES_VIOLATION")
        self.verifications.append(record)

    def promotable(self, function_id: str) -> Mapping[str, Any]:
        generated = self.generated.get(function_id)
        if generated is None:
            return {"promotable": False, "reason": "UNKNOWN_FUNCTION"}
        if function_id in self.revoked_functions:
            return {"promotable": False, "reason": "FUNCTION_REVOKED"}
        approved = [v for v in self.verifications if v.function_id == function_id and v.approved]
        if not approved:
            return {"promotable": False, "reason": "INDEPENDENT_VERIFICATION_ABSENT"}
        return {
            "promotable": True,
            "reason": "VERIFIED",
            "provenance_root": generated.provenance_root,
            "verification_ids": [v.verification_id for v in approved],
        }

    def record_promotion(self, record: PromotionRecord) -> None:
        state = self.promotable(record.function_id)
        if not state["promotable"]:
            raise RuntimeError(f"PROMOTION_REJECTED:{state['reason']}")
        generated = self.generated[record.function_id]
        if record.promoter_id == generated.generator_id or record.promoter_group == generated.generator_group:
            raise RuntimeError("GENERATOR_CANNOT_SELF_PROMOTE")
        if any(v.verifier_id == record.promoter_id for v in self.verifications if v.function_id == record.function_id):
            raise RuntimeError("VERIFIER_CANNOT_SELF_PROMOTE")
        if not record.rollback_ref:
            raise RuntimeError("ROLLBACK_REFERENCE_REQUIRED")
        self.promotions.append(record)

    def revoke(self, function_id: str, reason: str) -> None:
        if function_id not in self.generated:
            raise KeyError(function_id)
        self.revoked_functions[function_id] = reason

    def audit_snapshot(self) -> Mapping[str, Any]:
        snapshot = {
            "schema": "braink.self-coding-governance/v1",
            "requirements": [asdict(x) for x in self.requirements.values()],
            "generated": [asdict(x) for x in self.generated.values()],
            "verifications": [asdict(x) for x in self.verifications],
            "promotions": [asdict(x) for x in self.promotions],
            "revoked_functions": dict(self.revoked_functions),
            "generated_at_ns": time.time_ns(),
        }
        return {**snapshot, "snapshot_root": root(snapshot)}
