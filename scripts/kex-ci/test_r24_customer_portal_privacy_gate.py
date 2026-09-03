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
    membrane = ROOT / "enterprise/customer_access_control_r24.py"
    service = ROOT / "deployment/r23_foundry_closure_service.py"
    access_receipt_path = ROOT / "deployments/R24_CUSTOMER_ACCESS_CONTROL_RECEIPT_R1.json"
    http_receipt_path = ROOT / "deployments/R24_CUSTOMER_PORTAL_HTTP_BINDING_RECEIPT_R1.json"
    profile_path = ROOT / "governance/ENGINEERING_STANDARD_PROFILE_R24.json"

    for path in (membrane, service, access_receipt_path, http_receipt_path, profile_path):
        assert path.exists(), f"R24_CUSTOMER_PORTAL_REQUIRED_ARTIFACT_MISSING:{path}"

    access = json.loads(access_receipt_path.read_text("utf-8"))
    http = json.loads(http_receipt_path.read_text("utf-8"))
    profile = json.loads(profile_path.read_text("utf-8"))

    local = access["observed_local_invariant"]
    http_observed = http["observed_execution"]
    access_boundaries = access["claim_boundaries"]
    http_boundaries = http["claim_boundaries"]

    # Reconcile only observed evidence. Any disappearing proof must fail this gate closed.
    assert local["authorized_owner_read"] == "PASS"
    assert local["cross_customer_rejection"] == "PASS"
    assert local["privacy_consent_rejection"] == "PASS"
    assert local["expired_session_rejection"] == "PASS"
    assert local["revoked_session_rejection"] == "PASS"
    assert local["plaintext_session_persistence_rejection"] == "PASS"
    assert local["durable_session_and_audit_rehydration"] == "PASS"

    assert http_observed["owner_host_http_process"] == "PASS"
    assert http_observed["session_bind_http"] == "PASS"
    assert http_observed["authorized_customer_file_read"] == "PASS"
    assert http_observed["wrong_session_denial"] == "PASS"
    assert http_observed["cross_customer_denial"] == "PASS"
    assert http_observed["session_revoke_http"] == "PASS"
    assert http_observed["restart_rehydration"] == "PASS"
    assert http_observed["post_restart_revocation_denial"] == "PASS"
    assert http_observed["plaintext_session_token_persistence"] == "REJECTED"

    # Local/loopback proof must never be silently upgraded to public or production identity proof.
    assert access_boundaries["production_identity_assurance"] == "UNPROVEN"
    assert http_boundaries["public_ingress"] == "UNPROVEN"
    assert http_boundaries["external_idp_roundtrip"] == "UNPROVEN"
    assert http_boundaries["tls_public_origin"] == "UNPROVEN"
    assert http_boundaries["independent_verification"] == "PENDING"

    decision = EngineeringDecision(
        decision_id="ADR-R24-CUSTOMER-PORTAL-PRIVACY-GATE-001",
        title="Gate resident R23 customer portal and R24 privacy membrane without duplication",
        context="R23 closure and the R24 access membrane already provide durable customer lifecycle, loopback HTTP binding, ownership/scope/privacy enforcement, revocation and restart rehydration.",
        decision="Reuse the resident mechanics and reject promotion until missing public ingress, external identity-provider, TLS-origin, formal quality/security and independent-verification evidence is supplied.",
        consequences=(
            "No duplicate customer portal or session store",
            "Observed loopback HTTP evidence remains loopback evidence",
            "Public ingress and production identity assurance remain unproven",
            "Promotion fails closed until every mandatory R24 gate is evidenced",
        ),
    )

    evidence = [
        Evidence(
            evidence_id="R24-CUSTOMER-ACCESS-CONTROL-R1",
            class_id="EXECUTED_LOCAL_PRIVACY_EVIDENCE",
            subject="r23_customer_access_control",
            status=access["status"],
            mechanism_ref="enterprise/customer_access_control_r24.py",
            test_ref="deployments/R24_CUSTOMER_ACCESS_CONTROL_RECEIPT_R1.json",
            evidence_root=hashlib.sha256(access_receipt_path.read_bytes()).hexdigest(),
        ),
        Evidence(
            evidence_id="R24-CUSTOMER-PORTAL-HTTP-R1",
            class_id="EXECUTED_LOOPBACK_HTTP_EVIDENCE",
            subject="r23_customer_portal_http_binding",
            status=http["status"],
            mechanism_ref="deployment/r23_foundry_closure_service.py",
            test_ref="deployments/R24_CUSTOMER_PORTAL_HTTP_BINDING_RECEIPT_R1.json",
            evidence_root=http["receipt_root"],
        ),
    ]

    release = ReleaseManifestBuilder().build(
        release_id="R24-CUSTOMER-PORTAL-PRIVACY-CANDIDATE-1",
        artifacts=[
            {"path": "enterprise/customer_access_control_r24.py", "sha256": sha256_path(membrane)},
            {"path": "deployment/r23_foundry_closure_service.py", "sha256": sha256_path(service)},
            {"path": "deployments/R24_CUSTOMER_ACCESS_CONTROL_RECEIPT_R1.json", "sha256": sha256_path(access_receipt_path)},
            {"path": "deployments/R24_CUSTOMER_PORTAL_HTTP_BINDING_RECEIPT_R1.json", "sha256": sha256_path(http_receipt_path)},
            {"path": "governance/ENGINEERING_STANDARD_PROFILE_R24.json", "sha256": sha256_path(profile_path)},
        ],
        decisions=[decision],
        evidence=evidence,
    )

    required_quality = set(profile["standards"]["ISO_IEC_25010_2023"]["required_characteristics"])
    required_security = set(profile["standards"]["NIST_SP_800_218_SSDF_1_1"]["required_practice_groups"])

    quality = {k: False for k in required_quality}
    quality.update({
        "functional_suitability": True,
        "reliability": http_observed["restart_rehydration"] == "PASS",
        "security": (
            local["cross_customer_rejection"] == "PASS"
            and local["privacy_consent_rejection"] == "PASS"
            and local["plaintext_session_persistence_rejection"] == "PASS"
        ),
        "maintainability": False,
    })

    security = {k: False for k in required_security}
    security.update({
        "protect_software": (
            local["plaintext_session_persistence_rejection"] == "PASS"
            and http_observed["post_restart_revocation_denial"] == "PASS"
        ),
        "produce_well_secured_software": (
            local["expired_session_rejection"] == "PASS"
            and local["revoked_session_rejection"] == "PASS"
            and http_observed["cross_customer_denial"] == "PASS"
        ),
    })

    tests = {
        "unit": local["status"] == "PASS",
        "integration": (
            http_observed["owner_host_http_process"] == "PASS"
            and http_observed["authorized_customer_file_read"] == "PASS"
        ),
        "fault_injection": (
            http_observed["wrong_session_denial"] == "PASS"
            and http_observed["post_restart_revocation_denial"] == "PASS"
            and local["expired_session_rejection"] == "PASS"
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

    assert gate["status"] == "REJECTED", "R24_CUSTOMER_PORTAL_MUST_NOT_PROMOTE"
    assert gate["criteria"]["release_root_valid"] is True
    assert gate["criteria"]["tests_pass"] is True
    assert gate["criteria"]["rollback_ready"] is True
    assert gate["criteria"]["independent_verifier"] is False
    assert gate["criteria"]["quality_complete"] is False
    assert gate["criteria"]["security_complete"] is False

    market = MarketReadinessEvaluator().evaluate(
        technical={
            "access_membrane": 1.0,
            "loopback_http": 1.0,
            "restart_rehydration": 1.0,
            "public_ingress": 0.0,
            "tls_origin": 0.0,
        },
        operational={
            "rollback": 1.0,
            "independent_verification": 0.0,
            "external_idp_roundtrip": 0.0,
        },
        commercial={
            "public_customer_portal": 0.0,
            "production_identity_assurance": 0.0,
        },
        evidence_coverage=0.60,
    )
    assert market["classification"] == "ENGINEERING_ONLY"

    result = {
        "marker": "R24_CUSTOMER_PORTAL_PRIVACY_GATE_PASS",
        "release_root": release["release_root"],
        "decision_root": decision.decision_root,
        "promotion_status": gate["status"],
        "promotion_root": gate["promotion_root"],
        "quality_missing": gate["quality_missing"],
        "security_missing": gate["security_missing"],
        "independent_verifier": gate["criteria"]["independent_verifier"],
        "market_classification": market["classification"],
        "market_root": market["evaluation_root"],
        "claim_boundaries": {
            "access": access_boundaries,
            "http": http_boundaries,
        },
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print("R24_CUSTOMER_PORTAL_PRIVACY_GATE_PASS")


if __name__ == "__main__":
    main()
