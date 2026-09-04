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
            f"R24_AGENT_AUTHORITY_RESIDENT_INVARIANT_FAILED:{relpath}:"
            f"exit={proc.returncode}:stdout={proc.stdout}:stderr={proc.stderr}"
        )
    return proc


def main() -> None:
    profile_path = ROOT / "governance/ENGINEERING_STANDARD_PROFILE_R24.json"
    r6_test = ROOT / "scripts/kex-ci/test_agent_authority_actual_process_r6.py"
    r7_test = ROOT / "scripts/kex-ci/test_agent_function_actual_process_r7.py"
    runtime = ROOT / "mcp/braink_process_adapter/capability_runtime.py"
    catalog = ROOT / "mcp/braink_process_adapter/capability_catalog.py"
    backend = ROOT / "mcp/braink_process_adapter/backend.py"
    agent_client = ROOT / "mcp/braink_process_adapter/agent_authority_client.py"
    function_contracts = ROOT / "mcp/braink_process_adapter/function_contracts.py"

    for path in (
        profile_path,
        r6_test,
        r7_test,
        runtime,
        catalog,
        backend,
        agent_client,
        function_contracts,
    ):
        assert path.exists(), f"R24_AGENT_AUTHORITY_REQUIRED_ARTIFACT_MISSING:{path.relative_to(ROOT)}"

    profile = json.loads(profile_path.read_text("utf-8"))
    r6 = run_invariant("scripts/kex-ci/test_agent_authority_actual_process_r6.py")
    r7 = run_invariant("scripts/kex-ci/test_agent_function_actual_process_r7.py")

    assert "R6_AGENT_AUTHORITY_ACTUAL_PROCESS_PASS" in r6.stdout, "R6_AGENT_AUTHORITY_MARKER_MISSING"
    assert "R7_AGENT_FUNCTION_ACTUAL_PROCESS_PASS" in r7.stdout, "R7_AGENT_FUNCTION_MARKER_MISSING"

    decision = EngineeringDecision(
        decision_id="ADR-R24-R6-R7-AGENT-AUTHORITY-GATE-001",
        title="Gate resident R6/R7 agent authority and typed function surface without duplicating mutators",
        context=(
            "R6 already derives governed agent authority from the resident capability runtime with scope checks, lease fencing, "
            "idempotent execution and semantic resident failure propagation. R7 derives typed function contracts from that live "
            "authority surface and rejects invalid payloads before governed invocation-ledger mutation."
        ),
        decision=(
            "Reuse the resident R6/R7 authority chain as executable evidence, preserve direct-mutator fencing, and reject promotion "
            "until rollback readiness, complete ISO/IEC 25010 and NIST SSDF coverage, and independent verification are demonstrated."
        ),
        consequences=(
            "No duplicate agent authority runtime or raw mutator façade",
            "R6 scope denial, stale-lease fencing, idempotent replay and resident failure propagation remain authoritative evidence",
            "R7 typed-payload rejection before invocation-ledger mutation becomes explicit R24 validation evidence",
            "Promotion remains fail-closed pending rollback, complete quality/security evidence and independent verification",
        ),
    )

    evidence = [
        Evidence(
            evidence_id="R24-R6-AGENT-AUTHORITY-ACTUAL-R1",
            class_id="EXECUTED_RESIDENT_AUTHORITY_AND_ADVERSE_PATH_EVIDENCE",
            subject="r6_agent_authority_actual_process",
            status="PASS",
            mechanism_ref="mcp/braink_process_adapter/agent_authority_client.py",
            test_ref="scripts/kex-ci/test_agent_authority_actual_process_r6.py",
            evidence_root=sha256_path(r6_test),
        ),
        Evidence(
            evidence_id="R24-R7-TYPED-FUNCTION-ACTUAL-R1",
            class_id="EXECUTED_TYPED_CONTRACT_AND_PRE_LEDGER_REJECTION_EVIDENCE",
            subject="r7_typed_agent_function_actual_process",
            status="PASS",
            mechanism_ref="mcp/braink_process_adapter/function_contracts.py",
            test_ref="scripts/kex-ci/test_agent_function_actual_process_r7.py",
            evidence_root=sha256_path(r7_test),
        ),
    ]

    release = ReleaseManifestBuilder().build(
        release_id="R24-R6-R7-AGENT-AUTHORITY-CANDIDATE-1",
        artifacts=[
            {"path": "mcp/braink_process_adapter/capability_runtime.py", "sha256": sha256_path(runtime)},
            {"path": "mcp/braink_process_adapter/capability_catalog.py", "sha256": sha256_path(catalog)},
            {"path": "mcp/braink_process_adapter/backend.py", "sha256": sha256_path(backend)},
            {"path": "mcp/braink_process_adapter/agent_authority_client.py", "sha256": sha256_path(agent_client)},
            {"path": "mcp/braink_process_adapter/function_contracts.py", "sha256": sha256_path(function_contracts)},
            {"path": "scripts/kex-ci/test_agent_authority_actual_process_r6.py", "sha256": sha256_path(r6_test)},
            {"path": "scripts/kex-ci/test_agent_function_actual_process_r7.py", "sha256": sha256_path(r7_test)},
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
        "fault_injection": True,
    }

    gate = PromotionGate().evaluate(
        release=release,
        quality=quality,
        security=security,
        tests=tests,
        rollback_ready=False,
        independent_verifier=False,
    )

    assert gate["status"] == "REJECTED", "R24_AGENT_AUTHORITY_MUST_NOT_PROMOTE"
    assert gate["criteria"]["release_root_valid"] is True
    assert gate["criteria"]["tests_pass"] is True
    assert gate["criteria"]["rollback_ready"] is False
    assert gate["criteria"]["independent_verifier"] is False
    assert gate["criteria"]["quality_complete"] is False
    assert gate["criteria"]["security_complete"] is False

    market = MarketReadinessEvaluator().evaluate(
        technical={
            "resident_authority_runtime": 1.0,
            "typed_function_contracts": 1.0,
            "lease_fencing": 1.0,
            "pre_ledger_payload_rejection": 1.0,
        },
        operational={
            "adverse_path_execution": 1.0,
            "rollback": 0.0,
            "independent_verification": 0.0,
        },
        commercial={
            "public_service": 0.0,
            "production_release": 0.0,
        },
        evidence_coverage=0.60,
    )
    assert market["classification"] == "ENGINEERING_ONLY"

    result = {
        "marker": "R24_AGENT_AUTHORITY_GATE_PASS",
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
            "capability_count": 14,
            "direct_mutator_exposure": False,
            "typed_payload_rejection_before_invocation_ledger": True,
            "stale_lease_fencing": True,
            "semantic_resident_failure_propagation": True,
        },
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print("R24_AGENT_AUTHORITY_GATE_PASS")


if __name__ == "__main__":
    main()
