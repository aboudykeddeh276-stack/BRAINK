from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping
import hashlib
import json
import time


def root(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    status: str
    evidence_root: str
    reason: str = ""


@dataclass(frozen=True)
class ReleaseCandidate:
    release_id: str
    scope: str
    source_root: str
    requirements_root: str
    test_root: str
    risk_root: str
    sbom_root: str
    rollback_ref: str
    change_record_ref: str


class ReleaseQualifier:
    REQUIRED_GATES = (
        "REQUIREMENTS_TRACEABLE",
        "TESTS_PASS",
        "SECURITY_REVIEW",
        "RISK_ACCEPTED",
        "SBOM_PRESENT",
        "ROLLBACK_PROVEN",
        "CHANGE_CONTROLLED",
        "INDEPENDENT_REVIEW",
    )

    def qualify(self, candidate: ReleaseCandidate, gates: Mapping[str, GateResult]) -> Mapping[str, Any]:
        missing = [g for g in self.REQUIRED_GATES if g not in gates]
        failed = [g for g, r in gates.items() if g in self.REQUIRED_GATES and r.status != "PASS"]
        structural_missing = [
            name for name, value in {
                "source_root": candidate.source_root,
                "requirements_root": candidate.requirements_root,
                "test_root": candidate.test_root,
                "risk_root": candidate.risk_root,
                "sbom_root": candidate.sbom_root,
                "rollback_ref": candidate.rollback_ref,
                "change_record_ref": candidate.change_record_ref,
            }.items() if not value
        ]
        status = "QUALIFIED" if not missing and not failed and not structural_missing else "REJECTED"
        record = {
            "schema": "braink.release-qualification/v1",
            "release": asdict(candidate),
            "status": status,
            "missing_gates": missing,
            "failed_gates": failed,
            "structural_missing": structural_missing,
            "gates": {k: asdict(v) for k, v in sorted(gates.items())},
            "qualified_at_ns": time.time_ns(),
            "classification": "INTERNAL_RELEASE_QUALIFICATION_NOT_ISO_CERTIFICATION",
        }
        return {**record, "qualification_root": root(record)}
