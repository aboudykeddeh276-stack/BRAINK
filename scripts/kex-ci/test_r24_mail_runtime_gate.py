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
    control = ROOT / "deployments/R24_MAIL_CONTROL_PLANE_EXTERNAL_READBACK_R1.json"
    destination = ROOT / "deployments/R24_MAIL_DESTINATION_READBACK_R2.json"
    profile_path = ROOT / "governance/ENGINEERING_STANDARD_PROFILE_R24.json"

    for path in (control, destination, profile_path):
        assert path.exists(), f"MISSING_REQUIRED_ARTIFACT:{path}"

    c = json.loads(control.read_text("utf-8"))
    d = json.loads(destination.read_text("utf-8"))
    profile = json.loads(profile_path.read_text("utf-8"))

    observed = c["observed_execution"]
    c_bounds = c["claim_boundaries"]
    probe = d["probe"]
    transport = d["observed_transport_evidence"]
    recon = d["reconciliation"]

    # Executed external control-plane evidence.
    assert observed["add_result"] == "PASS"
    assert observed["mutation_readback"] == "PASS"
    assert observed["rollback_result"] == "PASS"
    assert observed["rollback_readback"] == "PASS"

    # Executed destination/submission evidence.
    assert probe["submission"] == "PASS"
    assert probe["inbox_readback"] == "PASS"
    assert probe["raw_mime_readback"] == "PASS"

    # Do not upgrade Gmail API submission/readback into SMTP/MX transport proof.
    assert transport["independent_mx_hop_observed"] is False
    assert transport["independent_smtp_hop_observed"] is False
    assert recon["smtp_transport_delivery"] == "UNPROVEN"
    assert recon["self_hosted_mail_server"] == "UNPROVEN"
    assert c_bounds["mx_dns_dkim_spf_dmarc"] == "UNPROVEN"
    assert c_bounds["customer_facing_mail_flow"] == "UNPROVEN"

    decision = EngineeringDecision(
        decision_id="ADR-R24-MAIL-RUNTIME-GATE-001",
        title="Gate resident Gmail control-plane and destination evidence without fabric duplication",
        context="R24 already records external Gmail mutation/readback/rollback and destination submission/readback evidence.",
        decision="Reuse the resident connector-backed mail control plane and reject promotion until transport, security, quality and independent-verifier evidence is complete.",
        consequences=(
            "No duplicate mail transport or connector runtime",
            "Gmail API evidence remains bounded to observed control-plane and mailbox effects",
            "SMTP/MX/DNS authentication claims remain unproven",
            "Promotion fails closed under R24",
        ),
    )

    evidence = [
        Evidence(
            evidence_id="R24-MAIL-CONTROL-PLANE-R1",
            class_id="EXECUTED_EXTERNAL_MUTATION_READBACK_ROLLBACK",
            subject="gmail_mail_control_plane",
            status=c["status"],
            mechanism_ref="enterprise/adapters/connector_bindings.py",
            test_ref="deployments/R24_MAIL_CONTROL_PLANE_EXTERNAL_READBACK_R1.json",
            evidence_root=c["receipt_root"],
        ),
        Evidence(
            evidence_id="R24-MAIL-DESTINATION-R2",
            class_id="EXECUTED_EXTERNAL_SUBMISSION_AND_MAILBOX_READBACK",
            subject="gmail_keddeh_destination_readback",
            status=d["status"],
            mechanism_ref="enterprise/adapters/connector_bindings.py",
            test_ref="deployments/R24_MAIL_DESTINATION_READBACK_R2.json",
            evidence_root=d["receipt_root"],
        ),
    ]

    release = ReleaseManifestBuilder().build(
        release_id="R24-MAIL-RUNTIME-CANDIDATE-1",
        artifacts=[
            {"path": "deployments/R24_MAIL_CONTROL_PLANE_EXTERNAL_READBACK_R1.json", "sha256": sha256_path(control)},
            {"path": "deployments/R24_MAIL_DESTINATION_READBACK_R2.json", "sha256": sha256_path(destination)},
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
        "reliability": observed["rollback_readback"] == "PASS",
        "compatibility": probe["inbox_readback"] == "PASS",
    })

    security = {k: False for k in required_security}
    # External connector effects exist, but no complete SSDF evidence package exists.

    tests = {
        "unit": False,
        "integration": True,
        "fault_injection": observed["rollback_result"] == "PASS" and observed["rollback_readback"] == "PASS",
    }

    gate = PromotionGate().evaluate(
        release=release,
        quality=quality,
        security=security,
        tests=tests,
        rollback_ready=True,
        independent_verifier=False,
    )

    assert gate["status"] == "REJECTED", "R24_MAIL_RUNTIME_MUST_NOT_PROMOTE"
    assert gate["criteria"]["release_root_valid"] is True
    assert gate["criteria"]["rollback_ready"] is True
    assert gate["criteria"]["independent_verifier"] is False
    assert gate["criteria"]["quality_complete"] is False
    assert gate["criteria"]["security_complete"] is False
    assert gate["criteria"]["tests_pass"] is False

    market = MarketReadinessEvaluator().evaluate(
        technical={"gmail_control_plane": 1.0, "mailbox_destination": 1.0, "smtp_transport": 0.0, "mx_authentication": 0.0},
        operational={"rollback": 1.0, "independent_verification": 0.0, "self_hosted_transport": 0.0},
        commercial={"customer_mail_flow": 0.0, "production_transport": 0.0},
        evidence_coverage=0.45,
    )
    assert market["classification"] == "ENGINEERING_ONLY"

    result = {
        "marker": "R24_MAIL_RUNTIME_GATE_PASS",
        "release_root": release["release_root"],
        "decision_root": decision.decision_root,
        "promotion_status": gate["status"],
        "promotion_root": gate["promotion_root"],
        "quality_missing": gate["quality_missing"],
        "security_missing": gate["security_missing"],
        "test_missing": gate["test_missing"],
        "failed_tests": gate["failed_tests"],
        "market_classification": market["classification"],
        "market_root": market["evaluation_root"],
        "transport_boundary": recon["smtp_transport_delivery"],
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print("R24_MAIL_RUNTIME_GATE_PASS")


if __name__ == "__main__":
    main()
