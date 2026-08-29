from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_dependency_failure_orchestrator as orchestrator


def test_policy_uses_non_global_failure_rule() -> None:
    policy = orchestrator.load_policy(ROOT)
    assert policy["canonical_runtime_rule"] == "DEPENDENCY_FAILURE_NE_GLOBAL_RUNTIME_FAILURE"
    assert "EXTERNAL_GATE" in policy["dependency_classes"]
    assert "DEFERRED_COMMIT" in policy["dependency_classes"]


def test_known_blocked_lanes_continue_without_global_fail_stop() -> None:
    result = orchestrator.run_orchestrator(ROOT, emit_receipt=True)
    receipt = result["receipt"]
    assert receipt["promotion_state"] == "LOCAL_PASS"
    assert receipt["global_fail_stop_count"] == 0
    assert receipt["continuation_count"] == receipt["dependency_count"]
    assert result["global_runtime_failure_from_dependency_failure"] is False


def test_m3_host_acceptance_is_external_gate_not_runtime_failure() -> None:
    result = orchestrator.run_orchestrator(ROOT, emit_receipt=True)
    decisions = {decision["dependency_id"]: decision for decision in result["decisions"]}
    m3 = decisions["m3_host_acceptance"]
    assert m3["dependency_class"] == "EXTERNAL_GATE"
    assert m3["overall_status"] == "OPERATIONAL_EXTERNAL_GATE"
    assert m3["global_fail_stop"] is False
    assert "target_host_validation" in m3["impact_radius"]


def test_speaker_failure_is_optional_adapter_scope_only() -> None:
    result = orchestrator.run_orchestrator(ROOT, emit_receipt=True)
    decisions = {decision["dependency_id"]: decision for decision in result["decisions"]}
    audio = decisions["audio_output_adapter"]
    assert audio["dependency_class"] == "OPTIONAL"
    assert audio["overall_status"] == "OPERATIONAL"
    assert audio["fallback_path"] == "visual alert and logged notification"


def test_dependency_blocks_write_bounded_task_packets() -> None:
    result = orchestrator.run_orchestrator(ROOT, emit_receipt=True)
    for decision in result["decisions"]:
        assert decision["bounded_task_packet_required"] is True
        assert Path(decision["task_packet_path"]).exists()
    assert Path(result["receipt"]["outbox_manifest"]).exists()
    assert (ROOT / "evidence" / "dependency_failure_receipt.json").exists()
