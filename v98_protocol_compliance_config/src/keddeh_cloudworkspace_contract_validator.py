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
    errors: List[str] = []

    for path in (deployment, standards, openapi, ledger):
        if not path.exists():
            errors.append(f"missing_file:{path.relative_to(root)}")

    if errors:
        return {"valid": False, "errors": errors}

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

    return {
        "version": "V104-CLOUDWORKSPACE-SOVEREIGN-1",
        "valid": not errors,
        "errors": errors,
        "artifacts": [
            str(deployment.relative_to(root)),
            str(standards.relative_to(root)),
            str(openapi.relative_to(root)),
            str(ledger.relative_to(root)),
        ],
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
