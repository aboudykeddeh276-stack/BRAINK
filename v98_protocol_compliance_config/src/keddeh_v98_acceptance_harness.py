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

from keddeh_service_probes import (
    EXTERNAL_CERTIFICATION_REQUIRED,
    LOCAL_FAIL,
    LOCAL_PASS,
    PROVIDER_REQUIRED,
    TARGET_HOST_REQUIRED,
    UNSUPPORTED_IN_THIS_RUNTIME,
    run_all_service_probes,
)

SERVICE_STAGES = ["recognize", "execute", "verify", "write_receipt", "readback", "handoff"]
REFERENCE_ALIGNMENT_ONLY = "REFERENCE_ALIGNMENT_ONLY"
TARGET_GATE_CHECK_MAP = {
    "TG-01": "runner_context",
    "TG-02": "launchd_service",
    "TG-04": "iostat_sample",
}
LOCAL_GATE_SERVICE_MAP = {
    "TG-08": "agent_runtime_service",
}
VALID_GATE_STATES = {
    LOCAL_PASS,
    LOCAL_FAIL,
    TARGET_HOST_REQUIRED,
    PROVIDER_REQUIRED,
    EXTERNAL_CERTIFICATION_REQUIRED,
    UNSUPPORTED_IN_THIS_RUNTIME,
}


@dataclass(frozen=True)
class ServiceReceipt:
    service_id: str
    owner_plane: str
    stages: Dict[str, bool]
    promotion_state: str
    boundary: str
    executed: bool
    probe_name: str
    evidence_path: str
    outbox_manifest: str
    details: Dict[str, Any]


@dataclass(frozen=True)
class GateReceipt:
    gate_id: str
    gate_type: str
    promotion_state: str
    receipt_required: str
    executed: bool
    evidence_path: str
    detail: str


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    return {
        "human_cannot_promote": model["human_can_promote_pass"] is False,
        "agent_cannot_promote": model["agent_can_promote_pass"] is False,
        "acceptance_harness_can_promote": model["acceptance_harness_can_promote_pass"] is True,
        "ledger_append_only": model["ledger_is_append_only"] is True,
        "virtual_cpu_validates": model["virtual_cpu_executes_validation"] is True,
        "virtual_gpu_renders": model["virtual_gpu_renders_state"] is True,
    }


def load_service_protocols(root: Path) -> List[Dict[str, Any]]:
    return read_json(root / "config" / "service_protocols.json")["services"]


def evaluate_services(root: Path) -> List[ServiceReceipt]:
    """Execute registered service probes and derive state from their results.

    The declaration in service_protocols.json is used only for discovery and metadata.
    It cannot promote a service. LOCAL_PASS requires an executed positive test, an
    executed negative-space test, receipt write, ledger readback and outbox handoff.
    """
    probe_receipts = run_all_service_probes(root, load_service_protocols(root))
    receipts: List[ServiceReceipt] = []
    for probe in probe_receipts:
        stages = {
            "recognize": True,
            "execute": probe.executed,
            "verify": probe.positive_test_passed and probe.negative_test_passed,
            "write_receipt": probe.receipt_written,
            "readback": probe.readback_passed,
            "handoff": probe.handoff_written,
        }
        receipts.append(
            ServiceReceipt(
                service_id=probe.service_id,
                owner_plane=probe.owner_plane,
                stages=stages,
                promotion_state=probe.classification,
                boundary=probe.boundary,
                executed=probe.executed,
                probe_name=probe.probe_name,
                evidence_path=probe.evidence_path,
                outbox_manifest=probe.outbox_manifest,
                details=probe.details,
            )
        )
    return receipts


def validate_standards_catalog(root: Path) -> Dict[str, Any]:
    catalog = read_json(root / "standards" / "standards_catalog.json")
    ids = {item["id"] for item in catalog["standards"]}
    required = {
        "ISO_56001_2024",
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


def load_target_host_checks(root: Path) -> tuple[str, Dict[str, Dict[str, Any]]]:
    evidence_path = root / "evidence" / "target_host_receipts.json"
    if not evidence_path.exists():
        return "", {}
    try:
        payload = read_json(evidence_path)
    except (OSError, ValueError, TypeError):
        return str(evidence_path), {}
    checks = payload.get("checks", [])
    if not isinstance(checks, list):
        return str(evidence_path), {}
    return str(evidence_path), {
        str(check.get("check_id")): check
        for check in checks
        if isinstance(check, dict) and check.get("check_id")
    }


def evaluate_local_gate(
    root: Path,
    gate: Dict[str, Any],
    service_receipts: List[ServiceReceipt],
) -> GateReceipt | None:
    """Resolve repository-local gates from executed receipts, never configuration flags."""
    gate_id = gate["gate_id"]
    if gate_id == "TG-03":
        ledger_path = root / "runtime_volume" / "proof_bundles.ledger"
        ledger_entries = read_ledger(ledger_path)
        readback_passed = bool(ledger_entries) and bool(service_receipts) and all(
            receipt.stages["readback"] for receipt in service_receipts
        )
        return GateReceipt(
            gate_id=gate_id,
            gate_type=gate["gate_type"],
            promotion_state=LOCAL_PASS if readback_passed else LOCAL_FAIL,
            receipt_required=gate["receipt_required"],
            executed=readback_passed,
            evidence_path=str(ledger_path) if ledger_path.exists() else "",
            detail=(
                f"Executable ledger readback verified with {len(ledger_entries)} entries "
                f"across {len(service_receipts)} service receipts."
                if readback_passed
                else "Local ledger write/readback proof is absent or incomplete."
            ),
        )

    service_id = LOCAL_GATE_SERVICE_MAP.get(gate_id)
    if not service_id:
        return None
    service = next((item for item in service_receipts if item.service_id == service_id), None)
    proved = bool(
        service
        and service.promotion_state == LOCAL_PASS
        and service.executed
        and service.stages["verify"]
        and service.stages["readback"]
        and service.evidence_path
    )
    return GateReceipt(
        gate_id=gate_id,
        gate_type=gate["gate_type"],
        promotion_state=LOCAL_PASS if proved else LOCAL_FAIL,
        receipt_required=gate["receipt_required"],
        executed=proved,
        evidence_path=service.evidence_path if service and proved else "",
        detail=(
            f"Executable virtual-CPU proof supplied by service {service_id}."
            if proved
            else f"Required executable service proof is missing for {service_id}."
        ),
    )


def evaluate_target_gates(
    root: Path,
    service_receipts: List[ServiceReceipt] | None = None,
) -> List[GateReceipt]:
    gates = read_json(root / "config" / "deployment_profile_macos_m3.json")["target_gates"]
    evidence_path, host_checks = load_target_host_checks(root)
    service_receipts = service_receipts or []
    receipts: List[GateReceipt] = []
    for gate in gates:
        local_receipt = evaluate_local_gate(root, gate, service_receipts)
        if local_receipt is not None:
            receipts.append(local_receipt)
            continue

        check_id = TARGET_GATE_CHECK_MAP.get(gate["gate_id"])
        check = host_checks.get(check_id, {}) if check_id else {}
        check_state = check.get("status")
        promotion_state = check_state if check_state in VALID_GATE_STATES else gate["promotion_state"]

        if gate["promotion_state"] == LOCAL_PASS and not check:
            promotion_state = LOCAL_FAIL

        receipts.append(
            GateReceipt(
                gate_id=gate["gate_id"],
                gate_type=gate["gate_type"],
                promotion_state=promotion_state,
                receipt_required=gate["receipt_required"],
                executed=bool(check.get("executed", False)),
                evidence_path=evidence_path if check else "",
                detail=str(
                    check.get(
                        "detail",
                        "No executable target-host or provider receipt has been ingested.",
                    )
                ),
            )
        )
    return receipts


def evaluate_orphans(root: Path) -> List[Dict[str, Any]]:
    registry = read_json(root / "config" / "orphan_registry.json")["orphaned_items"]
    return [
        {
            "item_id": item["item_id"],
            "previous_state": "ORPHANED",
            "assigned_service": item["assigned_service"],
            "resolution_state": item["resolution_state"],
        }
        for item in registry
    ]


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
    gates = evaluate_target_gates(root, service_receipts)
    orphan_rows = evaluate_orphans(root)

    ledger_entries = read_ledger(ledger_path)
    classification_counts: Dict[str, int] = {}
    for receipt in service_receipts:
        classification_counts[receipt.promotion_state] = classification_counts.get(receipt.promotion_state, 0) + 1

    gate_classification_counts: Dict[str, int] = {}
    for gate in gates:
        gate_classification_counts[gate.promotion_state] = gate_classification_counts.get(gate.promotion_state, 0) + 1

    local_services_passed = classification_counts.get(LOCAL_PASS, 0)
    service_probe_failures = [
        receipt.service_id for receipt in service_receipts if receipt.promotion_state == LOCAL_FAIL
    ]
    target_gate_failures = [gate.gate_id for gate in gates if gate.promotion_state == LOCAL_FAIL]
    all_probe_receipts_read_back = all(receipt.stages["readback"] for receipt in service_receipts)
    target_gate_count = sum(
        1
        for gate in gates
        if gate.promotion_state
        in {TARGET_HOST_REQUIRED, PROVIDER_REQUIRED, EXTERNAL_CERTIFICATION_REQUIRED}
    )

    write_csv(
        exports_dir / "service_execution_receipts.csv",
        [
            {
                "service_id": receipt.service_id,
                "owner_plane": receipt.owner_plane,
                "promotion_state": receipt.promotion_state,
                "executed": str(receipt.executed).lower(),
                "probe_name": receipt.probe_name,
                "evidence_path": receipt.evidence_path,
                "outbox_manifest": receipt.outbox_manifest,
                "boundary": receipt.boundary,
                **{stage: str(receipt.stages[stage]).lower() for stage in SERVICE_STAGES},
            }
            for receipt in service_receipts
        ],
    )
    write_csv(exports_dir / "target_gate_matrix.csv", [asdict(gate) for gate in gates])
    write_csv(exports_dir / "orphan_resolution_matrix.csv", orphan_rows)

    overall_pass = (
        all(authority_checks.values())
        and all_probe_receipts_read_back
        and not service_probe_failures
        and not target_gate_failures
        and standards["required_missing"] == []
        and standards["reference_alignment_only"] is True
    )
    outbox_manifest = {
        "handoff_id": canonical_hash(
            {
                "services": [
                    {"service_id": receipt.service_id, "state": receipt.promotion_state}
                    for receipt in service_receipts
                ],
                "gates": [
                    {"gate_id": gate.gate_id, "state": gate.promotion_state}
                    for gate in gates
                ],
                "started": started,
            }
        ),
        "source": "KEDDEH_V98_PROTOCOL_COMPLIANCE_DEPLOYMENT_OS",
        "payload_path": str(evidence_dir / "FINAL_VERIFICATION.json"),
        "receipt_path": str(ledger_path),
        "next_target": "self_hosted_macos_arm64_runner_then_launchd",
        "status": "READY_FOR_TARGET_HOST_EXECUTION" if overall_pass else "FAILED_CLOSED",
        "created_at": started,
    }
    outbox_path = outbox_dir / f"{outbox_manifest['handoff_id']}.handoff.json"
    write_json(outbox_path, outbox_manifest)

    launchd_gate = next((gate for gate in gates if gate.gate_id == "TG-02"), None)
    target_host_evidence_path, _ = load_target_host_checks(root)
    final = {
        "version": "V98",
        "status": (
            "PASS_WITH_EXECUTABLE_SERVICE_PROBES_AND_TARGET_HOST_DEPLOYMENT_GATES"
            if overall_pass
            else "LOCAL_FAIL_SERVICE_OR_TARGET_GATE_PROBE"
        ),
        "authority_checks_passed": all(authority_checks.values()),
        "authority_checks": authority_checks,
        "services_connected": len(service_receipts),
        "services_passed": local_services_passed,
        "service_classification_counts": classification_counts,
        "service_probe_failures": service_probe_failures,
        "service_receipts": [asdict(receipt) for receipt in service_receipts],
        "standards_catalog": standards,
        "target_gate_count": target_gate_count,
        "target_gate_classification_counts": gate_classification_counts,
        "target_gate_failures": target_gate_failures,
        "target_gate_receipts": [asdict(gate) for gate in gates],
        "target_host_receipt_ingested": bool(target_host_evidence_path),
        "orphan_items_resolved": len(orphan_rows),
        "ledger_entries": len(ledger_entries),
        "ledger_readback": all_probe_receipts_read_back,
        "outbox_manifest": str(outbox_path),
        "hash_used_as_functional_proof": False,
        "manifest_used_as_functional_proof": False,
        "telemetry_used_as_functional_proof": False,
        "certification_claimed": False,
        "remote_provider_claimed": False,
        "launchd_installed_here": bool(launchd_gate and launchd_gate.promotion_state == LOCAL_PASS),
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
    return 0 if result["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
