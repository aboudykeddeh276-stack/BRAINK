from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from enterprise.iso_ready_control import ISOReadyControlPlane, EvidenceRecord, Nonconformity, default_braink_controls
from enterprise.self_coding_governance import (
    SelfCodingGovernance, FunctionRequirement, GeneratedFunctionRecord,
    VerificationRecord, PromotionRecord,
)
from enterprise.release_qualification import ReleaseQualifier, ReleaseCandidate, GateResult


# ISO readiness evidence engine: incomplete evidence must not become verified.
plane = ISOReadyControlPlane(default_braink_controls())
assert plane.verify_control("AI-AIMS")["state"] == "EVIDENCE_INCOMPLETE"
plane.attach_evidence(EvidenceRecord("E1", "AI-AIMS", "ai_inventory", "a"*64, "agent://governance", 1, True))
plane.attach_evidence(EvidenceRecord("E2", "AI-AIMS", "roles", "b"*64, "agent://governance", 2, True))
plane.attach_evidence(EvidenceRecord("E3", "AI-AIMS", "risk_controls", "c"*64, "agent://risk", 3, True))
plane.attach_evidence(EvidenceRecord("E4", "AI-AIMS", "review", "d"*64, "agent://review", 4, True))
assert plane.verify_control("AI-AIMS")["state"] == "VERIFIED"

# Generated functions cannot self-verify or self-promote.
gov = SelfCodingGovernance()
gov.add_requirement(FunctionRequirement("REQ-1", "runtime.hash", "Produce canonical hash", ("T-HASH-1",)))
gen = GeneratedFunctionRecord(
    "fn://runtime/hash", "runtime.hash", "1"*64, "2"*64,
    "agent://evolution/a", "group://evolution", ("REQ-1",), ("T-HASH-1",), (), 10,
)
gov.record_generation(gen)
try:
    gov.record_verification(VerificationRecord("V-BAD", gen.function_id, "agent://evolution/a", "group://evolution", "3"*64, "4"*64, "5"*64, True, 11))
    raise AssertionError("self verification should fail")
except RuntimeError:
    pass

gov.record_verification(VerificationRecord("V-1", gen.function_id, "agent://verification/a", "group://verification", "3"*64, "4"*64, "5"*64, True, 12))
assert gov.promotable(gen.function_id)["promotable"] is True
try:
    gov.record_promotion(PromotionRecord("P-BAD", gen.function_id, "agent://verification/a", "group://verification", "registry://prod", "6"*64, "7"*64, "rollback://1", 13))
    raise AssertionError("verifier self promotion should fail")
except RuntimeError:
    pass

gov.record_promotion(PromotionRecord("P-1", gen.function_id, "agent://release/a", "group://release", "registry://prod", "6"*64, "7"*64, "rollback://1", 14))
assert len(gov.promotions) == 1

# Release qualification fails closed on missing gates.
qualifier = ReleaseQualifier()
candidate = ReleaseCandidate("R1", "braink", "a"*64, "b"*64, "c"*64, "d"*64, "e"*64, "rollback://r1", "change://r1")
partial = {"TESTS_PASS": GateResult("TESTS_PASS", "PASS", "f"*64)}
assert qualifier.qualify(candidate, partial)["status"] == "REJECTED"
all_gates = {g: GateResult(g, "PASS", (str(i % 10))*64) for i, g in enumerate(ReleaseQualifier.REQUIRED_GATES)}
assert qualifier.qualify(candidate, all_gates)["status"] == "QUALIFIED"

print("ISO_READY_CONTROLS_PASS")
