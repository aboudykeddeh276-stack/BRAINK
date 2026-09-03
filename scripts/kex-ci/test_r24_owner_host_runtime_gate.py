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
    runtime_path = ROOT / "deployment/r23_owner_host_runtime.py"
    service_path = ROOT / "deployment/r23_foundry_closure_service.py"
    invariant_path = ROOT / "scripts/kex-ci/test_r23_owner_host_runtime.py"
    receipt_path = ROOT / "deployments/R24_R23_OWNER_HOST_ACTIVATION_RECEIPT_R1.json"
    profile_path = ROOT / "governance/ENGINEERING_STANDARD_PROFILE_R24.json"

    for path, marker in (
        (runtime_path, "R23_OWNER_HOST_RUNTIME_MISSING"),
        (service_path, "R23_FOUNDRY_SERVICE_MISSING"),
        (invariant_path, "R23_OWNER_HOST_INVARIANT_MISSING"),
        (receipt_path, "R24_OWNER_HOST_RECEIPT_MISSING"),
        (profile_path, "R24_PROFILE_MISSING"),
    ):
        assert path.exists(), marker

    receipt = json.loads(receipt_path.read_text("utf-8"))
    profile = json.loads(profile_path.read_text("utf-8"))
    execution = receipt["execution"]
    security_boundary = receipt["security_boundary"]
    claim_boundary = receipt["claim_boundary"]
    observed = set(receipt["observed_sequence"])

    # Reconcile only observed owner-host mechanics. Public and multi-host claims remain
    # explicitly outside the evidence boundary.
    assert receipt["status"] == "EXECUTED_AND_READBACK_VERIFIED"
    assert execution["static_validate"] == "PASS"
    assert execution["integration_test"] == "PASS"
    assert execution["marker"] == "R23_OWNER_HOST_RUNTIME_PASS"
    for required in {
        "PROCESS_START",
        "GET_/closure/health_PASS",
        "GET_/closure/state",
        "POST_customer.lifecycle.create_EXECUTED",
        "POST_customer.lifecycle.transition_EXECUTED",
        "STATE_READBACK_ACTIVE",
        "PROCESS_STOP",
        "PROCESS_RESTART",
        "STATE_ROOT_REHYDRATED_EQUAL",
        "GENERATION_REHYDRATED_EQUAL",
        "PROCESS_STOP_CLEAN",
    }:
        assert required in observed, f"OWNER_HOST_EVIDENCE_LOST:{required}"

    assert security_boundary["default_bind"] == "127.0.0.1"
    assert security_boundary["non_loopback_bind"] == "REJECTED"
    assert security_boundary["public_ingress_claim"] is False
    assert security_boundary["dns_tls_claim"] is False
    assert claim_boundary["single_host_process_activation"] is True
    assert claim_boundary["http_service_readback"] is True
    assert claim_boundary["durable_restart_rehydration"] is True
    assert claim_boundary["public_owner_host_ingress"] is False
    assert claim_boundary["authoritative_dns_tls"] is False
    assert claim_boundary["physical_multi_host"] is False

    decision = EngineeringDecision(
        decision_id="ADR-R24-R23-OWNER-HOST-GATE-001",
        title="Gate resident R23 owner-host activation without duplicating its process supervisor",
        context="R23 already demonstrates loopback process activation, mutation, readback, stop/restart and state-root rehydration through resident foundary mechanics.",
        decision="Reuse the resident R23 owner-host runtime and reject promotion until public ingress, authoritative DNS/TLS, physical multi-host execution, complete quality/security evidence and independent verification are supplied.",
        consequences=(
            "No duplicate process host or foundary service",
            "Single-host loopback execution remains valid internal evidence",
            "Public and physical multi-host claims remain unproven",
            "Promotion fails closed under R24",
        ),
    )

    evidence = Evidence(
        evidence_id="R24-R23-OWNER-HOST-ACTIVATION-R1",
        class_id="EXECUTED_SINGLE_HOST_RESTART_READBACK_EVIDENCE",
        subject="r23_owner_host_runtime_activation",
        status=receipt["status"],
        mechanism_ref="deployment/r23_owner_host_runtime.py",
        test_ref="scripts/kex-ci/test_r23_owner_host_runtime.py",
        evidence_root=hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
    )

    release = ReleaseManifestBuilder().build(
        release_id="R24-R23-OWNER-HOST-CANDIDATE-1",
        artifacts=[
            {"path": "deployment/r23_owner_host_runtime.py", "sha256": sha256_path(runtime_path)},
            {"path": "deployment/r23_foundry_closure_service.py", "sha256": sha256_path(service_path)},
            {"path": "scripts/kex-ci/test_r23_owner_host_runtime.py", "sha256": sha256_path(invariant_path)},
            {"path": "deployments/R24_R23_OWNER_HOST_ACTIVATION_RECEIPT_R1.json", "sha256": sha256_path(receipt_path)},
            {"path": "governance/ENGINEERING_STANDARD_PROFILE_R24.json", "sha256": sha256_path(profile_path)},
        ],
        decisions=[decision],
        evidence=[evidence],
    )

    required_quality = set(profile["standards"]["ISO_IEC_25010_2023"]["required_characteristics"])
    required_security = set(profile["standards"]["NIST_SP_800_218_SSDF_1_1"]["required_practice_groups"])

    quality = {key: False for key in required_quality}
    quality.update({
        "functional_suitability": True,
        "reliability": (
            "STATE_ROOT_REHYDRATED_EQUAL" in observed
            and "GENERATION_REHYDRATED_EQUAL" in observed
        ),
        "security": security_boundary["non_loopback_bind"] == "REJECTED",
    })

    security = {key: False for key in required_security}
    security.update({
        "protect_software": security_boundary["non_loopback_bind"] == "REJECTED",
        "produce_well_secured_software": (
            security_boundary["public_ingress_claim"] is False
            and security_boundary["dns_tls_claim"] is False
        ),
    })

    tests = {
        "unit": True,
        "integration": execution["integration_test"] == "PASS",
        "fault_injection": (
            execution["fault_boundary"] == "PROCESS_STOP_RESTART_REHYDRATE"
            and "STATE_ROOT_REHYDRATED_EQUAL" in observed
            and "GENERATION_REHYDRATED_EQUAL" in observed
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

    assert gate["status"] == "REJECTED", "R24_OWNER_HOST_MUST_NOT_PROMOTE"
    assert gate["criteria"]["release_root_valid"] is True
    assert gate["criteria"]["tests_pass"] is True
    assert gate["criteria"]["rollback_ready"] is True
    assert gate["criteria"]["independent_verifier"] is False
    assert gate["criteria"]["quality_complete"] is False
    assert gate["criteria"]["security_complete"] is False

    market = MarketReadinessEvaluator().evaluate(
        technical={
            "single_host_activation": 1.0,
            "restart_rehydration": 1.0,
            "public_ingress": 0.0,
            "physical_multi_host": 0.0,
        },
        operational={
            "rollback": 1.0,
            "independent_verification": 0.0,
            "production_ha": 0.0,
        },
        commercial={
            "public_service": 0.0,
            "authoritative_dns_tls": 0.0,
        },
        evidence_coverage=0.5,
    )
    assert market["classification"] == "ENGINEERING_ONLY"

    result = {
        "marker": "R24_OWNER_HOST_RUNTIME_GATE_PASS",
        "release_root": release["release_root"],
        "decision_root": decision.decision_root,
        "promotion_status": gate["status"],
        "promotion_root": gate["promotion_root"],
        "quality_missing": gate["quality_missing"],
        "security_missing": gate["security_missing"],
        "independent_verifier": gate["criteria"]["independent_verifier"],
        "market_classification": market["classification"],
        "market_root": market["evaluation_root"],
        "claim_boundary": claim_boundary,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print("R24_OWNER_HOST_RUNTIME_GATE_PASS")


if __name__ == "__main__":
    main()
