from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Any, Iterable, Mapping


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_root(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


VALID_STATES = {"VERIFIED", "EXECUTED", "IMPLEMENTED", "BOUND", "UNVERIFIED", "FAILED"}


@dataclass(frozen=True)
class ArchitectureClaim:
    subsystem: str
    claim_id: str
    claim: str
    state: str
    mechanism_ref: str | None
    evidence_ref: str | None
    cs_basis: tuple[str, ...]
    failure_reason: str | None = None
    missing_mechanism: str | None = None

    @property
    def claim_root(self) -> str:
        return content_root(asdict(self))


def validate_claim(claim: ArchitectureClaim) -> None:
    if claim.state not in VALID_STATES:
        raise ValueError(f"INVALID_STATE:{claim.state}")
    if claim.state in {"VERIFIED", "EXECUTED"}:
        if not claim.mechanism_ref:
            raise ValueError(f"MISSING_MECHANISM:{claim.claim_id}")
        if not claim.evidence_ref:
            raise ValueError(f"MISSING_EVIDENCE:{claim.claim_id}")
        if claim.failure_reason or claim.missing_mechanism:
            raise ValueError(f"VERIFIED_CLAIM_HAS_FAILURE:{claim.claim_id}")
    if claim.state in {"UNVERIFIED", "FAILED"}:
        if not claim.failure_reason:
            raise ValueError(f"MISSING_FAILURE_REASON:{claim.claim_id}")
        if not claim.missing_mechanism:
            raise ValueError(f"MISSING_REQUIRED_MECHANISM:{claim.claim_id}")
    if not claim.cs_basis:
        raise ValueError(f"MISSING_CS_BASIS:{claim.claim_id}")


def validate_matrix(claims: Iterable[ArchitectureClaim]) -> Mapping[str, Any]:
    rows = list(claims)
    for claim in rows:
        validate_claim(claim)
    verified = [c for c in rows if c.state in {"VERIFIED", "EXECUTED"}]
    unresolved = [c for c in rows if c.state in {"UNVERIFIED", "FAILED"}]
    result = {
        "schema": "braink.architecture-verification-result.r19/v1",
        "claim_count": len(rows),
        "verified_or_executed": len(verified),
        "unverified_or_failed": len(unresolved),
        "claim_roots": [c.claim_root for c in rows],
    }
    result["verification_root"] = content_root(result)
    return result
