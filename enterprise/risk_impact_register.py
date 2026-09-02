from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping
import hashlib
import json
import time


def root(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RiskRecord:
    risk_id: str
    subject: str
    category: str
    likelihood: int
    consequence: int
    controls: tuple[str, ...]
    owner: str
    treatment: str
    residual_acceptance_ref: str = ""

    @property
    def inherent_score(self) -> int:
        return self.likelihood * self.consequence


@dataclass(frozen=True)
class ImpactRecord:
    impact_id: str
    ai_system: str
    affected_party: str
    impact_type: str
    severity: int
    probability: int
    mitigation_refs: tuple[str, ...]
    review_trigger: str

    @property
    def impact_score(self) -> int:
        return self.severity * self.probability


class RiskImpactRegister:
    def __init__(self):
        self.risks: dict[str, RiskRecord] = {}
        self.impacts: dict[str, ImpactRecord] = {}

    def add_risk(self, risk: RiskRecord) -> None:
        if not (1 <= risk.likelihood <= 5 and 1 <= risk.consequence <= 5):
            raise ValueError("RISK_SCALE_OUT_OF_RANGE")
        if not risk.owner or not risk.treatment:
            raise RuntimeError("RISK_OWNER_AND_TREATMENT_REQUIRED")
        self.risks[risk.risk_id] = risk

    def add_impact(self, impact: ImpactRecord) -> None:
        if not (1 <= impact.severity <= 5 and 1 <= impact.probability <= 5):
            raise ValueError("IMPACT_SCALE_OUT_OF_RANGE")
        if not impact.affected_party or not impact.review_trigger:
            raise RuntimeError("IMPACT_STAKEHOLDER_AND_REVIEW_TRIGGER_REQUIRED")
        self.impacts[impact.impact_id] = impact

    def release_view(self, risk_ids: tuple[str, ...], impact_ids: tuple[str, ...]) -> Mapping[str, Any]:
        missing_risks = [rid for rid in risk_ids if rid not in self.risks]
        missing_impacts = [iid for iid in impact_ids if iid not in self.impacts]
        risks = [self.risks[rid] for rid in risk_ids if rid in self.risks]
        impacts = [self.impacts[iid] for iid in impact_ids if iid in self.impacts]
        unresolved_acceptance = [r.risk_id for r in risks if r.inherent_score >= 15 and not r.residual_acceptance_ref]
        doc = {
            "schema": "braink.risk-impact-release-view/v1",
            "risks": [asdict(r) | {"inherent_score": r.inherent_score} for r in risks],
            "impacts": [asdict(i) | {"impact_score": i.impact_score} for i in impacts],
            "missing_risks": missing_risks,
            "missing_impacts": missing_impacts,
            "unresolved_acceptance": unresolved_acceptance,
            "generated_at_ns": time.time_ns(),
        }
        doc["status"] = "READY" if not missing_risks and not missing_impacts and not unresolved_acceptance else "INCOMPLETE"
        return {**doc, "view_root": root(doc)}
