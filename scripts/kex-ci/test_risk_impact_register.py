from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from enterprise.risk_impact_register import RiskImpactRegister, RiskRecord, ImpactRecord

reg = RiskImpactRegister()
reg.add_risk(RiskRecord(
    "R-AI-001", "capability://self-code", "incorrect generated function", 3, 5,
    ("independent verification", "acceptance tests", "rollback"), "role://ai-risk-owner",
    "reduce", "acceptance://R-AI-001",
))
reg.add_impact(ImpactRecord(
    "I-AI-001", "braink://self-evolution", "service user", "incorrect automated system mutation",
    4, 3, ("control://segregation-of-duties", "control://rollback"), "material capability or authority change",
))
view = reg.release_view(("R-AI-001",), ("I-AI-001",))
assert view["status"] == "READY"
assert view["risks"][0]["inherent_score"] == 15
assert view["impacts"][0]["impact_score"] == 12
print("RISK_IMPACT_REGISTER_PASS")
