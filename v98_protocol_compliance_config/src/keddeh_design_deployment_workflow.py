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

REQUIRED_PHASE_FIELDS = {
    "phase_id",
    "phase_type",
    "owner_service",
    "state",
    "required_inputs",
    "activities",
    "required_outputs",
    "required_receipts",
    "standards",
    "promotion_gate",
}

FORBIDDEN_SOLO_PROOF = {"manifest", "telemetry", "hash", "report", "dashboard_render", "documentation"}


@dataclass(frozen=True)
class PhaseValidation:
    phase_id: str
    phase_type: str
    owner_service: str
    state: str
    standards: str
    outputs: str
    receipts: str
    valid: bool
    reason: str


@dataclass(frozen=True)
class WorkflowReceipt:
    workflow_id: str
    version: str
    phase_count: int
    valid_phase_count: int
    completion_rule_count: int
    forbidden_solo_proof_blocked: bool
    ledger_readback: bool
    promotion_state: str
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


def append_ledger(path: Path, entry: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def read_ledger(path: Path) -> List[Dict[str, Any]]:
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
    return read_json(root / "config" / "software_design_deployment_workflow.json")


def validate_phase(phase: Dict[str, Any], allowed_states: set[str]) -> PhaseValidation:
    missing = sorted(REQUIRED_PHASE_FIELDS - set(phase))
    if missing:
        return PhaseValidation(
            phase_id=phase.get("phase_id", "UNKNOWN"),
            phase_type=phase.get("phase_type", "UNKNOWN"),
            owner_service=phase.get("owner_service", "UNKNOWN"),
            state=phase.get("state", "UNKNOWN"),
            standards=";".join(phase.get("standards", [])),
            outputs=";".join(phase.get("required_outputs", [])),
            receipts=";".join(phase.get("required_receipts", [])),
            valid=False,
            reason=f"missing_fields:{','.join(missing)}",
        )
    list_fields = ["required_inputs", "activities", "required_outputs", "required_receipts", "standards"]
    for field in list_fields:
        if not isinstance(phase[field], list) or not phase[field]:
            return PhaseValidation(
                phase_id=phase["phase_id"],
                phase_type=phase["phase_type"],
                owner_service=phase["owner_service"],
                state=phase["state"],
                standards=";".join(phase.get("standards", [])),
                outputs=";".join(phase.get("required_outputs", [])),
                receipts=";".join(phase.get("required_receipts", [])),
                valid=False,
                reason=f"empty_or_invalid:{field}",
            )
    if phase["state"] not in allowed_states:
        return PhaseValidation(
            phase_id=phase["phase_id"],
            phase_type=phase["phase_type"],
            owner_service=phase["owner_service"],
            state=phase["state"],
            standards=";".join(phase["standards"]),
            outputs=";".join(phase["required_outputs"]),
            receipts=";".join(phase["required_receipts"]),
            valid=False,
            reason="invalid_state",
        )
    return PhaseValidation(
        phase_id=phase["phase_id"],
        phase_type=phase["phase_type"],
        owner_service=phase["owner_service"],
        state=phase["state"],
        standards=";".join(phase["standards"]),
        outputs=";".join(phase["required_outputs"]),
        receipts=";".join(phase["required_receipts"]),
        valid=True,
        reason="valid",
    )


def validate_workflow(root: Path) -> List[PhaseValidation]:
    config = load_config(root)
    allowed_states = set(config["allowed_states"])
    order = list(config["phase_order"])
    phases = list(config["phases"])
    phase_ids = [phase.get("phase_id") for phase in phases]
    if order != phase_ids:
        return [PhaseValidation(
            phase_id="WORKFLOW_ORDER",
            phase_type="workflow",
            owner_service="software_design_deployment_workflow",
            state="blocked",
            standards="",
            outputs="",
            receipts="",
            valid=False,
            reason="phase_order_mismatch",
        )]
    return [validate_phase(phase, allowed_states) for phase in phases]


def run_design_deployment_workflow(root: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    root = root.expanduser().resolve()
    started = time.time()
    config = load_config(root)
    phase_validations = validate_workflow(root)

    evidence_dir = root / "evidence"
    exports_dir = root / "exports"
    ledger_path = root / "runtime_volume" / "proof_bundles.ledger"
    outbox_dir = root / "runtime_volume" / "outbox" / "design_deployment_workflow"
    outbox_dir.mkdir(parents=True, exist_ok=True)

    write_csv(exports_dir / "software_design_deployment_workflow_matrix.csv", [asdict(row) for row in phase_validations])

    forbidden_solo_proof_blocked = FORBIDDEN_SOLO_PROOF.issubset(set(config["not_completion_by_itself"]))
    valid_phase_count = sum(1 for row in phase_validations if row.valid)
    pre_receipt = {
        "workflow_id": config["workflow_id"],
        "version": config["version"],
        "phase_validations": [asdict(row) for row in phase_validations],
        "completion_rule": config["completion_rule"],
        "not_completion_by_itself": config["not_completion_by_itself"],
        "forbidden_solo_proof_blocked": forbidden_solo_proof_blocked,
        "timestamp": started,
    }
    receipt_hash = canonical_hash(pre_receipt)
    receipt_path = evidence_dir / "software_design_deployment_workflow_receipt.json"
    outbox_path = outbox_dir / f"{receipt_hash}.handoff.json"

    handoff = {
        "handoff_id": receipt_hash,
        "source": "KEDDEH_V99_SOFTWARE_DESIGN_DEPLOYMENT_WORKFLOW",
        "payload_path": str(receipt_path),
        "receipt_path": str(ledger_path),
        "next_target": "acceptance_harness_then_self_hosted_m3_runner",
        "status": "READY_FOR_TARGET_HOST_EXECUTION" if valid_phase_count == len(phase_validations) and forbidden_solo_proof_blocked else "FAILED_CLOSED",
        "created_at": started,
    }
    write_json(outbox_path, handoff)
    append_ledger(ledger_path, {
        "type": "software_design_deployment_workflow_receipt",
        "entry_hash": receipt_hash,
        "payload": pre_receipt,
        "outbox_manifest": str(outbox_path),
    })
    ledger_readback = any(entry.get("entry_hash") == receipt_hash for entry in read_ledger(ledger_path))

    receipt = WorkflowReceipt(
        workflow_id=config["workflow_id"],
        version=config["version"],
        phase_count=len(phase_validations),
        valid_phase_count=valid_phase_count,
        completion_rule_count=len(config["completion_rule"]),
        forbidden_solo_proof_blocked=forbidden_solo_proof_blocked,
        ledger_readback=ledger_readback,
        promotion_state="LOCAL_PASS" if valid_phase_count == len(phase_validations) and forbidden_solo_proof_blocked and ledger_readback else "LOCAL_FAIL",
        outbox_manifest=str(outbox_path),
        timestamp=started,
    )
    final = {
        "receipt": asdict(receipt),
        "receipt_hash": receipt_hash,
        "hash_used_as_functional_proof": False,
        "telemetry_used_as_functional_proof": False,
        "certification_claimed": False,
        "target_host_deployed_here": False,
    }
    if emit_receipt:
        write_json(receipt_path, final)
    return final


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    result = run_design_deployment_workflow(Path(args.root), emit_receipt=args.emit_receipt)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["receipt"]["promotion_state"] == "LOCAL_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
