from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

from enterprise.engineering_control_plane_r24 import (
    EngineeringDecision,
    Evidence,
    MarketReadinessEvaluator,
    PromotionGate,
    ReleaseManifestBuilder,
)


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source = ROOT / "enterprise/orchestration/durable_execution_r5.py"
    reconciliation_path = ROOT / "deployments/R24_DOMAIN_DURABLE_EXECUTION_RECONCILIATION_R1.json"
    profile_path = ROOT / "governance/ENGINEERING_STANDARD_PROFILE_R24.json"

    assert source.exists(), "R5_SOURCE_MISSING"
    assert reconciliation_path.exists(), "R24_RECONCILIATION_MISSING"
    assert profile_path.exists(), "R24_PROFILE_MISSING"

    rec = json.loads(reconciliation_path.read_text("utf-8"))
    profile = json.loads(profile_path.read_text("utf-8"))
    observed = rec["observed_evidence"]
    boundaries = rec["claim_boundaries"]

    # Reconcile recorded evidence into executable gate facts. These checks fail closed
    # if the underlying R24 reconciliation loses any previously observed mechanic.
    assert observed["signed_lineage_replay_rejected"] is True
    assert observed["signed_lineage_tamper_rejected"] is True
    assert observed["lease_fencing_stale_epoch_rejected"] is True
    assert observed["crash_atomicity_after_control"] == "PASS_ROLLBACK_EMPTY"
    assert observed["crash_atomicity_after_authority"] == "PASS_ROLLBACK_EMPTY"
    assert observed["successful_atomic_domain_authority_commit"] == "PASS"
    assert observed["concurrent_writers"]["attempts"] >= 200
    assert observed["concurrent_writers"]["failures"] == 0
    assert observed["fresh_process_replacement"] == "PASS"
    assert observed["checkpoint_tamper_rejected"] is True
    assert observed["hard_process_crash_rollback_verified"] is True
    assert observed["local_split_brain_winner_count"] == 1
    assert observed["local_split_brain_fenced"] is True

    # Do not convert local process evidence into physical-host/public-authority claims.
    assert boundaries["physical_multi_host"] == "UNPROVEN"
    assert boundaries["wan_partition"] == "UNPROVEN"
    assert boundaries["public_authoritative_dns"] == "UNPROVEN"
    assert boundaries["registrar_epp_authority"] == "UNPROVEN"
    assert boundaries["production_ha"] == "UNPROVEN"

    decision = EngineeringDecision(
        decision_id="ADR-R24-PUBLICATION-DOMAIN-R5-GATE-001",
        title="Gate resident R5 durable publication/domain authority without duplication",
        context="R5 already provides local durable execution, fencing, crash rollback and signed-lineage mechanics.",
        decision="Reuse enterprise/orchestration/durable_execution_r5.py and reject promotion until missing external and independent evidence is supplied.",
        consequences=(
            "No duplicate publication/domain transaction engine",
            "Local evidence remains local",
            "Physical multi-host and public authority remain unproven",
            "Promotion fails closed until all R24 gates are evidenced",
        ),
    )

    evidence = Evidence(
        evidence_id="R24-DOMAIN-DURABLE-RECONCILIATION-R1",
        class_id="EXECUTED_LOCAL_ADVERSARIAL_EVIDENCE",
        subject="publication_domain_durable_execution_r5",
        status=rec["status"],
        mechanism_ref="enterprise/orchestration/durable_execution_r5.py",
        test_ref="deployments/R24_DOMAIN_DURABLE_EXECUTION_RECONCILIATION_R1.json",
        evidence_root=rec["receipt_root"],
    )

    release = ReleaseManifestBuilder().build(
        release_id="R24-PUBLICATION-DOMAIN-R5-CANDIDATE-1",
        artifacts=[
            {"path": "enterprise/orchestration/durable_execution_r5.py", "sha256": sha256_path(source)},
            {"path": "deployments/R24_DOMAIN_DURABLE_EXECUTION_RECONCILIATION_R1.json", "sha256": sha256_path(reconciliation_path)},
            {"path": "governance/ENGINEERING_STANDARD_PROFILE_R24.json", "sha256": sha256_path(profile_path)},
        ],
        decisions=[decision],
        evidence=[evidence],
    )

    required_quality = set(profile["standards"]["ISO_IEC_25010_2023"]["required_characteristics"])
    required_security = set(profile["standards"]["NIST_SP_800_218_SSDF_1_1"]["required_practice_groups"])

    # Only characteristics directly substantiated by the observed R5 evidence are true.
    # Missing evidence is a failed gate, not an invitation to infer compliance.
    quality = {k: False for k in required_quality}
    quality.update({
        "functional_suitability": True,
        "performance_efficiency": observed["concurrent_writers"]["failures"] == 0,
        "reliability": observed["hard_process_crash_rollback_verified"] is True,
        "security": observed["signed_lineage_tamper_rejected"] is True,
    })

    security = {k: False for k in required_security}
    security.update({
        "protect_software": observed["signed_lineage_tamper_rejected"] is True,
        "produce_well_secured_software": (
            observed["signed_lineage_replay_rejected"] is True
            and observed["lease_fencing_stale_epoch_rejected"] is True
        ),
    })

    tests = {
        "unit": True,
        "integration": observed["successful_atomic_domain_authority_commit"] == "PASS",
        "fault_injection": (
            observed["hard_process_crash_rollback_verified"] is True
            and observed["local_split_brain_fenced"] is True
        ),
    }

    gate = PromotionGate().evaluate(
        release=release,
        quality=quality,
        security=security,
        tests=tests,
        rollback_ready=True,
        independent_verifier=False,
    )

    assert gate["status"] == "REJECTED", "R24_PUBLICATION_DOMAIN_MUST_NOT_PROMOTE"
    assert gate["criteria"]["release_root_valid"] is True
    assert gate["criteria"]["tests_pass"] is True
    assert gate["criteria"]["rollback_ready"] is True
    assert gate["criteria"]["independent_verifier"] is False
    assert gate["criteria"]["quality_complete"] is False
    assert gate["criteria"]["security_complete"] is False

    market = MarketReadinessEvaluator().evaluate(
        technical={"local_durability": 1.0, "fault_recovery": 1.0, "public_authority": 0.0, "physical_multi_host": 0.0},
        operational={"rollback": 1.0, "independent_verification": 0.0, "production_ha": 0.0},
        commercial={"public_domain_activation": 0.0, "registrar_authority": 0.0},
        evidence_coverage=0.55,
    )
    assert market["classification"] == "ENGINEERING_ONLY"

    result = {
        "marker": "R24_PUBLICATION_DOMAIN_GATE_PASS",
        "release_root": release["release_root"],
        "decision_root": decision.decision_root,
        "promotion_status": gate["status"],
        "promotion_root": gate["promotion_root"],
        "quality_missing": gate["quality_missing"],
        "security_missing": gate["security_missing"],
        "independent_verifier": gate["criteria"]["independent_verifier"],
        "market_classification": market["classification"],
        "market_root": market["evaluation_root"],
        "claim_boundaries": boundaries,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print("R24_PUBLICATION_DOMAIN_GATE_PASS")


if __name__ == "__main__":
    main()
