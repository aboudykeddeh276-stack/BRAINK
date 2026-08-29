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

RUNTIME_RULE = "DEPENDENCY_FAILURE_NE_GLOBAL_APPLICATION_FAILURE"


@dataclass(frozen=True)
class SurfaceAuditRow:
    surface_id: str
    surface_type: str
    issue_code: str
    evidence_state: str
    deployability_state: str
    dependency_class: str
    fallback_adapter: str
    corrective_workflow: str
    required_receipts: str
    next_action: str
    promotion_boundary: str


@dataclass(frozen=True)
class SurfaceAuditReceipt:
    version: str
    audited_surfaces: int
    local_shippable: int
    corrective_workflows: int
    target_or_provider_gated: int
    rejected_claim_count: int
    receipt_path: str
    matrix_path: str
    outbox_manifest: str
    ledger_readback: bool
    timestamp: float


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
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


class CurrentStateSurfaceAuditor:
    """Audits current app/application surfaces against deployable K-APP criteria.

    This class treats uploaded action history as useful diagnostic input, not proof.
    It converts problematic surfaces into corrective workflows with receipts and
    keeps dependency failures scoped to their domains.
    """

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.config = read_json(self.root / "config" / "current_state_surface_audit.json")
        self.package_root = self.root / "runtime_volume" / "k_app_packages" / "application_applet_shipping"
        self.evidence_dir = self.root / "evidence"
        self.exports_dir = self.root / "exports"
        self.workplan_dir = self.root / "runtime_volume" / "workplans" / "current_state_surface"
        self.outbox_dir = self.root / "runtime_volume" / "outbox" / "current_state_surface_audit"
        self.ledger_path = self.root / "runtime_volume" / "proof_bundles.ledger"

    def package_exists_for(self, surface_id: str) -> bool:
        normalized = "".join(ch if ch.isalnum() else "_" for ch in surface_id).strip("_").lower()
        package = self.package_root / normalized
        required = ["application/index.html", "k-app.manifest.json", "dependency-contracts.json", "degraded-mode-policy.json", "integrity.sha256"]
        return all((package / item).exists() for item in required)

    def evidence_state_for(self, surface: Dict[str, Any]) -> str:
        sid = surface["surface_id"]
        if self.package_exists_for(sid):
            return "K_APP_PACKAGE_PRESENT"
        if sid in {"google_tpu_server_rack", "simulated_agent_telemetry"}:
            return "CLAIM_OR_SIMULATION_REJECTED_AS_PROOF"
        if sid == "linux_microvm_v86":
            return "BOOT_ASSET_AND_SERIAL_READBACK_REQUIRED"
        if sid == "provision_agent":
            return "WORKER_CONTEXT_AND_RECEIPT_REQUIRED"
        if sid == "server_runtime_exec_endpoints":
            return "SECURITY_AND_AUDIT_RECEIPT_REQUIRED"
        return "K_APP_OR_RECEIPT_REQUIRED"

    def row_for(self, surface: Dict[str, Any]) -> SurfaceAuditRow:
        evidence_state = self.evidence_state_for(surface)
        has_package = evidence_state == "K_APP_PACKAGE_PRESENT"
        dependency_class = surface.get("dependency_class", "CORE_DEGRADED")
        gated = dependency_class in {"EXTERNAL_GATE", "DEFERRED_COMMIT", "REPLACEABLE"}
        deployability = "LOCAL_SHIPPABLE" if has_package else "CORRECTIVE_WORKFLOW_REQUIRED"
        if has_package and gated:
            deployability = "LOCAL_SHIPPABLE_WITH_TARGET_OR_PROVIDER_GATE"
        if not has_package and dependency_class == "CORE_MANDATORY":
            deployability = "LOCAL_REPAIR_REQUIRED_BEFORE_PROMOTION"
        issue_code = "NO_ISSUE" if has_package else surface.get("issue", "MISSING_DEPLOYABLE_EVIDENCE")
        required = "evidence/current_state_surface_audit_receipt.json;exports/current_state_surface_audit_matrix.csv"
        next_action = "bash scripts/ship_applications.command && bash scripts/current_state_audit.command"
        if surface["surface_id"] == "linux_microvm_v86":
            required += ";v86 boot asset receipt;serial output receipt"
            next_action = "capture BIOS/kernel/rootfs/v86 serial readback receipts"
        if surface["surface_id"] == "google_tpu_server_rack":
            required += ";hardware/provider capability receipt or local CPU fallback receipt"
            next_action = "bind TPU applet to explicit tensor job endpoint or local CPU fallback receipt"
        if surface["surface_id"] == "provision_agent":
            required += ";agent worker VFS namespace receipt;agent runtime work-order receipt"
            next_action = "bind provision agent to worker identity, VFS namespace, queue, policy, capability and receipt ledger"
        return SurfaceAuditRow(
            surface_id=surface["surface_id"],
            surface_type=surface["surface_type"],
            issue_code=issue_code,
            evidence_state=evidence_state,
            deployability_state=deployability,
            dependency_class=dependency_class,
            fallback_adapter=surface.get("fallback_adapter", "adapter.local-static-applet"),
            corrective_workflow=surface.get("required_correction", "generate K-APP package and receipts"),
            required_receipts=required,
            next_action=next_action,
            promotion_boundary="PROMOTE_ONLY_RECEIPT_BACKED_CAPABILITIES",
        )

    def write_packet(self, row: SurfaceAuditRow) -> Path:
        packet = {
            "surface_id": row.surface_id,
            "surface_type": row.surface_type,
            "issue_code": row.issue_code,
            "evidence_state": row.evidence_state,
            "deployability_state": row.deployability_state,
            "dependency_class": row.dependency_class,
            "fallback_adapter": row.fallback_adapter,
            "corrective_workflow": row.corrective_workflow,
            "required_receipts": row.required_receipts.split(";"),
            "next_action": row.next_action,
            "promotion_boundary": row.promotion_boundary,
            "research_basis": [
                "source action history is diagnostic, not proof",
                "K-APP manifest integrity readback before node execution",
                "dependency failure is not global application failure",
                "observability is not execution proof",
            ],
        }
        path = self.workplan_dir / f"{row.surface_id}_{canonical_hash(packet)}.json"
        write_json(path, packet)
        return path

    def run(self, emit_receipt: bool = False) -> Dict[str, Any]:
        started = time.time()
        rows = [self.row_for(surface) for surface in self.config["focus_surfaces"]]
        packet_paths = [self.write_packet(row) for row in rows]
        matrix_path = self.exports_dir / "current_state_surface_audit_matrix.csv"
        write_csv(matrix_path, [asdict(row) for row in rows])
        receipt_path = self.evidence_dir / "current_state_surface_audit_receipt.json"
        outbox = self.outbox_dir / f"{canonical_hash({'matrix': str(matrix_path), 'ts': started})}.handoff.json"
        local_shippable = sum(1 for row in rows if row.deployability_state.startswith("LOCAL_SHIPPABLE"))
        corrective = sum(1 for row in rows if "REQUIRED" in row.deployability_state)
        target_gated = sum(1 for row in rows if row.dependency_class in {"EXTERNAL_GATE", "DEFERRED_COMMIT", "REPLACEABLE"})
        rejected_claims = sum(1 for row in rows if row.evidence_state == "CLAIM_OR_SIMULATION_REJECTED_AS_PROOF")
        receipt = SurfaceAuditReceipt(
            version="V99",
            audited_surfaces=len(rows),
            local_shippable=local_shippable,
            corrective_workflows=corrective,
            target_or_provider_gated=target_gated,
            rejected_claim_count=rejected_claims,
            receipt_path=str(receipt_path),
            matrix_path=str(matrix_path),
            outbox_manifest=str(outbox),
            ledger_readback=False,
            timestamp=started,
        )
        if emit_receipt:
            append_jsonl(self.ledger_path, {"type": "current_state_surface_audit", "receipt": asdict(receipt), "packets": [str(p) for p in packet_paths]})
            ledger = read_jsonl(self.ledger_path)
            receipt = SurfaceAuditReceipt(**{**asdict(receipt), "ledger_readback": any(item.get("type") == "current_state_surface_audit" for item in ledger)})
            write_json(receipt_path, {
                "runtime_rule": RUNTIME_RULE,
                "receipt": asdict(receipt),
                "rows": [asdict(row) for row in rows],
                "work_packets": [str(path) for path in packet_paths],
                "source_history_treated_as_proof": False,
                "simulation_or_fake_telemetry_promoted": False,
            })
            write_json(outbox, {
                "source": "KEDDEH_V99_CURRENT_STATE_SURFACE_AUDITOR",
                "payload_path": str(receipt_path),
                "matrix_path": str(matrix_path),
                "status": "ACTIONABLE_CURRENT_STATE_AUDIT_READY",
                "next_target": "ship_applications_then_target_host_readback",
                "created_at": started,
            })
        return {
            "runtime_rule": RUNTIME_RULE,
            "receipt": asdict(receipt),
            "rows": [asdict(row) for row in rows],
            "work_packets": [str(path) for path in packet_paths],
            "source_history_treated_as_proof": False,
            "simulation_or_fake_telemetry_promoted": False,
        }


def run_current_state_surface_audit(root: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    return CurrentStateSurfaceAuditor(root).run(emit_receipt=emit_receipt)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    result = run_current_state_surface_audit(Path(args.root), emit_receipt=args.emit_receipt)
    print(json.dumps(result["receipt"], indent=2, sort_keys=True))
    return 0 if result["receipt"]["audited_surfaces"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
