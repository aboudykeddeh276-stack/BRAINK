#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

DEPENDENCY_FAILURE_NE_GLOBAL_APPLICATION_FAILURE = "DEPENDENCY_FAILURE_NE_GLOBAL_APPLICATION_FAILURE"


@dataclass(frozen=True)
class AppletAssessment:
    component_id: str
    component_type: str
    package_path: str
    manifest_path: str
    integrity_readback_before_node_execution: bool
    runtime_contract_complete: bool
    k_app_files_complete: bool
    shipping_state: str
    target_gate_state: str
    overall_runtime_state: str
    capabilities: str
    fallback_adapter: str
    reason: str


@dataclass(frozen=True)
class ApplicationAppletShippingReceipt:
    version: str
    assessed_components: int
    local_shippable_components: int
    target_host_required_components: int
    provider_required_components: int
    integrity_failures: int
    missing_contracts: int
    package_root: str
    catalog_path: str
    receipt_path: str
    outbox_manifest: str
    timestamp: float


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def write_csv(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def slug(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return clean or "component"


def package_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower() or "component"


def load_registry(root: Path) -> Dict[str, Any]:
    return read_json(root / "config" / "application_applet_registry.json")


def load_services(root: Path) -> List[Dict[str, Any]]:
    return read_json(root / "config" / "service_protocols.json")["services"]


class ApplicationAppletPackager:
    """Assess every local service as a shippable application/applet package.

    This class does not call a remote mesh and does not claim remote provider health. It
    creates concrete local K-APP packages with browser-openable application surfaces,
    required policy files, manifest integrity, receipt output, ledger write and outbox
    handoff. Target-host and provider claims stay as gates.
    """

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.registry = load_registry(self.root)
        self.service_protocols = load_services(self.root)
        self.package_root = self.root / "runtime_volume" / "k_app_packages" / "application_applet_shipping"
        self.catalog_root = self.root / "runtime_volume" / "application_catalog"
        self.evidence_dir = self.root / "evidence"
        self.exports_dir = self.root / "exports"
        self.outbox_dir = self.root / "runtime_volume" / "outbox" / "application_applet_shipping"
        self.ledger_path = self.root / "runtime_volume" / "proof_bundles.ledger"

    def component_specs(self) -> List[Dict[str, Any]]:
        specs: List[Dict[str, Any]] = []
        for app in self.registry.get("primary_applications", []):
            specs.append({
                "component_id": app["component_id"],
                "component_type": app.get("component_type", "APPLICATION"),
                "owner_plane": "application_plane",
                "boundary": "root browser application shell",
                "supplied_capabilities": app.get("supplied_capabilities", []),
                "criticality": app.get("criticality", "CORE_MANDATORY"),
                "fallback_adapter": app.get("fallback_adapter", "adapter.static-local-launcher"),
                "source_surface": app.get("source_surface", "vite_or_static_browser_surface"),
            })
        overrides = self.registry.get("component_type_overrides", {})
        for service in self.service_protocols:
            service_id = service["service_id"]
            specs.append({
                "component_id": service_id,
                "component_type": overrides.get(service_id, "APPLET"),
                "owner_plane": service.get("owner_plane", "virtual_cpu"),
                "boundary": service.get("boundary", "local service boundary"),
                "supplied_capabilities": [service_id, service.get("owner_plane", "virtual_cpu")],
                "criticality": self.criticality_for(service_id),
                "fallback_adapter": self.fallback_for(service_id),
                "source_surface": "service_protocol_runtime_surface",
            })
        return specs

    def criticality_for(self, service_id: str) -> str:
        if service_id in {"vfs_volume_custody", "k_cloud_adapter"}:
            return "CORE_MANDATORY"
        if service_id in {"virtual_gpu_hci_dashboard"}:
            return "REPLACEABLE"
        if service_id in {"failure_ledger", "health_state_monitor", "dependency_failure_orchestrator"}:
            return "CORE_DEGRADED"
        if service_id in {"peer_ack_verifier"}:
            return "EXTERNAL_GATE"
        return self.registry.get("default_dependency_policy", "CORE_DEGRADED")

    def fallback_for(self, service_id: str) -> str:
        if service_id == "virtual_gpu_hci_dashboard":
            return "adapter.canvas-cpu-renderer"
        if service_id == "peer_ack_verifier":
            return "adapter.local-peer-ack-outbox"
        if service_id == "btc_core_protocol_router":
            return "adapter.read-only-local-p2p-framer"
        return "adapter.local-static-applet"

    def runtime_contract(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        service_identity = f"service.{slug(spec['component_id'])}"
        return {
            "identity": spec["component_id"],
            "suppliedCapabilities": list(spec.get("supplied_capabilities", [])),
            "startupDependencies": list(self.registry.get("default_required_services", [])),
            "runtimeDependencies": [service_identity],
            "optionalDependencies": list(self.registry.get("default_optional_services", [])),
            "criticalityClass": spec.get("criticality", "CORE_DEGRADED"),
            "fallbackAdapter": spec.get("fallback_adapter", "adapter.local-static-applet"),
            "degradedModeBehaviour": "preserve core runtime and expose degraded capability state",
            "queueOutboxPolicy": f"runtime_volume/outbox/application_applet_shipping/{package_id(spec['component_id'])}",
            "circuitBreakerLimits": {"failureThreshold": 2, "recoveryTimeoutSeconds": 60},
            "rollbackContract": "retain previous package directory until new package receipt and integrity readback pass",
            "recoveryConditions": ["dependency health check passes", "manifest integrity readback passes", "node capability readback passes"],
            "reintegrationTests": ["tests/test_application_applet_packager.py", "tests/test_k_cloud_adapter.py"],
        }

    def manifest_for(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        contract = self.runtime_contract(spec)
        required_services = list(self.registry.get("default_required_services", []))
        optional_services = list(self.registry.get("default_optional_services", []))
        dependency_policies = {service: "CORE_MANDATORY" for service in required_services}
        dependency_policies.update({service: "OPTIONAL" for service in optional_services})
        dependency_policies[f"service.{slug(spec['component_id'])}"] = contract["criticalityClass"]
        fallback_adapters = dict(self.registry.get("default_fallback_adapters", {}))
        fallback_adapters[f"service.{slug(spec['component_id'])}"] = contract["fallbackAdapter"]
        manifest = {
            "applicationId": f"kex.{slug(spec['component_id']).replace('-', '.')}",
            "componentId": spec["component_id"],
            "componentType": spec["component_type"],
            "version": "1.0.0",
            "entrypoint": "/index.html",
            "runtime": "BROWSER_ESM",
            "deploymentMode": "MESH_REPLICATED",
            "requiredServices": required_services,
            "optionalServices": optional_services,
            "dependencyPolicies": dependency_policies,
            "fallbackAdapters": fallback_adapters,
            "targetGates": list(self.registry.get("target_gates", [])),
            "runtimeIndependenceContract": contract,
            "sourceSurface": spec.get("source_surface", "unknown"),
            "ownerPlane": spec.get("owner_plane", "unknown"),
            "boundary": spec.get("boundary", "unknown"),
            "canonicalRuntimeRule": DEPENDENCY_FAILURE_NE_GLOBAL_APPLICATION_FAILURE,
        }
        return manifest

    def application_html(self, spec: Dict[str, Any], manifest: Dict[str, Any]) -> str:
        title = html.escape(spec["component_id"])
        component_type = html.escape(spec["component_type"])
        state = "LOCAL_SHIPPABLE_K_APP"
        capabilities = ", ".join(html.escape(str(cap)) for cap in manifest["runtimeIndependenceContract"]["suppliedCapabilities"])
        return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{title} — K-APP</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2rem; max-width: 980px; }}
    .card {{ border: 1px solid #bbb; border-radius: 14px; padding: 1rem; margin: 1rem 0; }}
    code {{ background: #f2f2f2; padding: .15rem .3rem; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p><strong>Component type:</strong> {component_type}</p>
  <p><strong>Shipping state:</strong> {state}</p>
  <div class=\"card\">
    <h2>Runtime independence contract</h2>
    <p><strong>Canonical rule:</strong> <code>Dependency failure != global application failure</code></p>
    <p><strong>Capabilities:</strong> {capabilities}</p>
    <p><strong>Fallback adapter:</strong> {html.escape(manifest['runtimeIndependenceContract']['fallbackAdapter'])}</p>
    <p><strong>Outbox:</strong> <code>{html.escape(manifest['runtimeIndependenceContract']['queueOutboxPolicy'])}</code></p>
  </div>
  <div class=\"card\">
    <h2>Readback requirement</h2>
    <p>Node-side execution is permitted only after <code>k-app.manifest.json</code> matches <code>integrity.sha256</code> and all K-APP files are present.</p>
  </div>
</body>
</html>
"""

    def write_package(self, spec: Dict[str, Any]) -> Path:
        package = self.package_root / package_id(spec["component_id"])
        package.mkdir(parents=True, exist_ok=True)
        (package / "application").mkdir(exist_ok=True)
        manifest = self.manifest_for(spec)
        (package / "application" / "index.html").write_text(self.application_html(spec, manifest), encoding="utf-8")
        write_json(package / "k-app.manifest.json", manifest)
        write_json(package / "asset-manifest.json", {"assets": [{"path": "application/index.html", "type": "text/html"}]})
        write_json(package / "route-manifest.json", {"routes": [{"path": "/", "entrypoint": "/index.html"}]})
        write_json(package / "agent-bindings.json", {"agents": ["acceptance_harness_agent", "virtual_cpu_executor"], "component": spec["component_id"]})
        write_json(package / "vfs-namespaces.json", {"namespaces": [f"vfs://apps/{slug(spec['component_id'])}/", f"vfs://agents/{slug(spec['component_id'])}/receipts/"]})
        write_json(package / "telemetry-schema.json", {"signals": ["receipt_event", "health_state", "capability_readback"], "telemetry_is_not_proof": True})
        write_json(package / "permission-policy.json", {"network": "policy_resolved", "secrets": "host_injected_only", "filesystem": "vfs_namespace_only"})
        write_json(package / "dependency-contracts.json", manifest["runtimeIndependenceContract"])
        write_json(package / "degraded-mode-policy.json", {"canonicalRule": DEPENDENCY_FAILURE_NE_GLOBAL_APPLICATION_FAILURE, "fallbackAdapters": manifest["fallbackAdapters"]})
        write_json(package / "recovery-policy.json", {"rollback": manifest["runtimeIndependenceContract"]["rollbackContract"], "recoveryConditions": manifest["runtimeIndependenceContract"]["recoveryConditions"]})
        write_json(package / "SBOM.spdx.json", {"spdxVersion": "SPDX-2.3", "name": spec["component_id"], "packages": [{"name": spec["component_id"], "versionInfo": "1.0.0"}]})
        write_json(package / "build-receipt.json", {"builder": "keddeh_application_applet_packager", "component_id": spec["component_id"], "timestamp": time.time(), "source_surface": spec.get("source_surface")})
        self.write_integrity(package)
        return package

    def write_integrity(self, package: Path) -> None:
        entries: Dict[str, str] = {}
        for relative in self.registry["required_k_app_files"]:
            if relative == "integrity.sha256":
                continue
            path = package / relative
            if path.exists():
                entries[relative] = file_hash(path)
        write_json(package / "integrity.sha256", entries)

    def integrity_readback(self, package: Path) -> Tuple[bool, str]:
        manifest = package / "k-app.manifest.json"
        integrity = package / "integrity.sha256"
        if not manifest.exists() or not integrity.exists():
            return False, "missing_manifest_or_integrity"
        hashes = read_json(integrity)
        expected = hashes.get("k-app.manifest.json")
        actual = file_hash(manifest)
        required_ok = all((package / rel).exists() for rel in self.registry["required_k_app_files"])
        contract_ok = self.runtime_contract_complete(read_json(manifest))
        if expected != actual:
            return False, "manifest_integrity_mismatch"
        if not required_ok:
            return False, "missing_required_k_app_files"
        if not contract_ok:
            return False, "missing_runtime_independence_contract"
        return True, "integrity_readback_passed"

    def runtime_contract_complete(self, manifest: Dict[str, Any]) -> bool:
        contract = manifest.get("runtimeIndependenceContract", {})
        return all(field in contract and contract[field] not in (None, "", []) for field in self.registry["required_runtime_contract_fields"])

    def assess_one(self, spec: Dict[str, Any]) -> AppletAssessment:
        package = self.write_package(spec)
        manifest_path = package / "k-app.manifest.json"
        readback, reason = self.integrity_readback(package)
        manifest = read_json(manifest_path)
        contract_complete = self.runtime_contract_complete(manifest)
        files_complete = all((package / rel).exists() for rel in self.registry["required_k_app_files"])
        if not contract_complete:
            shipping_state = "NOT_SHIPPABLE_MISSING_CONTRACT"
        elif not readback:
            shipping_state = "NOT_SHIPPABLE_INTEGRITY_FAILURE"
        else:
            shipping_state = "LOCAL_SHIPPABLE_K_APP"
        target_gate_state = "TARGET_HOST_REQUIRED" if manifest.get("targetGates") else "LOCAL_ONLY"
        overall = "OPERATIONAL_DEGRADED" if shipping_state == "LOCAL_SHIPPABLE_K_APP" and target_gate_state == "TARGET_HOST_REQUIRED" else shipping_state
        return AppletAssessment(
            component_id=spec["component_id"],
            component_type=spec["component_type"],
            package_path=str(package),
            manifest_path=str(manifest_path),
            integrity_readback_before_node_execution=readback,
            runtime_contract_complete=contract_complete,
            k_app_files_complete=files_complete,
            shipping_state=shipping_state,
            target_gate_state=target_gate_state,
            overall_runtime_state=overall,
            capabilities=";".join(manifest["runtimeIndependenceContract"].get("suppliedCapabilities", [])),
            fallback_adapter=manifest["runtimeIndependenceContract"].get("fallbackAdapter", ""),
            reason=reason,
        )

    def write_catalog(self, rows: List[AppletAssessment]) -> Path:
        self.catalog_root.mkdir(parents=True, exist_ok=True)
        items = []
        for row in rows:
            rel = Path(row.package_path) / "application" / "index.html"
            items.append(f"<li><a href='{html.escape(str(rel))}'>{html.escape(row.component_id)}</a> — {html.escape(row.component_type)} — {html.escape(row.shipping_state)}</li>")
        body = "\n".join(items)
        html_doc = f"""<!doctype html><html><head><meta charset='utf-8'><title>KEDDEH Application Catalog</title></head><body><h1>KEDDEH Application/Applet Catalog</h1><p>Every listed item has a K-APP package and manifest integrity readback receipt. Target-host/provider gates remain explicit.</p><ul>{body}</ul></body></html>\n"""
        path = self.catalog_root / "index.html"
        path.write_text(html_doc, encoding="utf-8")
        return path

    def run(self, emit_receipt: bool = False) -> Dict[str, Any]:
        started = time.time()
        rows = [self.assess_one(spec) for spec in self.component_specs()]
        catalog = self.write_catalog(rows)
        csv_path = self.exports_dir / "application_applet_shipping_matrix.csv"
        write_csv(csv_path, [asdict(row) for row in rows])
        local_shippable = sum(1 for row in rows if row.shipping_state == "LOCAL_SHIPPABLE_K_APP")
        target_required = sum(1 for row in rows if row.target_gate_state == "TARGET_HOST_REQUIRED")
        provider_required = 0
        integrity_failures = sum(1 for row in rows if row.shipping_state == "NOT_SHIPPABLE_INTEGRITY_FAILURE")
        missing_contracts = sum(1 for row in rows if row.shipping_state == "NOT_SHIPPABLE_MISSING_CONTRACT")
        receipt_path = self.evidence_dir / "application_applet_shipping_receipt.json"
        outbox = self.outbox_dir / f"{canonical_hash({'catalog': str(catalog), 'ts': started})}.handoff.json"
        receipt = ApplicationAppletShippingReceipt(
            version="V99",
            assessed_components=len(rows),
            local_shippable_components=local_shippable,
            target_host_required_components=target_required,
            provider_required_components=provider_required,
            integrity_failures=integrity_failures,
            missing_contracts=missing_contracts,
            package_root=str(self.package_root),
            catalog_path=str(catalog),
            receipt_path=str(receipt_path),
            outbox_manifest=str(outbox),
            timestamp=started,
        )
        final = {
            "runtime_rule": DEPENDENCY_FAILURE_NE_GLOBAL_APPLICATION_FAILURE,
            "receipt": asdict(receipt),
            "assessments": [asdict(row) for row in rows],
            "all_modules_assessed_as_packages": True,
            "simulation_used_as_shipping_proof": False,
            "telemetry_used_as_shipping_proof": False,
            "global_failure_from_dependency_failure": False,
        }
        handoff = {
            "source": "KEDDEH_V99_APPLICATION_APPLET_PACKAGER",
            "payload_path": str(receipt_path),
            "package_root": str(self.package_root),
            "catalog_path": str(catalog),
            "status": "LOCAL_SHIPPABLE_WITH_TARGET_GATES" if integrity_failures == 0 and missing_contracts == 0 else "FAILED_CLOSED",
            "next_target": "k_cloud_admission_then_mesh_node_readback",
            "created_at": started,
        }
        if emit_receipt:
            write_json(receipt_path, final)
            write_json(outbox, handoff)
            append_jsonl(self.ledger_path, {"type": "application_applet_shipping", "receipt": asdict(receipt)})
        return final


def run_application_applet_shipping(root: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    return ApplicationAppletPackager(root).run(emit_receipt=emit_receipt)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    result = run_application_applet_shipping(Path(args.root), emit_receipt=args.emit_receipt)
    print(json.dumps(result["receipt"], indent=2, sort_keys=True))
    ok = result["receipt"]["integrity_failures"] == 0 and result["receipt"]["missing_contracts"] == 0
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
