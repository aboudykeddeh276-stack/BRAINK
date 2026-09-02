from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Iterable, Mapping, Optional
import hashlib
import json
import time


def _root(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


class ControlState(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    PLANNED = "PLANNED"
    IMPLEMENTED = "IMPLEMENTED"
    EXECUTED = "EXECUTED"
    VERIFIED = "VERIFIED"
    NONCONFORMING = "NONCONFORMING"


@dataclass(frozen=True)
class StandardControl:
    control_id: str
    standard: str
    objective: str
    owner: str
    evidence_required: tuple[str, ...]
    state: ControlState = ControlState.PLANNED


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    control_id: str
    scope: str
    artifact_root: str
    producer: str
    produced_at_ns: int
    verified: bool

    @property
    def evidence_root(self) -> str:
        return _root(asdict(self))


@dataclass(frozen=True)
class Nonconformity:
    nc_id: str
    control_id: str
    description: str
    severity: str
    corrective_action: str
    owner: str
    due_state: str


class ISOReadyControlPlane:
    """Evidence-oriented readiness control. Does not assert certification."""

    def __init__(self, controls: Iterable[StandardControl]):
        self.controls = {c.control_id: c for c in controls}
        self.evidence: list[EvidenceRecord] = []
        self.nonconformities: list[Nonconformity] = []

    def attach_evidence(self, record: EvidenceRecord) -> None:
        if record.control_id not in self.controls:
            raise KeyError(record.control_id)
        self.evidence.append(record)

    def open_nonconformity(self, nc: Nonconformity) -> None:
        if nc.control_id not in self.controls:
            raise KeyError(nc.control_id)
        self.nonconformities.append(nc)

    def verify_control(self, control_id: str) -> Mapping[str, Any]:
        control = self.controls[control_id]
        evidence = [e for e in self.evidence if e.control_id == control_id and e.verified]
        supplied = {e.scope for e in evidence}
        missing = [x for x in control.evidence_required if x not in supplied]
        open_nc = [n for n in self.nonconformities if n.control_id == control_id]
        state = "VERIFIED" if not missing and not open_nc else "NONCONFORMING" if open_nc else "EVIDENCE_INCOMPLETE"
        return {
            "control_id": control_id,
            "standard": control.standard,
            "state": state,
            "missing_evidence": missing,
            "open_nonconformities": [asdict(n) for n in open_nc],
            "evidence_roots": [e.evidence_root for e in evidence],
        }

    def readiness_report(self) -> Mapping[str, Any]:
        results = [self.verify_control(cid) for cid in sorted(self.controls)]
        verified = sum(1 for r in results if r["state"] == "VERIFIED")
        return {
            "schema": "braink.iso-ready.report/v1",
            "generated_at_ns": time.time_ns(),
            "classification": "READINESS_EVIDENCE_NOT_CERTIFICATION",
            "controls_total": len(results),
            "controls_verified": verified,
            "controls": results,
            "report_root": _root(results),
        }


def default_braink_controls() -> tuple[StandardControl, ...]:
    return (
        StandardControl("LC-REQ", "ISO/IEC/IEEE 12207:2026", "Requirements are identified, traceable and acceptance-testable.", "BRAINK_REQUIREMENTS", ("requirements", "traceability", "acceptance_tests")),
        StandardControl("LC-CFG", "ISO/IEC/IEEE 12207:2026", "Configuration items, versions, baselines and changes are controlled.", "BRAINK_CONFIGURATION", ("baseline", "change_record", "rollback")),
        StandardControl("Q-PROD", "ISO/IEC 25010:2023", "Product quality requirements and objective measures are defined and evaluated.", "BRAINK_QUALITY", ("quality_requirements", "quality_tests", "quality_results")),
        StandardControl("IS-RISK", "ISO/IEC 27001:2022", "Information-security risk is assessed, treated and evidenced.", "BRAINK_SECURITY", ("risk_register", "treatment", "verification")),
        StandardControl("AI-AIMS", "ISO/IEC 42001:2023", "AI-system governance, roles, objectives, controls and continual improvement are evidenced.", "BRAINK_AI_GOVERNANCE", ("ai_inventory", "roles", "risk_controls", "review")),
        StandardControl("AI-RISK", "ISO/IEC 23894:2023", "AI-specific risks are integrated into lifecycle decisions and controls.", "BRAINK_AI_RISK", ("ai_risk_register", "mitigation", "monitoring")),
        StandardControl("AI-IMPACT", "ISO/IEC 42005:2025", "AI-system impacts are assessed through the lifecycle and updated on material change.", "BRAINK_AI_IMPACT", ("impact_assessment", "stakeholders", "impact_review")),
        StandardControl("REL-REC", "KEDDEH PROCESS-NATIVE + ISO-ready resilience", "Execution is restartable, reversible where required, and supported by durable evidence.", "BRAINK_RUNTIME", ("checkpoint", "recovery_test", "rollback")),
    )
