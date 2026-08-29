#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

CANONICAL_RUNTIME_RULE = "DEPENDENCY_FAILURE_NE_GLOBAL_APPLICATION_FAILURE"


@dataclass(frozen=True)
class MaturityRow:
    component_id: str
    component_type: str
    owner_plane: str
    issue_code: str
    maturity_state: str
    corrective_workflow: str
    pending_workload: str
    action_command: str
    required_receipts: str
    dependency_class: str
    fallback_path: str
    reentry_condition: str
    promotion_boundary: str


@dataclass(frozen=True)
class DeploymentMaturityReceipt:
    version: str
    assessed_components: int
    local_shippable: int
    local_repair_required: int
    target_host_required: int
    provider_required: int
    workplan_packets_written: int
    ledger_readback: bool
    receipt_path: str
    matrix_path: str
    outbox_manifest: str
    timestamp: float


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def load_config(root: Path) -> Dict[str, Any]:
    return read_json(root / "config" / "deployment_maturity_workplan.json")


def load_services(root: Path) -> List[Dict[str, Any]]:
    return read_json(root / "config" / "service_protocols.json")["services"]


def package_name(service_id: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in service_id).strip("_").lower()


class DeploymentMaturityWorkplan:
    """Actionable maturity assessment for KEDDEH modules and K-APP deployment lanes.

    The workplan does not promote remote, target-host, provider or certification claims.
    It creates executable work packets and declares the next command/receipt needed for each
    module. Dependency failure is handled as a capability/domain condition, not a global app
    failure, unless an invariant violation is proven elsewhere.
    """

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.config = load_config(self.root)
        self.services = load_services(self.root)
        self.package_root = self.root / "runtime_volume" / "k_app_packages" / "application_applet_shipping"
        self.evidence_dir = self.root / "evidence"
        self.exports_dir = self.root / "exports"
        self.workplan_dir = self.root / "runtime_volume" / "workplans" / "deployment_maturity"
        self.outbox_dir = self.root / "runtime_volume" / "outbox" / "deployment_maturity_workplan"
        self.ledger_path = self.root / "runtime_volume" / "proof_bundles.ledger"

    def package_exists(self, service_id: str) -> bool:
        package = self.package_root / package_name(service_id)
        required = [
            "application/index.html",
            "k-app.manifest.json",
            "dependency-contracts.json",
            "degraded-mode-policy.json",
            "recovery-policy.json",
            "SBOM.spdx.json",
            "build-receipt.json",
            "integrity.sha256",
        ]
        return all((package / relative).exists() for relative in required)

    def receipt_exists(self, relative: str) -> bool:
        return (self.root / relative).exists()

    def dependency_class(self, service: Dict[str, Any]) -> str:
        service_id = service["service_id"]
        boundary = service.get("boundary", "").lower()
        if service_id in {"vfs_volume_custody", "k_cloud_adapter"}:
            return "CORE_MANDATORY"
        if service_id in {"virtual_gpu_hci_dashboard"}:
            return "REPLACEABLE"
        if service_id in {"peer_ack_verifier"} or "provider" in boundary or "external" in boundary or "certification" in boundary:
            return "EXTERNAL_GATE"
        if service_id in {"task_milestone_monitor", "failure_ledger", "health_state_monitor", "dependency_failure_orchestrator"}:
            return "CORE_DEGRADED"
        return "CORE_DEGRADED"

    def fallback_for(self, service_id: str) -> str:
        if service_id == "virtual_gpu_hci_dashboard":
            return "adapter.canvas-cpu-renderer"
        if service_id == "peer_ack_verifier":
            return "adapter.local-peer-ack-outbox"
        if service_id == "btc_core_protocol_router":
            return "adapter.read-only-local-p2p-framer"
        if service_id == "k_cloud_adapter":
            return "adapter.local-k-app-package-outbox"
        return "adapter.local-static-applet"

    def row_for(self, service: Dict[str, Any]) -> MaturityRow:
        service_id = service["service_id"]
        dep_class = self.dependency_class(service)
        has_package = self.package_exists(service_id)
        if not has_package:
            return MaturityRow(
                component_id=service_id,
                component_type="SERVICE_APPLET",
                owner_plane=service.get("owner_plane", "unknown"),
                issue_code="MISSING_K_APP_PACKAGE",
                maturity_state="LOCAL_REPAIR_REQUIRED",
                corrective_workflow="package_local",
                pending_workload="Generate K-APP package, required manifests, runtime independence contract and manifest integrity readback.",
                action_command="bash scripts/ship_applications.command",
                required_receipts="evidence/application_applet_shipping_receipt.json;exports/application_applet_shipping_matrix.csv",
                dependency_class=dep_class,
                fallback_path=self.fallback_for(service_id),
                reentry_condition="package exists and integrity readback passes",
                promotion_boundary="LOCAL_SHIPPABLE_ONLY_AFTER_PACKAGE_RECEIPT",
            )
        if dep_class == "EXTERNAL_GATE":
            return MaturityRow(
                component_id=service_id,
                component_type="SERVICE_APPLET",
                owner_plane=service.get("owner_plane", "unknown"),
                issue_code="PROVIDER_GATE_PENDING",
                maturity_state="LOCAL_SHIPPABLE_WITH_TARGET_GATES",
                corrective_workflow="provider_gate",
                pending_workload="Keep local package and outbox active while awaiting external/provider or target-host proof.",
                action_command="capture signed provider/peer receipt then replay outbox",
                required_receipts="runtime_volume/outbox/*;provider_peer_ack_receipt_or_target_host_receipt",
                dependency_class=dep_class,
                fallback_path=self.fallback_for(service_id),
                reentry_condition="provider or target host produces signed receipt and capability readback",
                promotion_boundary="PROVIDER_REQUIRED_OR_TARGET_HOST_REQUIRED",
            )
        return MaturityRow(
            component_id=service_id,
            component_type="SERVICE_APPLET",
            owner_plane=service.get("owner_plane", "unknown"),
            issue_code="INTEGRITY_READBACK_REQUIRED",
            maturity_state="LOCAL_SHIPPABLE",
            corrective_workflow="full_local_acceptance",
            pending_workload="Preserve module as local shippable K-APP and keep running acceptance receipts until target host deployment is available.",
            action_command="bash scripts/run.command",
            required_receipts="evidence/application_applet_shipping_receipt.json;evidence/k_cloud_deployment_receipt.json;evidence/test_runner_receipt.json",
            dependency_class=dep_class,
            fallback_path=self.fallback_for(service_id),
            reentry_condition="local receipts pass and no target-host gate is required for local surface",
            promotion_boundary="LOCAL_PASS_WITH_TARGET_HOST_BOUNDARY_IF_APPLICABLE",
        )

    def global_rows(self) -> List[MaturityRow]:
        return [
            MaturityRow(
                component_id="pull_request_32_review_surface",
                component_type="GOVERNANCE_WORKFLOW",
                owner_plane="delivery_governance",
                issue_code="REVIEW_SURFACE_TOO_LARGE",
                maturity_state="TARGET_HOST_REQUIRED",
                corrective_workflow="split_release",
                pending_workload="After local receipt pack stabilizes, split the integration workbench into smaller release PRs so each lane can be reviewed, deployed and rolled back independently.",
                action_command="create lane-specific PRs after evidence artifact is captured",
                required_receipts="PR split plan; per-lane test receipts; per-lane K-APP packages",
                dependency_class="CORE_DEGRADED",
                fallback_path="continue current integration branch until split is safe",
                reentry_condition="local run.command receipt pack is stable and target-host evidence is captured",
                promotion_boundary="RELEASE_REVIEW_REQUIRED",
            ),
            MaturityRow(
                component_id="m3_target_host_deployment",
                component_type="TARGET_HOST_WORKFLOW",
                owner_plane="target_host_receipt_harness",
                issue_code="TARGET_HOST_GATE_PENDING",
                maturity_state="TARGET_HOST_REQUIRED",
                corrective_workflow="target_host",
                pending_workload="Register self-hosted macOS ARM64 runner, run host acceptance, capture launchd/iostat/browser/K-APP catalog readback receipts.",
                action_command="run v98-host-acceptance on [self-hosted, macOS, ARM64, KEDDEH-M3]",
                required_receipts="GitHub Actions artifact;launchd status;iostat receipt;browser catalog readback",
                dependency_class="EXTERNAL_GATE",
                fallback_path="portable local K-APP packages and outbox replay",
                reentry_condition="matching M3 runner executes and uploads evidence artifact",
                promotion_boundary="TARGET_HOST_REQUIRED",
            ),
        ]

    def write_work_packet(self, row: MaturityRow) -> Path:
        packet = {
            "component_id": row.component_id,
            "issue_code": row.issue_code,
            "maturity_state": row.maturity_state,
            "corrective_workflow": row.corrective_workflow,
            "pending_workload": row.pending_workload,
            "action_command": row.action_command,
            "required_receipts": row.required_receipts.split(";"),
            "dependency_class": row.dependency_class,
            "fallback_path": row.fallback_path,
            "reentry_condition": row.reentry_condition,
            "promotion_boundary": row.promotion_boundary,
            "research_basis": [
                "DORA continuous delivery small-batch deployability",
                "NIST SSDF lifecycle-integrated secure development",
                "GitHub deployment environments and protected gates",
                "fault-domain isolation and durable outbox pattern",
            ],
        }
        packet_hash = canonical_hash(packet)
        path = self.workplan_dir / f"{row.component_id}_{packet_hash}.json".replace("/", "_")
        write_json(path, packet)
        return path

    def run(self, emit_receipt: bool = False) -> Dict[str, Any]:
        started = time.time()
        rows = [self.row_for(service) for service in self.services] + self.global_rows()
        packet_paths = [self.write_work_packet(row) for row in rows]
        matrix_path = self.exports_dir / "deployment_maturity_workplan_matrix.csv"
        write_csv(matrix_path, [asdict(row) for row in rows])
        receipt_path = self.evidence_dir / "deployment_maturity_workplan_receipt.json"
        outbox = self.outbox_dir / f"{canonical_hash({'matrix': str(matrix_path), 'ts': started})}.handoff.json"
        local_shippable = sum(1 for row in rows if row.maturity_state == "LOCAL_SHIPPABLE")
        local_repair = sum(1 for row in rows if row.maturity_state == "LOCAL_REPAIR_REQUIRED")
        target_host = sum(1 for row in rows if row.maturity_state in {"TARGET_HOST_REQUIRED", "LOCAL_SHIPPABLE_WITH_TARGET_GATES"})
        provider = sum(1 for row in rows if row.issue_code == "PROVIDER_GATE_PENDING")
        receipt = DeploymentMaturityReceipt(
            version="V99",
            assessed_components=len(rows),
            local_shippable=local_shippable,
            local_repair_required=local_repair,
            target_host_required=target_host,
            provider_required=provider,
            workplan_packets_written=len(packet_paths),
            ledger_readback=False,
            receipt_path=str(receipt_path),
            matrix_path=str(matrix_path),
            outbox_manifest=str(outbox),
            timestamp=started,
        )
        entry = {"type": "deployment_maturity_workplan", "receipt": asdict(receipt), "packet_paths": [str(path) for path in packet_paths]}
        if emit_receipt:
            append_jsonl(self.ledger_path, entry)
            ledger = read_jsonl(self.ledger_path)
            receipt = DeploymentMaturityReceipt(**{**asdict(receipt), "ledger_readback": any(item.get("type") == "deployment_maturity_workplan" for item in ledger)})
            final_entry = {"type": "deployment_maturity_workplan", "receipt": asdict(receipt), "packet_paths": [str(path) for path in packet_paths]}
            write_json(receipt_path, {
                "runtime_rule": CANONICAL_RUNTIME_RULE,
                "receipt": asdict(receipt),
                "rows": [asdict(row) for row in rows],
                "workplan_packets": [str(path) for path in packet_paths],
                "simulation_used_as_deployment_proof": False,
                "telemetry_used_as_deployment_proof": False,
                "global_failure_from_dependency_failure": False,
            })
            write_json(outbox, {
                "source": "KEDDEH_V99_DEPLOYMENT_MATURITY_WORKPLAN",
                "payload_path": str(receipt_path),
                "matrix_path": str(matrix_path),
                "status": "ACTIONABLE_WORKPLAN_READY",
                "next_target": "run_command_then_target_host_provider_receipts",
                "created_at": started,
            })
            append_jsonl(self.ledger_path, final_entry)
        return {
            "runtime_rule": CANONICAL_RUNTIME_RULE,
            "receipt": asdict(receipt),
            "rows": [asdict(row) for row in rows],
            "workplan_packets": [str(path) for path in packet_paths],
            "simulation_used_as_deployment_proof": False,
            "telemetry_used_as_deployment_proof": False,
            "global_failure_from_dependency_failure": False,
        }


def run_deployment_maturity_workplan(root: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    return DeploymentMaturityWorkplan(root).run(emit_receipt=emit_receipt)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    result = run_deployment_maturity_workplan(Path(args.root), emit_receipt=args.emit_receipt)
    print(json.dumps(result["receipt"], indent=2, sort_keys=True))
    return 0 if result["receipt"]["workplan_packets_written"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
