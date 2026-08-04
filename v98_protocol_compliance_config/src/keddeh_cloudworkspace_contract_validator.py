#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List


def require(text: str, token: str, errors: List[str], label: str) -> None:
    if token not in text:
        errors.append(f"{label}:missing:{token}")


def validate(root: Path) -> Dict[str, object]:
    deployment = root / "deploy" / "cloudworkspace-engine" / "cloudworkspace-engine.yaml"
    standards = root / "deploy" / "cloudworkspace-engine" / "DEPLOYMENT_STANDARDS.md"
    openapi = root / "api" / "mesh-engine-node-registry.openapi.yaml"
    ledger = root / "web" / "src" / "failure-ledger.ts"
    server = root / "services" / "cloudworkspace_engine" / "server.py"
    dockerfile = root / "services" / "cloudworkspace_engine" / "Dockerfile"
    runner_bootstrap = root / "scripts" / "bootstrap_m3_self_hosted_runner.command"
    kind_deploy = root / "scripts" / "deploy_cloudworkspace_kind_m3.command"
    errors: List[str] = []

    artifacts = (deployment, standards, openapi, ledger, server, dockerfile, runner_bootstrap, kind_deploy)
    for path in artifacts:
        if not path.exists():
            errors.append(f"missing_file:{path.relative_to(root)}")

    if errors:
        return {"valid": False, "errors": errors, "global_stop": False}

    deployment_text = deployment.read_text(encoding="utf-8")
    for token in (
        "kind: Deployment",
        "kind: Service",
        "type: ClusterIP",
        "kind: ConfigMap",
        "startupProbe:",
        "readinessProbe:",
        "livenessProbe:",
        "kind: PodDisruptionBudget",
        "kind: HorizontalPodAutoscaler",
        "kind: NetworkPolicy",
        "runAsNonRoot: true",
        "readOnlyRootFilesystem: true",
        "allowPrivilegeEscalation: false",
        "DEPENDENCY_POLICY_JSON",
        "A_W=f(W,C,E,S,V,O,L,T)",
    ):
        require(deployment_text, token, errors, "kubernetes")

    openapi_text = openapi.read_text(encoding="utf-8")
    for token in (
        "openapi: 3.0.3",
        "/healthz:",
        "/readyz:",
        "/v1/nodes:",
        "/v1/packages/manifests:",
        "/v1/failures:",
        "/v1/failures/{failureId}/reconcile:",
        "PackageManifestSubmission:",
        "FailureRecord:",
        "DependencyCriticality:",
        "globalStop:",
    ):
        require(openapi_text, token, errors, "openapi")

    ledger_text = ledger.read_text(encoding="utf-8")
    for token in (
        "export class FailureLedger",
        "indexedDB.open",
        "durability",
        "recoverOnStartup",
        "enqueueDeferredWork",
        "async reconcile",
        "REINTEGRATED",
        "globalStop: false",
        "receipt://failure-ledger/",
    ):
        require(ledger_text, token, errors, "failure-ledger")

    standards_text = standards.read_text(encoding="utf-8")
    for token in (
        "DEPENDENCY FAILURE != GLOBAL APPLICATION FAILURE",
        "IMPLEMENTED",
        "EXTERNALLY_PROVEN",
        "Bilateral evidence",
        "FailureLedger reintegration",
    ):
        require(standards_text, token, errors, "standards")

    server_text = server.read_text(encoding="utf-8")
    for token in (
        "ThreadingHTTPServer",
        "PRAGMA journal_mode=WAL",
        'path == "/startupz"',
        'path == "/healthz"',
        'path == "/readyz"',
        'path == "/v1/nodes"',
        'path == "/v1/packages/manifests"',
        'path == "/v1/failures"',
        'path.endswith("/reconcile")',
        '"globalStop": False',
        '"REINTEGRATED" if recovered else "DEFERRED"',
    ):
        require(server_text, token, errors, "cloudworkspace-runtime")

    docker_text = dockerfile.read_text(encoding="utf-8")
    for token in (
        "FROM python:3.12-slim",
        "USER 10001:10001",
        "HEALTHCHECK",
        'ENTRYPOINT ["python", "/app/server.py"]',
    ):
        require(docker_text, token, errors, "cloudworkspace-container")

    runner_text = runner_bootstrap.read_text(encoding="utf-8")
    for token in (
        "actions/runners/downloads",
        "actions/runners/registration-token",
        "osx",
        "arm64",
        "KEDDEH-M3",
        "./svc.sh install",
        "./svc.sh start",
    ):
        require(runner_text, token, errors, "m3-runner-bootstrap")

    kind_text = kind_deploy.read_text(encoding="utf-8")
    for token in (
        "kind create cluster",
        "docker build --platform linux/arm64",
        "kind load docker-image",
        "kubectl apply",
        "kubectl -n \"$NAMESPACE\" rollout status",
        "/startupz",
        "/healthz",
        "/readyz",
        "TARGET_HOST_PASS",
    ):
        require(kind_text, token, errors, "m3-kind-deployment")

    return {
        "version": "V106-CLOUDWORKSPACE-EXECUTABLE-1",
        "valid": not errors,
        "errors": errors,
        "artifacts": [str(path.relative_to(root)) for path in artifacts],
        "execution_paths": {
            "m3_runner_bootstrap": str(runner_bootstrap.relative_to(root)),
            "m3_kind_deployment": str(kind_deploy.relative_to(root)),
            "cloudworkspace_runtime": str(server.relative_to(root)),
            "cloudworkspace_container": str(dockerfile.relative_to(root)),
        },
        "global_stop": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    result = validate(root)
    if args.emit_receipt:
        target = root / "evidence" / "cloudworkspace_sovereign_contract_receipt.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
