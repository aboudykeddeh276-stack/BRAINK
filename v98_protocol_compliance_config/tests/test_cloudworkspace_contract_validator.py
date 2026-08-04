from __future__ import annotations

from pathlib import Path

from src.keddeh_cloudworkspace_contract_validator import validate


def test_cloudworkspace_contracts_are_complete() -> None:
    root = Path(__file__).resolve().parents[1]
    result = validate(root)
    assert result["valid"] is True, result["errors"]
    assert result["global_stop"] is False
    assert len(result["artifacts"]) == 4


def test_kubernetes_manifest_separates_readiness_and_liveness() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "deploy" / "cloudworkspace-engine" / "cloudworkspace-engine.yaml").read_text(encoding="utf-8")
    assert "path: /readyz" in text
    assert "path: /healthz" in text
    assert "path: /startupz" in text
    assert "remote-telemetry\":\"DEFERRED_COMMIT" in text


def test_openapi_exposes_registry_manifest_and_failure_surfaces() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "api" / "mesh-engine-node-registry.openapi.yaml").read_text(encoding="utf-8")
    assert "/v1/nodes:" in text
    assert "/v1/packages/manifests:" in text
    assert "/v1/failures:" in text
    assert "/v1/failures/{failureId}/reconcile:" in text


def test_failure_ledger_is_persistent_and_reconciling() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "web" / "src" / "failure-ledger.ts").read_text(encoding="utf-8")
    assert "globalThis.indexedDB.open" in text
    assert "async recoverOnStartup" in text
    assert "async reconcile" in text
    assert "failure.state = remaining === 0 ? 'REINTEGRATED' : 'DEFERRED'" in text
