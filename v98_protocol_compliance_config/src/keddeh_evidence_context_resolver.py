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

FORMULA = "S=f(I,V,O,E,X,R,L)"
CANONICAL_STATEMENT = "Evidence classification is contextual state-resolution, not one-word terminal judgement."

VALID_DERIVED_STATES = {
    "DECLARED_TARGET",
    "DECLARED_VARIANT",
    "PROJECTION_ACTIVE",
    "FIXTURE_ACTIVE",
    "EMULATOR_ACTIVE",
    "LOCAL_EXECUTED",
    "HOST_EXECUTED",
    "PROVIDER_EXECUTED",
    "DEGRADED_VALID",
    "DEFERRED_COMMIT",
    "EVIDENCE_CORRELATION_REQUIRED",
    "CONTEXT_RESOLUTION_REQUIRED",
    "REINTEGRATION_REQUIRED",
    "BOUNDED_STOP",
    "GLOBAL_SAFETY_STOP",
}

FORBIDDEN_DIRECT_OUTPUTS = {"FAKE", "IMPOSSIBLE", "FAILED", "GLOBAL_STOP"}


@dataclass(frozen=True)
class EvidenceResolution:
    finding: str
    character_capability: str
    purpose: str
    observer: str
    environment: str
    execution_plane: str
    evidence_class: str
    freshness: str
    lineage: str
    derived_state: str
    impact_radius: str
    bounded_stop: bool
    global_safety_stop: bool
    resolution_required: bool
    reason: str


@dataclass(frozen=True)
class EvidenceContextReceipt:
    version: str
    formula: str
    resolution_count: int
    context_resolution_required_count: int
    evidence_correlation_required_count: int
    bounded_stop_count: int
    global_safety_stop_count: int
    forbidden_direct_terminal_judgement_count: int
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


def load_policy(root: Path) -> Dict[str, Any]:
    return read_json(root / "config" / "evidence_context_resolution_policy.json")


def validate_policy(policy: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if policy.get("formula") != FORMULA:
        errors.append("formula_mismatch")
    for key in ["invariants", "variants", "resolution_pipeline", "valid_derived_states", "sample_resolution_items"]:
        if not isinstance(policy.get(key), list) or not policy[key]:
            errors.append(f"missing_or_empty:{key}")
    missing_states = set(policy.get("valid_derived_states", [])) - VALID_DERIVED_STATES
    if missing_states:
        errors.append("unknown_valid_state:" + ",".join(sorted(missing_states)))
    forbidden = set(policy.get("forbidden_direct_outputs_from_single_signal", []))
    if not FORBIDDEN_DIRECT_OUTPUTS.issubset(forbidden):
        errors.append("forbidden_direct_outputs_incomplete")
    return errors


def derive_state(item: Dict[str, Any]) -> tuple[str, str]:
    if item.get("proven_global_safety_violation") or item.get("proven_global_semantic_violation") or item.get("proven_global_integrity_violation"):
        return "GLOBAL_SAFETY_STOP", "proven_global_violation"
    if item.get("proven_invariant_violation"):
        return "BOUNDED_STOP", "proven_invariant_violation"

    evidence_class = str(item.get("evidence_class", "")).lower()
    execution_plane = str(item.get("execution_plane", "")).lower()
    declared_state = str(item.get("derived_state", ""))

    if declared_state in VALID_DERIVED_STATES and declared_state not in {"BOUNDED_STOP", "GLOBAL_SAFETY_STOP"}:
        return declared_state, "declared_contextual_state_preserved"
    if "provider" in execution_plane and "receipt" in evidence_class:
        return "PROVIDER_EXECUTED", "provider_receipt_detected"
    if "host" in execution_plane and "receipt" in evidence_class:
        return "HOST_EXECUTED", "host_receipt_detected"
    if "local" in execution_plane and "receipt" in evidence_class:
        return "LOCAL_EXECUTED", "local_receipt_detected"
    if "emulator" in execution_plane:
        return "EMULATOR_ACTIVE", "emulator_variant"
    if "fixture" in execution_plane or "fixture" in evidence_class:
        return "FIXTURE_ACTIVE", "fixture_variant"
    if "projection" in execution_plane or "projection" in evidence_class:
        return "PROJECTION_ACTIVE", "projection_variant"
    if "deferred" in execution_plane or "deferred" in evidence_class:
        return "DEFERRED_COMMIT", "deferred_execution_variant"
    if "degraded" in execution_plane or "degraded" in evidence_class:
        return "DEGRADED_VALID", "degraded_execution_variant"
    if "label_without" in evidence_class or "uncorroborated" in evidence_class:
        return "EVIDENCE_CORRELATION_REQUIRED", "single_signal_requires_correlation"
    return "CONTEXT_RESOLUTION_REQUIRED", "insufficient_context_for_capability_state"


def resolve_item(item: Dict[str, Any]) -> EvidenceResolution:
    derived_state, reason = derive_state(item)
    return EvidenceResolution(
        finding=str(item.get("finding", "UNKNOWN")),
        character_capability=str(item.get("character_capability", "UNKNOWN")),
        purpose=str(item.get("purpose", "UNKNOWN")),
        observer=str(item.get("observer", "UNKNOWN")),
        environment=str(item.get("environment", "UNKNOWN")),
        execution_plane=str(item.get("execution_plane", "UNKNOWN")),
        evidence_class=str(item.get("evidence_class", "UNKNOWN")),
        freshness=str(item.get("freshness", "UNKNOWN")),
        lineage=str(item.get("lineage", "UNKNOWN")),
        derived_state=derived_state,
        impact_radius=";".join(item.get("impact_radius", ["capability_scoped"])) if isinstance(item.get("impact_radius", ["capability_scoped"]), list) else str(item.get("impact_radius")),
        bounded_stop=derived_state == "BOUNDED_STOP",
        global_safety_stop=derived_state == "GLOBAL_SAFETY_STOP",
        resolution_required=derived_state in {"CONTEXT_RESOLUTION_REQUIRED", "EVIDENCE_CORRELATION_REQUIRED", "REINTEGRATION_REQUIRED"},
        reason=reason,
    )


def work_packet_for(root: Path, resolution: EvidenceResolution) -> Path:
    packet = {
        "finding": resolution.finding,
        "character_capability": resolution.character_capability,
        "purpose": resolution.purpose,
        "observer": resolution.observer,
        "environment": resolution.environment,
        "execution_plane": resolution.execution_plane,
        "evidence_class": resolution.evidence_class,
        "freshness": resolution.freshness,
        "lineage": resolution.lineage,
        "derived_state": resolution.derived_state,
        "impact_radius": resolution.impact_radius.split(";"),
        "required_changes": [
            "collect capability-scoped readback",
            "bind receipt to observer/environment/execution plane",
            "preserve lineage and freshness",
        ],
        "positive_tests": ["tests/test_evidence_context_resolver.py"],
        "negative_tests": ["single signal does not produce FAKE, FAILED, IMPOSSIBLE or GLOBAL_STOP"],
        "reentry_conditions": ["fresh receipt correlates identity, execution plane, evidence class and lineage"],
        "promotion_evidence": ["evidence/evidence_context_resolution_receipt.json"],
        "owner": "evidence_context_resolver",
    }
    packet_hash = canonical_hash(packet)
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in resolution.finding).strip("_").lower() or "finding"
    path = root / "runtime_volume" / "workplans" / "evidence_context" / f"{safe_name}_{packet_hash}.json"
    write_json(path, packet)
    return path


def run_evidence_context_resolution(root: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    root = root.expanduser().resolve()
    started = time.time()
    policy = load_policy(root)
    errors = validate_policy(policy)
    if errors:
        raise ValueError("invalid evidence context policy: " + ";".join(errors))

    resolutions = [resolve_item(item) for item in policy["sample_resolution_items"]]
    packet_paths = [work_packet_for(root, resolution) for resolution in resolutions if resolution.resolution_required]

    matrix_path = root / "exports" / "evidence_context_resolution_matrix.csv"
    receipt_path = root / "evidence" / "evidence_context_resolution_receipt.json"
    outbox = root / "runtime_volume" / "outbox" / "evidence_context_resolution" / f"{canonical_hash({'ts': started, 'count': len(resolutions)})}.handoff.json"
    ledger_path = root / "runtime_volume" / "proof_bundles.ledger"
    write_csv(matrix_path, [asdict(resolution) for resolution in resolutions])

    forbidden_direct = sum(1 for resolution in resolutions if resolution.derived_state in FORBIDDEN_DIRECT_OUTPUTS)
    receipt = EvidenceContextReceipt(
        version=str(policy.get("version", "V99")),
        formula=FORMULA,
        resolution_count=len(resolutions),
        context_resolution_required_count=sum(1 for resolution in resolutions if resolution.derived_state == "CONTEXT_RESOLUTION_REQUIRED"),
        evidence_correlation_required_count=sum(1 for resolution in resolutions if resolution.derived_state == "EVIDENCE_CORRELATION_REQUIRED"),
        bounded_stop_count=sum(1 for resolution in resolutions if resolution.bounded_stop),
        global_safety_stop_count=sum(1 for resolution in resolutions if resolution.global_safety_stop),
        forbidden_direct_terminal_judgement_count=forbidden_direct,
        ledger_readback=False,
        receipt_path=str(receipt_path),
        matrix_path=str(matrix_path),
        outbox_manifest=str(outbox),
        timestamp=started,
    )
    entry = {"type": "evidence_context_resolution", "receipt": asdict(receipt), "packet_paths": [str(path) for path in packet_paths]}

    if emit_receipt:
        append_jsonl(ledger_path, entry)
        ledger = read_jsonl(ledger_path)
        receipt = EvidenceContextReceipt(**{**asdict(receipt), "ledger_readback": any(item.get("type") == "evidence_context_resolution" for item in ledger)})
        final = {
            "canonical_statement": CANONICAL_STATEMENT,
            "formula": FORMULA,
            "terms": policy["terms"],
            "invariants": policy["invariants"],
            "variants": policy["variants"],
            "receipt": asdict(receipt),
            "resolutions": [asdict(resolution) for resolution in resolutions],
            "work_packets": [str(path) for path in packet_paths],
            "single_signal_used_as_terminal_judgement": False,
            "global_stop_from_single_signal": False,
        }
        write_json(receipt_path, final)
        write_json(outbox, {
            "source": "KEDDEH_V99_EVIDENCE_CONTEXT_RESOLVER",
            "payload_path": str(receipt_path),
            "matrix_path": str(matrix_path),
            "status": "CONTEXTUAL_RESOLUTION_READY",
            "created_at": started,
        })
        append_jsonl(ledger_path, {"type": "evidence_context_resolution", "receipt": asdict(receipt), "packet_paths": [str(path) for path in packet_paths]})

    return {
        "canonical_statement": CANONICAL_STATEMENT,
        "formula": FORMULA,
        "terms": policy["terms"],
        "invariants": policy["invariants"],
        "variants": policy["variants"],
        "receipt": asdict(receipt),
        "resolutions": [asdict(resolution) for resolution in resolutions],
        "work_packets": [str(path) for path in packet_paths],
        "single_signal_used_as_terminal_judgement": False,
        "global_stop_from_single_signal": False,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    result = run_evidence_context_resolution(Path(args.root), emit_receipt=args.emit_receipt)
    print(json.dumps(result["receipt"], indent=2, sort_keys=True))
    ok = result["receipt"]["forbidden_direct_terminal_judgement_count"] == 0 and not result["global_stop_from_single_signal"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
