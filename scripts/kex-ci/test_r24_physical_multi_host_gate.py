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
    reconciliation_path = ROOT / "deployments/R24_KOS_MESH_RESIDENT_RECONCILIATION_R1.json"
    profile_path = ROOT / "governance/ENGINEERING_STANDARD_PROFILE_R24.json"
    verifier_path = ROOT / "enterprise/physical_host_evidence_r24.py"
    verifier_test_path = ROOT / "scripts/kex-ci/test_physical_host_evidence_r24.py"

    assert reconciliation_path.exists(), "R24_KOS_MESH_RECONCILIATION_MISSING"
    assert profile_path.exists(), "R24_PROFILE_MISSING"
    assert verifier_path.exists(), "R24_PHYSICAL_HOST_EVIDENCE_VERIFIER_MISSING"
    assert verifier_test_path.exists(), "R24_PHYSICAL_HOST_EVIDENCE_VERIFIER_TEST_MISSING"

    reconciliation = json.loads(reconciliation_path.read_text("utf-8"))
    profile = json.loads(profile_path.read_text("utf-8"))
    historical = reconciliation["observed_historical_evidence"]
    boundary = reconciliation["preserved_boundary"]

    assert reconciliation["subject"] == "R22_KOS_MESH_PHYSICAL_MULTI_HOST"
    assert reconciliation["classification"] == "UNDOCUMENTED_RESIDENT_CAPABILITY_RECONCILED_PHYSICAL_MULTI_HOST_UNPROVEN"
    assert reconciliation["r24_decision"].startswith("DO_NOT_REIMPLEMENT_MESH")

    for key in (
        "static_compilation",
        "three_local_nodes_real_sockets",
        "three_os_processes",
        "one_node_outage_2_of_3_continuation",
        "restart_anti_entropy_catchup",
        "dns_udp_tcp",
    ):
        assert historical[key] == "PASS", f"HISTORICAL_MESH_EVIDENCE_LOST:{key}"
    assert historical["test_suite"] == "33/33 PASS"

    assert boundary["distinct_physical_hosts"] == "UNEXECUTED"
    assert boundary["private_static_ips"] == "CONFIGURED_NOT_EXECUTED"
    assert boundary["physical_root"] == "UNTESTED"
    assert boundary["public_authoritative_dns"] == "UNAPPLIED"
    assert boundary["hardware_signer"] == "UNINSTANTIATED"

    decision = EngineeringDecision(
        decision_id="ADR-R24-R22-PHYSICAL-MULTI-HOST-GATE-003",
        title="Separate structural host-evidence qualification from physical execution verification",
        context=(
            "The resident K-OS/BOS mesh has historical local multi-process evidence, while distinct physical-host "
            "execution remains unobserved. The first R24 host-evidence verifier could return VERIFIED from structurally "
            "valid synthetic attestation objects. R24 classified that as OVERCLAIM because no externally anchored trust "
            "binding established that the attestors, hardware roots, machine fingerprints or evidence roots were genuine."
        ),
        decision=(
            "Reuse the resident mesh and retain the host-evidence component only as a fail-closed structural qualifier. "
            "It may emit STRUCTURALLY_QUALIFIED, but physical_host_status remains UNVERIFIED. Physical verification and "
            "promotion require a separate externally anchored trust-binding layer plus execution on distinct authorised "
            "hosts with quorum, fault-recovery and rollback evidence."
        ),
        consequences=(
            "No duplicate mesh implementation",
            "Synthetic fixtures cannot produce VERIFIED physical-host status",
            "Structural qualification and external trust verification are separate propositions",
            "Package hash equality and unique machine fingerprints remain mandatory",
            "Fault-recovery and rollback roots remain mandatory evidence fields",
            "Promotion fails closed until reproducible physical execution and trust binding exist",
        ),
        supersedes="ADR-R24-R22-PHYSICAL-MULTI-HOST-GATE-002",
    )

    evidence = Evidence(
        evidence_id="R24-R22-KOS-MESH-RESIDENT-R2",
        class_id="HISTORICAL_LOCAL_MULTI_PROCESS_MESH_EVIDENCE",
        subject="r22_kos_mesh_physical_multi_host",
        status=reconciliation["classification"],
        mechanism_ref="KEDDEH K-OS/BOS Mesh Substrate v2.0 + R24 structural host-evidence qualifier",
        test_ref="recorded 33/33 resident package suite + test_physical_host_evidence_r24.py contract invariant",
        evidence_root=sha256_path(reconciliation_path),
    )

    release = ReleaseManifestBuilder().build(
        release_id="R24-R22-PHYSICAL-MULTI-HOST-CANDIDATE-3",
        artifacts=[
            {
                "path": "deployments/R24_KOS_MESH_RESIDENT_RECONCILIATION_R1.json",
                "sha256": sha256_path(reconciliation_path),
            },
            {
                "path": "governance/ENGINEERING_STANDARD_PROFILE_R24.json",
                "sha256": sha256_path(profile_path),
            },
            {
                "path": "enterprise/physical_host_evidence_r24.py",
                "sha256": sha256_path(verifier_path),
            },
            {
                "path": "scripts/kex-ci/test_physical_host_evidence_r24.py",
                "sha256": sha256_path(verifier_test_path),
            },
        ],
        decisions=[decision],
        evidence=[evidence],
    )

    required_quality = set(profile["standards"]["ISO_IEC_25010_2023"]["required_characteristics"])
    required_security = set(profile["standards"]["NIST_SP_800_218_SSDF_1_1"]["required_practice_groups"])

    quality = {key: False for key in required_quality}
    quality.update({"functional_suitability": True, "reliability": True})

    security = {key: False for key in required_security}
    security.update({"protect_software": False, "produce_well_secured_software": False})

    tests = {
        "unit": True,
        "integration": False,
        "fault_injection": False,
    }

    gate = PromotionGate().evaluate(
        release=release,
        quality=quality,
        security=security,
        tests=tests,
        rollback_ready=False,
        independent_verifier=False,
    )

    assert gate["status"] == "REJECTED", "R24_PHYSICAL_MULTI_HOST_MUST_NOT_PROMOTE_WITHOUT_EXECUTION"
    assert gate["criteria"]["release_root_valid"] is True
    assert gate["criteria"]["tests_pass"] is False
    assert gate["criteria"]["rollback_ready"] is False
    assert gate["criteria"]["independent_verifier"] is False
    assert gate["criteria"]["quality_complete"] is False
    assert gate["criteria"]["security_complete"] is False

    market = MarketReadinessEvaluator().evaluate(
        technical={
            "resident_mesh_package": 1.0,
            "structural_host_evidence_qualifier": 1.0,
            "external_trust_binding": 0.0,
            "physical_multi_host": 0.0,
            "physical_host_identity_readback": 0.0,
            "physical_quorum_recovery": 0.0,
        },
        operational={
            "physical_deployment_rollback": 0.0,
            "independent_verification": 0.0,
            "hardware_signer": 0.0,
        },
        commercial={
            "public_authoritative_dns": 0.0,
            "production_multi_host_service": 0.0,
        },
        evidence_coverage=0.40,
    )
    assert market["classification"] == "ENGINEERING_ONLY"

    result = {
        "marker": "R24_PHYSICAL_MULTI_HOST_GATE_PASS",
        "release_root": release["release_root"],
        "decision_root": decision.decision_root,
        "promotion_status": gate["status"],
        "promotion_root": gate["promotion_root"],
        "physical_multi_host": boundary["distinct_physical_hosts"],
        "host_evidence_qualifier": "IMPLEMENTED_AND_CONTRACT_QUALIFIED",
        "physical_host_verification": "UNAVAILABLE_PENDING_EXTERNAL_TRUST_BINDING",
        "rollback_ready": gate["criteria"]["rollback_ready"],
        "independent_verifier": gate["criteria"]["independent_verifier"],
        "market_classification": market["classification"],
        "market_root": market["evaluation_root"],
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print("R24_PHYSICAL_MULTI_HOST_GATE_PASS")


if __name__ == "__main__":
    main()
