from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from keddeh_k_cloud_adapter import CircuitBreaker, FailureLedger, HealthStateMonitor, KCloudAdapter


def test_k_app_package_contains_required_manifests_and_integrity_readback_passes() -> None:
    adapter = KCloudAdapter(ROOT)
    package = adapter.scaffold_package()
    readback = adapter.integrity_readback(package)
    assert readback.all_required_files_present is True
    assert readback.manifest_valid is True
    assert readback.node_execution_allowed is True
    assert (package / "dependency-contracts.json").exists()
    assert (package / "degraded-mode-policy.json").exists()


def test_manifest_tamper_blocks_node_side_execution() -> None:
    adapter = KCloudAdapter(ROOT)
    package = adapter.scaffold_package(ROOT / "runtime_volume" / "k_app_packages" / "tamper_fixture")
    manifest = package / "k-app.manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["version"] = "tampered"
    manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")
    readback = adapter.integrity_readback(package)
    assert readback.node_execution_allowed is False
    assert readback.manifest_valid is False


def test_failure_ledger_records_and_reconciles_deferred_work() -> None:
    ledger = FailureLedger(ROOT)
    record = ledger.record_failure({
        "blocked_capability": "service.remote-telemetry",
        "blocked_domain": "service.remote-telemetry",
        "criticality": "DEFERRED_COMMIT",
        "root_cause": "unavailable",
        "impact_radius": ["remote_telemetry"],
        "unaffected_domains": ["application_core", "vfs"],
        "continuation_mode": "local telemetry outbox",
        "fallback_adapter": "adapter.local-telemetry-outbox",
        "durable_outbox": "runtime_volume/outbox/k_cloud/telemetry",
        "research_basis": ["durable outbox"],
        "required_changes": ["recover telemetry service"],
        "positive_tests": ["test_k_cloud_adapter"],
        "negative_tests": ["missing telemetry does not stop core"],
        "failover_tests": ["fallback outbox"],
        "recovery_tests": ["reconcile"],
        "reentry_conditions": ["telemetry service healthy"],
        "promotion_evidence": ["receipt"],
        "owner": "k_cloud_adapter",
    })
    assert record.criticality == "DEFERRED_COMMIT"
    assert ledger.categorize().get("DEFERRED_COMMIT", 0) >= 1
    assert ledger.reconcile_deferred_work(["service.remote-telemetry"]) >= 1


def test_health_state_monitor_triggers_degraded_ui_without_global_failure() -> None:
    adapter = KCloudAdapter(ROOT)
    monitor = HealthStateMonitor(adapter.policy)
    projection = monitor.observe({
        "service.vfs": "HEALTHY",
        "service.runtime-config": "HEALTHY",
        "service.agent-registry": "DEGRADED",
        "service.native-gpu": "REPLACEABLE",
        "service.audio-output": "FAILED_OPTIONAL",
        "service.remote-telemetry": "DEFERRED_COMMIT",
        "service.mesh-registry": "EXTERNAL_GATE",
    })
    assert projection.degraded_ui_state is True
    assert projection.core_semantic_validity == "PRESERVED"
    assert projection.overall_state == "OPERATIONAL_DEGRADED"


def test_circuit_breaker_opens_and_prevents_cascading_external_calls() -> None:
    breaker = CircuitBreaker("service.mesh-registry", failure_threshold=2, recovery_timeout_seconds=60)
    assert breaker.allow_call() is True
    breaker.record_failure(now=100.0)
    assert breaker.state == "CLOSED"
    breaker.record_failure(now=101.0)
    assert breaker.state == "OPEN"
    assert breaker.allow_call(now=102.0) is False


def test_k_cloud_deploy_emits_receipt_and_keeps_dependency_failures_contained() -> None:
    adapter = KCloudAdapter(ROOT)
    result = adapter.deploy(emit_receipt=True)
    receipt = result["receipt"]
    assert result["runtime_rule"] == "DEPENDENCY_FAILURE_NE_GLOBAL_APPLICATION_FAILURE"
    assert result["dependency_failure_as_global_application_failure"] is False
    assert receipt["integrity_readback_before_node_execution"] is True
    assert receipt["node_execution_started"] is True
    assert receipt["overall_state"] in {"OPERATIONAL_DEGRADED", "OPERATIONAL_EXTERNAL_GATE", "OPERATIONAL"}
    assert Path(receipt["receipt_path"]).exists()
    assert Path(receipt["outbox_manifest"]).exists()
