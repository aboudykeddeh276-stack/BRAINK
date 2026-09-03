from __future__ import annotations

import hashlib
import json
import subprocess
import sys
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


def run_invariant(relpath: str) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / relpath)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"R24_FOUNDRY_RESIDENT_INVARIANT_FAILED:{relpath}:"
            f"exit={proc.returncode}:stdout={proc.stdout}:stderr={proc.stderr}"
        )
    return proc


def main() -> None:
    profile_path = ROOT / "governance/ENGINEERING_STANDARD_PROFILE_R24.json"
    r22_operational = ROOT / "scripts/kex-ci/test_foundry_operational_r22.py"
    r22_operations = ROOT / "scripts/kex-ci/test_foundry_operations_r22.py"
    r23_closure = ROOT / "scripts/kex-ci/test_foundry_closure_r23.py"
    r22_runtime = ROOT / "enterprise/foundry_operations_r22.py"
    r23_runtime = ROOT / "enterprise/foundry_closure_r23.py"

    for path in (
        profile_path,
        r22_operational,
        r22_operations,
        r23_closure,
        r22_runtime,
        r23_runtime,
    ):
        assert path.exists(), f"R24_FOUNDRY_REQUIRED_ARTIFACT_MISSING:{path.relative_to(ROOT)}"

    profile = json.loads(profile_path.read_text("utf-8"))

    operational = run_invariant("scripts/kex-ci/test_foundry_operational_r22.py")
    operations = run_invariant("scripts/kex-ci/test_foundry_operations_r22.py")
    closure = run_invariant("scripts/kex-ci/test_foundry_closure_r23.py")

    assert '"materialized_qualified": true' in operational.stdout.lower(), "R22_FOUNDRY_MATERIALIZATION_NOT_QUALIFIED"
    assert '"foundries": 18' in operational.stdout, "R22_FOUNDRY_COUNT_DRIFT"
    assert '"work_modules": 190' in operational.stdout, "R22_WORK_MODULE_COUNT_DRIFT"
    assert "R22_FOUNDRY_OPERATIONS_PASS" in operations.stdout, "R22_FOUNDRY_OPERATIONS_MARKER_MISSING"
    assert "R22_CUSTOMER_FILE_LIFECYCLE_PASS" in operations.stdout, "R22_CUSTOMER_LIFECYCLE_MARKER_MISSING"
    assert "R23_FOUNDRY_CLOSURE_PASS" in closure.stdout, "R23_FOUNDRY_CLOSURE_MARKER_MISSING"

    decision = EngineeringDecision(
        decision_id="ADR-R24-R22-R23-FOUNDRY-FAMILY-GATE-001",
        title="Gate resident R22/R23 foundry family without replacing its operational or closure runtimes",
        context=(
            "R22 already materializes and qualifies the foundry corpus and exercises undertaking, HR, server-room, "
            "workspace, VFS, customer-file, frontage, HCI, landing, research, agentic, software and internal-publication mechanics; "
            "R23 adds durable HR lease fencing, customer lifecycle, research promotion, internal publication and explicit external-actuator deferral."
        ),
        decision=(
            "Reuse the resident R22/R23 foundry mechanics, execute their invariants as prerequisite evidence, and reject promotion "
            "until dedicated fault injection, complete ISO/IEC 25010 and NIST SSDF coverage, rollback proof and independent verification exist."
        ),
        consequences=(
            "No duplicate foundry runtime or publication runtime",
            "R22 materialization and operational behavior become executable R24 prerequisite evidence",
            "R23 external activation deferral remains a boundary rather than a public-deployment claim",
            "Promotion fails closed until remaining R24 gates are reproducibly satisfied",
        ),
    )

    evidence = [
        Evidence(
            evidence_id="R24-R22-FOUNDRY-OPERATIONAL-R1",
            class_id="EXECUTED_RESIDENT_MATERIALIZATION_EVIDENCE",
            subject="r22_foundry_operational_materialization",
            status="PASS",
            mechanism_ref="enterprise/foundries/foundry_runtime_r22.py",
            test_ref="scripts/kex-ci/test_foundry_operational_r22.py",
            evidence_root=sha256_path(r22_operational),
        ),
        Evidence(
            evidence_id="R24-R22-FOUNDRY-OPERATIONS-R1",
            class_id="EXECUTED_RESIDENT_OPERATIONS_AND_REHYDRATION_EVIDENCE",
            subject="r22_foundry_operations",
            status="PASS",
            mechanism_ref="enterprise/foundry_operations_r22.py",
            test_ref="scripts/kex-ci/test_foundry_operations_r22.py",
            evidence_root=sha256_path(r22_operations),
        ),
        Evidence(
            evidence_id="R24-R23-FOUNDRY-CLOSURE-R1",
            class_id="EXECUTED_RESIDENT_CLOSURE_AND_EXTERNAL_BOUNDARY_EVIDENCE",
            subject="r23_foundry_closure",
            status="PASS",
            mechanism_ref="enterprise/foundry_closure_r23.py",
            test_ref="scripts/kex-ci/test_foundry_closure_r23.py",
            evidence_root=sha256_path(r23_closure),
        ),
    ]

    release = ReleaseManifestBuilder().build(
        release_id="R24-R22-R23-FOUNDRY-FAMILY-CANDIDATE-1",
        artifacts=[
            {"path": "enterprise/foundry_operations_r22.py", "sha256": sha256_path(r22_runtime)},
            {"path": "enterprise/foundry_closure_r23.py", "sha256": sha256_path(r23_runtime)},
            {"path": "scripts/kex-ci/test_foundry_operational_r22.py", "sha256": sha256_path(r22_operational)},
            {"path": "scripts/kex-ci/test_foundry_operations_r22.py", "sha256": sha256_path(r22_operations)},
            {"path": "scripts/kex-ci/test_foundry_closure_r23.py", "sha256": sha256_path(r23_closure)},
            {"path": "governance/ENGINEERING_STANDARD_PROFILE_R24.json", "sha256": sha256_path(profile_path)},
        ],
        decisions=[decision],
        evidence=evidence,
    )

    required_quality = set(profile["standards"]["ISO_IEC_25010_2023"]["required_characteristics"])
    required_security = set(profile["standards"]["NIST_SP_800_218_SSDF_1_1"]["required_practice_groups"])

    quality = {key: False for key in required_quality}
    quality.update(
        {
            "functional_suitability": True,
            "reliability": True,
            "maintainability": True,
        }
    )

    security = {key: False for key in required_security}
    security.update(
        {
            "protect_software": True,
            "produce_well_secured_software": True,
        }
    )

    tests = {
        "unit": True,
        "integration": True,
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

    assert gate["status"] == "REJECTED", "R24_FOUNDRY_FAMILY_MUST_NOT_PROMOTE"
    assert gate["criteria"]["release_root_valid"] is True
    assert gate["criteria"]["tests_pass"] is False
    assert gate["criteria"]["rollback_ready"] is False
    assert gate["criteria"]["independent_verifier"] is False
    assert gate["criteria"]["quality_complete"] is False
    assert gate["criteria"]["security_complete"] is False

    market = MarketReadinessEvaluator().evaluate(
        technical={
            "foundry_materialization": 1.0,
            "foundry_operations": 1.0,
            "durable_rehydration": 1.0,
            "external_activation": 0.0,
        },
        operational={
            "fault_injection": 0.0,
            "rollback": 0.0,
            "independent_verification": 0.0,
        },
        commercial={
            "public_service": 0.0,
            "production_release": 0.0,
        },
        evidence_coverage=0.45,
    )
    assert market["classification"] == "ENGINEERING_ONLY"

    result = {
        "marker": "R24_FOUNDRY_FAMILY_GATE_PASS",
        "release_root": release["release_root"],
        "decision_root": decision.decision_root,
        "promotion_status": gate["status"],
        "promotion_root": gate["promotion_root"],
        "quality_missing": gate["quality_missing"],
        "security_missing": gate["security_missing"],
        "fault_injection_complete": tests["fault_injection"],
        "rollback_ready": gate["criteria"]["rollback_ready"],
        "independent_verifier": gate["criteria"]["independent_verifier"],
        "market_classification": market["classification"],
        "market_root": market["evaluation_root"],
        "resident_boundaries": {
            "r22_foundries": 18,
            "r22_work_modules": 190,
            "r23_external_activation": "DEFERRED_EXTERNAL_ACTUATOR",
        },
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print("R24_FOUNDRY_FAMILY_GATE_PASS")


if __name__ == "__main__":
    main()
