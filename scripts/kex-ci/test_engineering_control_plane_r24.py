from pathlib import Path
import tempfile
from enterprise.engineering_control_plane_r24 import (
    AppendOnlyLedger, EngineeringDecision, Evidence, ReconciliationEngine,
    ReleaseManifestBuilder, PromotionGate, MarketReadinessEvaluator, root
)

with tempfile.TemporaryDirectory(prefix="braink-r24-") as td:
    ledger = AppendOnlyLedger(Path(td) / "engineering-ledger.jsonl")
    r1 = ledger.append("DISCOVERY_AUDIT", "BRAINK", {"resident_capabilities": 20, "holes": 52})
    r2 = ledger.append("SOURCE_RECONCILIATION", "BRAINK", {"delta_count": 2})
    assert r2["predecessor_root"] == r1["record_root"]
    reloaded = AppendOnlyLedger(Path(td) / "engineering-ledger.jsonl")
    assert reloaded.ledger_root == r2["record_root"]

    decision = EngineeringDecision(
        "ADR-R24-001", "Mandatory evidence-gated promotion",
        "R23 permits durable execution but promotion needs architecture, quality, security and rollback gates.",
        "All deployable releases pass R24 PromotionGate.",
        ("promotion is reproducible", "failed gates are explicit", "rollback is mandatory")
    )
    evidence = Evidence("EV-R24-001", "EXECUTED", "foundry_closure_r23", "VERIFIED", "enterprise/foundry_closure_r23.py", "scripts/kex-ci/test_foundry_closure_r23.py", root({"test":"PASS"}))
    release = ReleaseManifestBuilder().build(
        "BRAINK-R24-TEST",
        [{"path":"enterprise/foundry_closure_r23.py","sha256":root({"artifact":"r23"})}],
        [decision], [evidence]
    )
    assert len(release["release_root"]) == 64

    reconcile = ReconciliationEngine().reconcile(
        {"runtime":"VERIFIED","mail":"VERIFIED"},
        {"runtime":"VERIFIED","mail":"UNVERIFIED","new_capability":"IMPLEMENTED"}
    )
    classes = {d["classification"] for d in reconcile["deltas"]}
    assert "OVERCLAIM" in classes
    assert "UNDOCUMENTED_RESIDENT_CAPABILITY" in classes

    quality = {k: True for k in PromotionGate.REQUIRED_QUALITY}
    security = {k: True for k in PromotionGate.REQUIRED_SECURITY}
    gate = PromotionGate()
    promoted = gate.evaluate(release, quality, security, {"unit":True,"integration":True,"fault_injection":True}, True, True)
    assert promoted["status"] == "PROMOTED"
    rejected = gate.evaluate(release, {**quality,"reliability":False}, security, {"unit":True}, True, True)
    assert rejected["status"] == "REJECTED" and "reliability" in rejected["quality_missing"]

    market = MarketReadinessEvaluator().evaluate(
        {"functional":0.95,"performance":0.90,"security":0.90},
        {"reliability":0.88,"support":0.82},
        {"value_proposition":0.86,"pricing":0.80},
        0.90
    )
    assert market["classification"] == "MARKET_READY_CANDIDATE"

print("R24_ENGINEERING_CONTROL_PLANE_PASS")
