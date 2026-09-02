from __future__ import annotations

import json
from pathlib import Path

from enterprise.architecture_verification import ArchitectureClaim, validate_matrix

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "enterprise" / "ARCHITECTURE_VERIFICATION_MATRIX_R19.json"

raw = json.loads(MATRIX.read_text("utf-8"))
claims = [
    ArchitectureClaim(
        subsystem=row["subsystem"],
        claim_id=row["claim_id"],
        claim=row["claim"],
        state=row["state"],
        mechanism_ref=row.get("mechanism_ref"),
        evidence_ref=row.get("evidence_ref"),
        cs_basis=tuple(row.get("cs_basis", ())),
        failure_reason=row.get("failure_reason"),
        missing_mechanism=row.get("missing_mechanism"),
    )
    for row in raw["claims"]
]
result = validate_matrix(claims)
assert result["claim_count"] == len(raw["claims"])
assert result["verified_or_executed"] > 0
assert result["unverified_or_failed"] > 0
assert raw["methodology"]["certification_claim"] == "NONE"
assert any(c.state == "FAILED" for c in claims)
assert any(c.state == "UNVERIFIED" for c in claims)
assert all(c.failure_reason and c.missing_mechanism for c in claims if c.state in {"FAILED", "UNVERIFIED"})
print("R19_ARCHITECTURE_VERIFICATION_PASS", result["verification_root"], result["claim_count"], result["verified_or_executed"], result["unverified_or_failed"])
