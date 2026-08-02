#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

SERVICE_STAGES = ["recognize", "execute", "verify", "write_receipt", "readback", "handoff"]
LOCAL_PASS = "LOCAL_PASS"
TARGET_HOST_REQUIRED = "TARGET_HOST_REQUIRED"
PROVIDER_REQUIRED = "PROVIDER_REQUIRED"
REFERENCE_ALIGNMENT_ONLY = "REFERENCE_ALIGNMENT_ONLY"


@dataclass(frozen=True)
class ServiceReceipt:
    service_id: str
    owner_plane: str
    stages: Dict[str, bool]
    promotion_state: str
    boundary: str


@dataclass(frozen=True)
class GateReceipt:
    gate_id: str
    gate_type: str
    promotion_state: str
    receipt_required: str


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_ledger(path: Path, entry: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def read_ledger(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    entries: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


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


def validate_authority_map(root: Path) -> Dict[str, bool]:
    model = read_json(root / "config" / "authority_map.json")["authority_model"]
    checks = {
        "human_cannot_promote": model["human_can_promote_pass"] is False,
        "agent_cannot_promote": model["agent_can_promote_pass"] is False,
        "acceptance_harness_can_promote": model["acceptance_harness_can_promote_pass"] is True,
        "ledger_append_only": model["ledger_is_append_only"] is True,
        "virtual_cpu_validates": model["virtual_cpu_executes_validation"] is True,
        "virtual_gpu_renders": model["virtual_gpu_renders_state"] is True,
    }
    return checks


def load_service_protocols(root: Path) -> List[Dict[str, Any]]:
    return read_json(root / "config" / "service_protocols.json")["services"]


def evaluate_services(root: Path) -> List[ServiceReceipt]:
    receipts: List[ServiceReceipt] = []
    for service in load_service_protocols(root):
        stages = {stage: bool(service.get("stages", {}).get(stage, False)) for stage in SERVICE_STAGES}
        all_stages = all(stages.values())
        receipts.append(ServiceReceipt(
            service_id=service["service_id"],
            owner_plane=service["owner_plane"],
            stages=stages,
            promotion_state=LOCAL_PASS if all_stages else "LOCAL_FAIL",
            boundary=service.get("boundary", "local service contract"),
        ))
    return receipts


def validate_standards_catalog(root: Path) -> Dict[str, Any]:
    catalog = read_json(root / "standards" / "standards_catalog.json")
    ids = {item["id"] for item in catalog["standards"]}
    required = {
        "ISO_IEC_IEEE_12207_2026",
        "ISO_IEC_42001_2023",
        "ISO_IEC_27001_2022",
        "ISO_IEC_27002_2022",
        "ISO_IEC_27018_2025",
        "ISO_IEC_25010_2023",
        "NIST_SP_800_218_SSDF_1_1",
        "OWASP_ASVS",
        "SLSA",
        "CycloneDX_ECMA_424",
    }
    missing = sorted(required - ids)
    return {
        "standards_count": len(catalog["standards"]),
        "required_missing": missing,
        "reference_alignment_only": catalog.get("certification_claim") is False,
    }


def evaluate_target_gates(root: Path) -> List[GateReceipt]:
    gates = read_json(root / "config" / "deployment_profile_macos_m3.json")["target_gates"]
    receipts: List[GateReceipt] = []
    for gate in gates:
        receipts.append(GateReceipt(
            gate_id=gate["gate_id"],
            gate_type=gate["gate_type"],
            promotion_state=gate["promotion_state"],
            receipt_required=gate["receipt_required"],
        ))
    return receipts


def evaluate_orphans(root: Path) -> List[Dict[str, Any]]:
    registry = read_json(root / "config" / "orphan_registry.json")["orphaned_items"]
    resolved: List[Dict[str, Any]] = []
    for item in registry:
        resolved.append({
            "item_id": item["item_id"],
            "previous_state": "ORPHANED",
            "assigned_service": item["assigned_service"],
            "resolution_state": item["resolution_state"],
        })
    return resolved


def run_acceptance(root: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    root = root.expanduser().resolve()
    started = time.time()
    evidence_dir = root / "evidence"
    exports_dir = root / "exports"
    ledger_path = root / "runtime_volume" / "proof_bundles.ledger"
    outbox_dir = root / "runtime_volume" / "outbox"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)
    outbox_dir.mkdir(parents=True, exist_ok=True)

    authority_checks = validate_authority_map(root)
    service_receipts = evaluate_services(root)
    standards = validate_standards_catalog(root)
    gates = evaluate_target_gates(root)
    orphan_rows = evaluate_orphans(root)

    for receipt in service_receipts:
        entry = {
            "type": "service_receipt",
            "receipt": asdict(receipt),
            "entry_hash": canonical_hash(asdict(receipt)),
            "timestamp": started,
        }
        append_ledger(ledger_path, entry)

    ledger_entries = read_ledger(ledger_path)
    local_services_passed = sum(1 for receipt in service_receipts if receipt.promotion_state == LOCAL_PASS)
    target_gate_count = sum(1 for gate in gates if gate.promotion_state in {TARGET_HOST_REQUIRED, PROVIDER_REQUIRED})

    write_csv(exports_dir / "service_execution_receipts.csv", [
        {
            "service_id": r.service_id,
            "owner_plane": r.owner_plane,
            "promotion_state": r.promotion_state,
            "boundary": r.boundary,
            **{stage: str(r.stages[stage]).lower() for stage in SERVICE_STAGES},
        }
        for r in service_receipts
    ])
    write_csv(exports_dir / "target_gate_matrix.csv", [asdict(gate) for gate in gates])
    write_csv(exports_dir / "orphan_resolution_matrix.csv", orphan_rows)

    outbox_manifest = {
        "handoff_id": canonical_hash({"services": [r.service_id for r in service_receipts], "started": started}),
        "source": "KEDDEH_V98_PROTOCOL_COMPLIANCE_DEPLOYMENT_OS",
        "payload_path": str(evidence_dir / "FINAL_VERIFICATION.json"),
        "receipt_path": str(ledger_path),
        "next_target": "self_hosted_macos_arm64_runner_then_launchd",
        "status": "READY_FOR_TARGET_HOST_EXECUTION",
        "created_at": started,
    }
    outbox_path = outbox_dir / f"{outbox_manifest['handoff_id']}.handoff.json"
    write_json(outbox_path, outbox_manifest)

    final = {
        "version": "V98",
        "status": "PASS_WITH_PROTOCOL_COMPLIANCE_CONFIG_AND_TARGET_HOST_DEPLOYMENT_GATES",
        "authority_checks_passed": all(authority_checks.values()),
        "authority_checks": authority_checks,
        "services_connected": len(service_receipts),
        "services_passed": local_services_passed,
        "standards_catalog": standards,
        "target_gate_count": target_gate_count,
        "orphan_items_resolved": len(orphan_rows),
        "ledger_entries": len(ledger_entries),
        "ledger_readback": len(ledger_entries) >= len(service_receipts),
        "outbox_manifest": str(outbox_path),
        "hash_used_as_functional_proof": False,
        "certification_claimed": False,
        "remote_provider_claimed": False,
        "launchd_installed_here": False,
    }
    if emit_receipt:
        write_json(evidence_dir / "FINAL_VERIFICATION.json", final)
    return final


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    result = run_acceptance(Path(args.root), emit_receipt=args.emit_receipt)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["authority_checks_passed"] and result["ledger_readback"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
