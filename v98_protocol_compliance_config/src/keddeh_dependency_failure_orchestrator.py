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

ALLOWED_CLASSES = {
    "CORE_MANDATORY",
    "CORE_DEGRADED",
    "OPTIONAL",
    "EXTERNAL_GATE",
    "REPLACEABLE",
    "DEFERRED_COMMIT",
}

NON_GLOBAL_FAILURE_STATES = {
    "OPERATIONAL",
    "OPERATIONAL_PARTIAL",
    "OPERATIONAL_DEGRADED",
    "OPERATIONAL_EXTERNAL_GATE",
    "OPERATIONAL_ALTERNATE_PATH",
    "OPERATIONAL_DEFERRED_COMMIT",
}

REQUIRED_FIELDS = {
    "dependency_id",
    "class",
    "affected_capability",
    "blocked_domain",
    "impact_radius",
    "fallback_path",
    "continuation_mode",
    "re_entry_condition",
    "owner",
    "queue_policy",
    "retry_policy",
    "circuit_breaker_policy",
    "rollback_policy",
}


@dataclass(frozen=True)
class DependencyDecision:
    dependency_id: str
    dependency_class: str
    affected_capability: str
    blocked_domain: str
    impact_radius: str
    continuation_mode: str
    fallback_path: str
    re_entry_condition: str
    owner: str
    overall_status: str
    global_fail_stop: bool
    bounded_task_packet_required: bool
    task_packet_path: str
    valid: bool
    reason: str


@dataclass(frozen=True)
class DependencyFailureReceipt:
    version: str
    dependency_count: int
    valid_dependency_count: int
    global_fail_stop_count: int
    continuation_count: int
    task_packets_written: int
    ledger_readback: bool
    outbox_manifest: str
    promotion_state: str
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


def load_policy(root: Path) -> Dict[str, Any]:
    return read_json(root / "config" / "dependency_failure_policy.json")


def validate_dependency(dep: Dict[str, Any]) -> tuple[bool, str]:
    missing = sorted(REQUIRED_FIELDS - set(dep))
    if missing:
        return False, f"missing_fields:{','.join(missing)}"
    if dep["class"] not in ALLOWED_CLASSES:
        return False, f"invalid_class:{dep['class']}"
    for list_field in ["impact_radius"]:
        if not isinstance(dep[list_field], list) or not dep[list_field]:
            return False, f"invalid_list:{list_field}"
    for text_field in REQUIRED_FIELDS - {"impact_radius"}:
        if not isinstance(dep[text_field], str) or not dep[text_field].strip():
            return False, f"invalid_text:{text_field}"
    return True, "valid"


def decision_for_dependency(root: Path, dep: Dict[str, Any], policy: Dict[str, Any]) -> DependencyDecision:
    valid, reason = validate_dependency(dep)
    dep_class = dep.get("class", "UNKNOWN")
    class_rule = policy.get("dependency_classes", {}).get(dep_class, {})
    overall_status = class_rule.get("default_overall_status", "OPERATIONAL_PARTIAL")
    global_fail_stop = False

    # A dependency lane cannot globally stop the machine unless the input explicitly proves
    # that continuation violates a safety, integrity, or semantic invariant. The current
    # policy config intentionally contains no such proven global invariant violation.
    if dep.get("proven_global_invariant_violation") is True:
        overall_status = "GLOBAL_FAIL_STOP"
        global_fail_stop = True

    packet = {
        "owner": dep.get("owner", "UNKNOWN"),
        "blocked_capability": dep.get("affected_capability", "UNKNOWN"),
        "root_cause": dep.get("blocked_domain", "UNKNOWN"),
        "criticality_classification": dep_class,
        "research_basis": "failure-domain isolation, bulkheads, circuit breakers, durable outbox, graceful degradation, recovery reintegration",
        "logical_assessment": "Dependency failure is isolated to declared impact radius; unaffected runtimes continue.",
        "fallback_implementation": dep.get("fallback_path", "UNKNOWN"),
        "tests": ["tests/test_dependency_failure_orchestrator.py"],
        "receipts": ["evidence/dependency_failure_receipt.json"],
        "recovery_path": dep.get("retry_policy", "UNKNOWN"),
        "reintegration_criteria": dep.get("re_entry_condition", "UNKNOWN"),
        "closure_evidence": "dependency health check plus receipt-backed re-entry",
    }
    packet_hash = canonical_hash(packet)
    packet_path = root / "runtime_volume" / "task_packets" / "dependency_failure" / f"{dep.get('dependency_id', 'unknown')}_{packet_hash}.json"
    write_json(packet_path, packet)

    return DependencyDecision(
        dependency_id=dep.get("dependency_id", "UNKNOWN"),
        dependency_class=dep_class,
        affected_capability=dep.get("affected_capability", "UNKNOWN"),
        blocked_domain=dep.get("blocked_domain", "UNKNOWN"),
        impact_radius=";".join(dep.get("impact_radius", [])),
        continuation_mode=dep.get("continuation_mode", "UNKNOWN"),
        fallback_path=dep.get("fallback_path", "UNKNOWN"),
        re_entry_condition=dep.get("re_entry_condition", "UNKNOWN"),
        owner=dep.get("owner", "UNKNOWN"),
        overall_status=overall_status,
        global_fail_stop=global_fail_stop,
        bounded_task_packet_required=True,
        task_packet_path=str(packet_path),
        valid=valid and (global_fail_stop or overall_status in NON_GLOBAL_FAILURE_STATES),
        reason=reason,
    )


def run_orchestrator(root: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    root = root.expanduser().resolve()
    started = time.time()
    policy = load_policy(root)
    evidence_dir = root / "evidence"
    exports_dir = root / "exports"
    ledger = root / "runtime_volume" / "proof_bundles.ledger"
    outbox_dir = root / "runtime_volume" / "outbox" / "dependency_failure"
    outbox_dir.mkdir(parents=True, exist_ok=True)

    decisions = [decision_for_dependency(root, dep, policy) for dep in policy.get("runtime_domains", [])]
    matrix = [asdict(decision) for decision in decisions]
    write_csv(exports_dir / "dependency_failure_matrix.csv", matrix)

    global_fail_stop_count = sum(1 for decision in decisions if decision.global_fail_stop)
    continuation_count = sum(1 for decision in decisions if not decision.global_fail_stop)
    all_valid = all(decision.valid for decision in decisions)
    receipt_seed = {
        "policy_id": policy["policy_id"],
        "decision_count": len(decisions),
        "global_fail_stop_count": global_fail_stop_count,
        "continuation_count": continuation_count,
        "timestamp": started,
    }
    receipt_hash = canonical_hash(receipt_seed)
    outbox_path = outbox_dir / f"{receipt_hash}.handoff.json"
    handoff = {
        "handoff_id": receipt_hash,
        "source": "KEDDEH_V99_DEPENDENCY_FAILURE_ORCHESTRATOR",
        "payload_path": str(evidence_dir / "dependency_failure_receipt.json"),
        "receipt_path": str(ledger),
        "next_target": "acceptance_harness_then_target_host_reintegration",
        "status": "READY_FOR_TARGET_HOST_EXECUTION" if all_valid else "FAILED_CLOSED",
        "created_at": started,
    }
    write_json(outbox_path, handoff)

    append_ledger(ledger, {
        "type": "dependency_failure_orchestrator_receipt",
        "entry_hash": receipt_hash,
        "decisions": matrix,
        "outbox_manifest": str(outbox_path),
    })
    ledger_readback = any(entry.get("entry_hash") == receipt_hash for entry in read_ledger(ledger))

    receipt = DependencyFailureReceipt(
        version=policy["version"],
        dependency_count=len(decisions),
        valid_dependency_count=sum(1 for decision in decisions if decision.valid),
        global_fail_stop_count=global_fail_stop_count,
        continuation_count=continuation_count,
        task_packets_written=sum(1 for decision in decisions if Path(decision.task_packet_path).exists()),
        ledger_readback=ledger_readback,
        outbox_manifest=str(outbox_path),
        promotion_state="LOCAL_PASS" if all_valid and ledger_readback and global_fail_stop_count == 0 else "LOCAL_FAIL",
        timestamp=started,
    )
    payload = {
        "receipt": asdict(receipt),
        "decisions": matrix,
        "canonical_runtime_rule": policy["canonical_runtime_rule"],
        "global_runtime_failure_from_dependency_failure": False,
        "hash_used_as_functional_proof": False,
        "telemetry_used_as_functional_proof": False,
    }
    if emit_receipt:
        write_json(evidence_dir / "dependency_failure_receipt.json", payload)
    return payload


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    result = run_orchestrator(Path(args.root), emit_receipt=args.emit_receipt)
    print(json.dumps(result["receipt"], indent=2, sort_keys=True))
    return 0 if result["receipt"]["promotion_state"] == "LOCAL_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
