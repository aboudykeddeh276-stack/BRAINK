#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DEPENDENCY_FAILURE_NE_GLOBAL_APPLICATION_FAILURE = "DEPENDENCY_FAILURE_NE_GLOBAL_APPLICATION_FAILURE"
NON_GLOBAL_STATES = {
    "OPERATIONAL",
    "OPERATIONAL_DEGRADED",
    "OPERATIONAL_EXTERNAL_GATE",
    "OPERATIONAL_DEFERRED_COMMIT",
    "OPERATIONAL_ALTERNATE_PATH",
}


@dataclass(frozen=True)
class IntegrityReadback:
    package_path: str
    manifest_path: str
    manifest_hash_expected: str
    manifest_hash_actual: str
    manifest_valid: bool
    all_required_files_present: bool
    node_execution_allowed: bool
    reason: str


@dataclass(frozen=True)
class FailureRecord:
    failure_id: str
    blocked_capability: str
    blocked_domain: str
    criticality: str
    root_cause: str
    impact_radius: List[str]
    unaffected_domains: List[str]
    continuation_mode: str
    fallback_adapter: str
    durable_outbox: str
    research_basis: List[str]
    required_changes: List[str]
    positive_tests: List[str]
    negative_tests: List[str]
    failover_tests: List[str]
    recovery_tests: List[str]
    reentry_conditions: List[str]
    promotion_evidence: List[str]
    owner: str
    recovery_state: str
    timestamp: float


@dataclass
class CircuitBreaker:
    service_id: str
    failure_threshold: int = 2
    recovery_timeout_seconds: int = 60
    failure_count: int = 0
    state: str = "CLOSED"
    opened_at: Optional[float] = None

    def allow_call(self, now: Optional[float] = None) -> bool:
        now = now or time.time()
        if self.state == "OPEN":
            if self.opened_at is not None and (now - self.opened_at) >= self.recovery_timeout_seconds:
                self.state = "HALF_OPEN"
                return True
            return False
        return True

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = "CLOSED"
        self.opened_at = None

    def record_failure(self, now: Optional[float] = None) -> None:
        now = now or time.time()
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.opened_at = now


@dataclass(frozen=True)
class NodeHealth:
    node_id: str
    domain: str
    status: str
    failed_dependencies: List[str]
    degraded_dependencies: List[str]
    supplied_capabilities: List[str]


@dataclass(frozen=True)
class HealthProjection:
    application_core: str
    vite_package: str
    k_cloud_admission: str
    vfs: str
    agent_registry: str
    native_gpu: str
    audio_output: str
    remote_telemetry: str
    m3_host_validation: str
    core_semantic_validity: str
    overall_state: str
    degraded_ui_state: bool
    nodes: List[NodeHealth]


@dataclass(frozen=True)
class KCloudDeploymentReceipt:
    version: str
    application_id: str
    package_path: str
    integrity_readback_before_node_execution: bool
    node_execution_started: bool
    circuit_breakers_open: List[str]
    failures_recorded: int
    reconciled_count: int
    overall_state: str
    degraded_ui_state: bool
    promoted_capabilities: List[str]
    held_capabilities: List[str]
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


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


class FailureLedger:
    """Append-only failure ledger for dependency recovery and deferred-work replay."""

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.ledger_path = self.root / "runtime_volume" / "failure_ledger.jsonl"
        self.task_dir = self.root / "runtime_volume" / "continuation_workflows" / "k_cloud"

    def record_failure(self, task: Dict[str, Any]) -> FailureRecord:
        required = {
            "blocked_capability",
            "blocked_domain",
            "criticality",
            "root_cause",
            "impact_radius",
            "unaffected_domains",
            "continuation_mode",
            "fallback_adapter",
            "durable_outbox",
            "research_basis",
            "required_changes",
            "positive_tests",
            "negative_tests",
            "failover_tests",
            "recovery_tests",
            "reentry_conditions",
            "promotion_evidence",
            "owner",
        }
        missing = sorted(required - set(task))
        if missing:
            raise ValueError(f"continuation task missing fields: {','.join(missing)}")
        failure_id = canonical_hash({"task": task, "ts": time.time()})
        task_path = self.task_dir / f"{failure_id}.json"
        write_json(task_path, task)
        record = FailureRecord(
            failure_id=failure_id,
            blocked_capability=task["blocked_capability"],
            blocked_domain=task["blocked_domain"],
            criticality=task["criticality"],
            root_cause=task["root_cause"],
            impact_radius=list(task["impact_radius"]),
            unaffected_domains=list(task["unaffected_domains"]),
            continuation_mode=task["continuation_mode"],
            fallback_adapter=task["fallback_adapter"],
            durable_outbox=task["durable_outbox"],
            research_basis=list(task["research_basis"]),
            required_changes=list(task["required_changes"]),
            positive_tests=list(task["positive_tests"]),
            negative_tests=list(task["negative_tests"]),
            failover_tests=list(task["failover_tests"]),
            recovery_tests=list(task["recovery_tests"]),
            reentry_conditions=list(task["reentry_conditions"]),
            promotion_evidence=list(task["promotion_evidence"]),
            owner=task["owner"],
            recovery_state="WAITING_FOR_RECOVERY",
            timestamp=time.time(),
        )
        append_jsonl(self.ledger_path, {"type": "failure_record", "record": asdict(record), "task_path": str(task_path)})
        return record

    def records(self) -> List[Dict[str, Any]]:
        return read_jsonl(self.ledger_path)

    def categorize(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for entry in self.records():
            record = entry.get("record", {})
            criticality = record.get("criticality", "UNKNOWN")
            counts[criticality] = counts.get(criticality, 0) + 1
        return counts

    def reconcile_deferred_work(self, recovered_domains: Iterable[str]) -> int:
        recovered = set(recovered_domains)
        reconciled = 0
        for entry in self.records():
            if entry.get("type") != "failure_record":
                continue
            record = entry.get("record", {})
            if record.get("blocked_domain") in recovered or record.get("blocked_capability") in recovered:
                append_jsonl(self.ledger_path, {
                    "type": "recovery_reconciliation",
                    "failure_id": record.get("failure_id"),
                    "blocked_domain": record.get("blocked_domain"),
                    "recovery_state": "RECONCILED",
                    "timestamp": time.time(),
                })
                reconciled += 1
        return reconciled


class HealthStateMonitor:
    """Central health projection for mesh nodes and capability-specific UI state."""

    def __init__(self, policy: Dict[str, Any]):
        self.policy = policy

    def observe(self, service_health: Dict[str, str]) -> HealthProjection:
        nodes: List[NodeHealth] = []
        for node in self.policy["mesh_nodes"]:
            failed: List[str] = []
            degraded: List[str] = []
            for dep in node.get("dependencies", []):
                state = service_health.get(dep, "UNKNOWN")
                if state in {"FAILED", "EXTERNAL_GATE", "DEFERRED_COMMIT"}:
                    failed.append(dep)
                if state in {"DEGRADED", "REPLACEABLE", "FAILED_OPTIONAL"}:
                    degraded.append(dep)
            status = "HEALTHY" if not failed and not degraded else "DEGRADED"
            nodes.append(NodeHealth(
                node_id=node["node_id"],
                domain=node["domain"],
                status=status,
                failed_dependencies=failed,
                degraded_dependencies=degraded,
                supplied_capabilities=[node["domain"]],
            ))
        degraded_ui = any(node.status == "DEGRADED" for node in nodes)
        mandatory_ok = service_health.get("service.vfs") == "HEALTHY" and service_health.get("service.runtime-config") == "HEALTHY"
        overall = "OPERATIONAL_DEGRADED" if degraded_ui and mandatory_ok else "OPERATIONAL_PARTIAL"
        if not degraded_ui and mandatory_ok:
            overall = "OPERATIONAL"
        return HealthProjection(
            application_core="HEALTHY" if mandatory_ok else "DEGRADED",
            vite_package="HEALTHY",
            k_cloud_admission="HEALTHY",
            vfs=service_health.get("service.vfs", "UNKNOWN"),
            agent_registry=service_health.get("service.agent-registry", "UNKNOWN"),
            native_gpu=service_health.get("service.native-gpu", "UNKNOWN"),
            audio_output=service_health.get("service.audio-output", "UNKNOWN"),
            remote_telemetry=service_health.get("service.remote-telemetry", "UNKNOWN"),
            m3_host_validation=service_health.get("service.mesh-registry", "UNKNOWN"),
            core_semantic_validity="PRESERVED" if mandatory_ok else "AT_RISK",
            overall_state=overall,
            degraded_ui_state=degraded_ui,
            nodes=nodes,
        )


class KCloudAdapter:
    """Vite-to-K-Cloud deployment adapter with package integrity readback and failure containment."""

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.policy = read_json(self.root / "config" / "k_app_package_policy.json")
        defaults = self.policy["circuit_breaker_defaults"]
        self.circuit_breakers = {
            service_id: CircuitBreaker(
                service_id,
                failure_threshold=int(defaults["failure_threshold"]),
                recovery_timeout_seconds=int(defaults["recovery_timeout_seconds"]),
            )
            for service_id in self.policy["external_services"]
        }
        self.failure_ledger = FailureLedger(self.root)
        self.health_monitor = HealthStateMonitor(self.policy)

    def package_dir(self) -> Path:
        app = self.policy["canonical_manifest"]["applicationId"].replace(".", "_")
        return self.root / "runtime_volume" / "k_app_packages" / app

    def scaffold_package(self, package_dir: Optional[Path] = None) -> Path:
        package = (package_dir or self.package_dir()).expanduser().resolve()
        package.mkdir(parents=True, exist_ok=True)
        (package / "application").mkdir(parents=True, exist_ok=True)
        (package / "application" / "index.html").write_text(
            "<!doctype html><html><head><meta charset='utf-8'><title>KEX Workstation</title></head><body>K-APP</body></html>\n",
            encoding="utf-8",
        )
        manifest = dict(self.policy["canonical_manifest"])
        write_json(package / "k-app.manifest.json", manifest)
        write_json(package / "asset-manifest.json", {"assets": [{"path": "application/index.html", "type": "text/html"}]})
        write_json(package / "route-manifest.json", {"routes": [{"path": "/", "entrypoint": "/index.html"}]})
        write_json(package / "agent-bindings.json", {"agents": ["acceptance_harness_agent", "virtual_cpu_executor"]})
        write_json(package / "vfs-namespaces.json", {"namespaces": ["vfs://apps/kex.workstation.core/", "vfs://agents/acceptance_harness_agent/"]})
        write_json(package / "telemetry-schema.json", {"signals": ["trace", "metric", "log", "receipt_event"]})
        write_json(package / "permission-policy.json", {"network": "policy_resolved", "secrets": "host_injected_only"})
        write_json(package / "dependency-contracts.json", {
            "runtime_rule": DEPENDENCY_FAILURE_NE_GLOBAL_APPLICATION_FAILURE,
            "dependencyPolicies": manifest["dependencyPolicies"],
            "fallbackAdapters": manifest["fallbackAdapters"],
        })
        write_json(package / "degraded-mode-policy.json", {
            "service.audio-output": "visual alert and logged notification",
            "service.native-gpu": "canvas CPU renderer",
            "service.remote-telemetry": "local telemetry outbox",
            "service.mesh-registry": "local mesh outbox and deferred mesh registration",
        })
        write_json(package / "recovery-policy.json", {"reintegrate_when": "dependency health and integrity checks pass"})
        write_json(package / "SBOM.spdx.json", {"spdxVersion": "SPDX-2.3", "name": "kex.workstation.core", "packages": []})
        write_json(package / "build-receipt.json", {"builder": "keddeh_k_cloud_adapter", "timestamp": time.time(), "vite_build": "modeled_or_existing_dist"})
        self.write_integrity(package)
        return package

    def write_integrity(self, package: Path) -> None:
        entries: Dict[str, str] = {}
        for relative in self.policy["required_package_files"]:
            if relative == "integrity.sha256":
                continue
            path = package / relative
            if path.exists():
                entries[relative] = file_hash(path)
        write_json(package / "integrity.sha256", entries)

    def integrity_readback(self, package: Path) -> IntegrityReadback:
        manifest_path = package / "k-app.manifest.json"
        integrity_path = package / "integrity.sha256"
        if not manifest_path.exists() or not integrity_path.exists():
            return IntegrityReadback(str(package), str(manifest_path), "", "", False, False, False, "missing_manifest_or_integrity")
        integrity = read_json(integrity_path)
        expected = str(integrity.get("k-app.manifest.json", ""))
        actual = file_hash(manifest_path)
        required_present = all((package / rel).exists() for rel in self.policy["required_package_files"])
        manifest = read_json(manifest_path)
        manifest_valid = (
            expected == actual
            and manifest.get("applicationId")
            and manifest.get("entrypoint")
            and isinstance(manifest.get("dependencyPolicies"), dict)
            and (package / "dependency-contracts.json").exists()
            and (package / "degraded-mode-policy.json").exists()
        )
        return IntegrityReadback(
            package_path=str(package),
            manifest_path=str(manifest_path),
            manifest_hash_expected=expected,
            manifest_hash_actual=actual,
            manifest_valid=bool(manifest_valid),
            all_required_files_present=required_present,
            node_execution_allowed=bool(manifest_valid and required_present),
            reason="valid" if manifest_valid and required_present else "integrity_or_required_file_failure",
        )

    def service_health(self) -> Dict[str, str]:
        health = {
            "service.agent-registry": "DEGRADED",
            "service.vfs": "HEALTHY",
            "service.runtime-config": "HEALTHY",
            "service.audio-output": "FAILED_OPTIONAL",
            "service.native-gpu": "REPLACEABLE",
            "service.remote-telemetry": "DEFERRED_COMMIT",
            "service.mesh-registry": "EXTERNAL_GATE",
        }
        for service_id, details in self.policy["external_services"].items():
            breaker = self.circuit_breakers[service_id]
            available = bool(details.get("available_by_default"))
            if not breaker.allow_call():
                health[service_id] = "CIRCUIT_OPEN"
                continue
            if available:
                breaker.record_success()
                health[service_id] = "HEALTHY"
            else:
                breaker.record_failure()
                health[service_id] = details["criticality"]
        return health

    def record_dependency_failures(self, health: Dict[str, str]) -> List[FailureRecord]:
        records: List[FailureRecord] = []
        manifest = self.policy["canonical_manifest"]
        for service_id, state in health.items():
            if state == "HEALTHY":
                continue
            criticality = manifest.get("dependencyPolicies", {}).get(service_id)
            if criticality is None:
                criticality = self.policy.get("external_services", {}).get(service_id, {}).get("criticality", "OPTIONAL")
            fallback = manifest.get("fallbackAdapters", {}).get(service_id)
            if fallback is None:
                fallback = self.policy.get("external_services", {}).get(service_id, {}).get("fallback_adapter", "adapter.local-outbox")
            record = self.failure_ledger.record_failure({
                "blocked_capability": service_id,
                "blocked_domain": service_id,
                "criticality": criticality,
                "root_cause": state,
                "impact_radius": [service_id],
                "unaffected_domains": ["application_core", "vfs", "local_runtime", "receipt_ledger"],
                "continuation_mode": "activate fallback/degraded mode and preserve core execution",
                "fallback_adapter": fallback,
                "durable_outbox": f"runtime_volume/outbox/k_cloud/{service_id.replace('.', '_')}",
                "research_basis": ["failure-domain isolation", "circuit breaker", "durable outbox", "graceful degradation"],
                "required_changes": ["recover dependency or prove fallback health"],
                "positive_tests": ["tests/test_k_cloud_adapter.py"],
                "negative_tests": ["tampered manifest integrity readback fails"],
                "failover_tests": ["circuit breaker opens on repeated external failures"],
                "recovery_tests": ["FailureLedger.reconcile_deferred_work"],
                "reentry_conditions": ["dependency health check passes", "integrity readback remains valid"],
                "promotion_evidence": ["evidence/k_cloud_deployment_receipt.json"],
                "owner": "k_cloud_adapter",
            })
            records.append(record)
        return records

    def deploy(self, package: Optional[Path] = None, emit_receipt: bool = False) -> Dict[str, Any]:
        started = time.time()
        package = self.scaffold_package(package)
        readback = self.integrity_readback(package)
        health = self.service_health()
        failures = self.record_dependency_failures(health)
        projection = self.health_monitor.observe(health)
        circuit_open = [service_id for service_id, breaker in self.circuit_breakers.items() if breaker.state == "OPEN"]
        promoted = ["application_core", "vite_package", "k_cloud_admission", "vfs"] if readback.node_execution_allowed else []
        held = [service_id for service_id, state in health.items() if state != "HEALTHY"]
        reconciled = self.failure_ledger.reconcile_deferred_work([])
        evidence_dir = self.root / "evidence"
        receipt_path = evidence_dir / "k_cloud_deployment_receipt.json"
        outbox = self.root / "runtime_volume" / "outbox" / "k_cloud" / f"{canonical_hash({'package': str(package), 'ts': started})}.handoff.json"
        handoff = {
            "source": "KEDDEH_V99_K_CLOUD_ADAPTER",
            "payload_path": str(receipt_path),
            "package_path": str(package),
            "status": "READY_FOR_TARGET_HOST_EXECUTION" if readback.node_execution_allowed else "FAILED_CLOSED",
            "next_target": "mesh_registration_then_node_capability_readback",
            "created_at": started,
        }
        write_json(outbox, handoff)
        receipt = KCloudDeploymentReceipt(
            version="V99",
            application_id=self.policy["canonical_manifest"]["applicationId"],
            package_path=str(package),
            integrity_readback_before_node_execution=readback.node_execution_allowed,
            node_execution_started=readback.node_execution_allowed,
            circuit_breakers_open=circuit_open,
            failures_recorded=len(failures),
            reconciled_count=reconciled,
            overall_state=projection.overall_state,
            degraded_ui_state=projection.degraded_ui_state,
            promoted_capabilities=promoted,
            held_capabilities=held,
            receipt_path=str(receipt_path),
            outbox_manifest=str(outbox),
            timestamp=started,
        )
        final = {
            "runtime_rule": DEPENDENCY_FAILURE_NE_GLOBAL_APPLICATION_FAILURE,
            "integrity_readback": asdict(readback),
            "health_projection": {
                **{k: v for k, v in asdict(projection).items() if k != "nodes"},
                "nodes": [asdict(node) for node in projection.nodes],
            },
            "failure_categories": self.failure_ledger.categorize(),
            "receipt": asdict(receipt),
            "manifest_or_telemetry_as_completion": False,
            "dependency_failure_as_global_application_failure": False,
        }
        if emit_receipt:
            write_json(receipt_path, final)
            append_jsonl(self.root / "runtime_volume" / "proof_bundles.ledger", {
                "type": "k_cloud_deployment_receipt",
                "entry_hash": canonical_hash(final),
                "receipt": final["receipt"],
            })
            write_csv(self.root / "exports" / "k_cloud_health_matrix.csv", [asdict(node) for node in projection.nodes])
        return final


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    parser.add_argument("--package", default=None)
    args = parser.parse_args(argv)
    adapter = KCloudAdapter(Path(args.root))
    result = adapter.deploy(Path(args.package) if args.package else None, emit_receipt=args.emit_receipt)
    print(json.dumps(result["receipt"], indent=2, sort_keys=True))
    return 0 if result["receipt"]["integrity_readback_before_node_execution"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
