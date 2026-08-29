from __future__ import annotations

from pathlib import Path

from src.keddeh_cloudworkspace_contract_validator import validate


def test_cloudworkspace_contracts_are_complete() -> None:
    root = Path(__file__).resolve().parents[1]
    result = validate(root)
    assert result["valid"] is True, result["errors"]
    assert result["global_stop"] is False
    assert len(result["artifacts"]) == 8
    assert result["execution_paths"]["m3_runner_bootstrap"].endswith("bootstrap_m3_self_hosted_runner.command")
    assert result["execution_paths"]["m3_kind_deployment"].endswith("deploy_cloudworkspace_kind_m3.command")


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


def test_cloudworkspace_runtime_is_runnable_and_persistent() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "services" / "cloudworkspace_engine" / "server.py").read_text(encoding="utf-8")
    assert "ThreadingHTTPServer" in text
    assert "PRAGMA journal_mode=WAL" in text
    assert 'path == "/startupz"' in text
    assert 'path == "/readyz"' in text
    assert 'path == "/healthz"' in text
    assert 'path == "/v1/packages/manifests"' in text
    assert 'path.endswith("/reconcile")' in text
    assert '"globalStop": False' in text


def test_m3_scripts_execute_runner_and_cluster_paths() -> None:
    root = Path(__file__).resolve().parents[1]
    runner = (root / "scripts" / "bootstrap_m3_self_hosted_runner.command").read_text(encoding="utf-8")
    deploy = (root / "scripts" / "deploy_cloudworkspace_kind_m3.command").read_text(encoding="utf-8")
    assert "actions/runners/registration-token" in runner
    assert "./svc.sh start" in runner
    assert "kind create cluster" in deploy
    assert "docker build --platform linux/arm64" in deploy
    assert "kind load docker-image" in deploy
    assert "rollout status" in deploy
    assert "TARGET_HOST_PASS" in deploy
