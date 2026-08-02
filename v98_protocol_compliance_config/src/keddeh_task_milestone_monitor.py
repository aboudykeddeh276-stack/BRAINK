#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    group_id: str
    ordinal: int
    worker_agent: str
    service_id: str
    primary_standard: str
    required_state: str
    deployment_state: str
    receipt_requirement: str


@dataclass(frozen=True)
class CompletionRecord:
    task_id: str
    state: str
    receipt_path: str
    completed_by: str
    completed_at: float
    hash_used_as_functional_proof: bool = False
    telemetry_only: bool = False


@dataclass(frozen=True)
class TaskMilestoneReceipt:
    monitor_id: str
    total_tasks: int
    valid_completed_tasks: int
    invalid_completion_records: int
    milestones_reached: List[int]
    newly_reached_milestones: List[int]
    notify_required: bool
    ledger_readback: bool
    outbox_manifest: str
    case_study: Dict[str, Any]
    timestamp: float


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
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
    return read_json(root / "config" / "task_milestone_registry.json")


def expand_tasks(config: Dict[str, Any]) -> List[TaskSpec]:
    tasks: List[TaskSpec] = []
    for group in config["task_groups"]:
        for index in range(1, int(group["count"]) + 1):
            tasks.append(TaskSpec(
                task_id=f"{config['version']}-{group['group_id']}-{index:03d}",
                group_id=group["group_id"],
                ordinal=index,
                worker_agent=group["worker_agent"],
                service_id=group["service_id"],
                primary_standard=group["primary_standard"],
                required_state=group["required_state"],
                deployment_state=group["deployment_state"],
                receipt_requirement=group["receipt_requirement"],
            ))
    return tasks


def load_completion_records(root: Path, config: Dict[str, Any]) -> List[CompletionRecord]:
    raw_records = read_json(root / config["completion_source"], default=[])
    records: List[CompletionRecord] = []
    for raw in raw_records or []:
        records.append(CompletionRecord(
            task_id=str(raw["task_id"]),
            state=str(raw["state"]),
            receipt_path=str(raw["receipt_path"]),
            completed_by=str(raw.get("completed_by", "unknown_worker")),
            completed_at=float(raw.get("completed_at", time.time())),
            hash_used_as_functional_proof=bool(raw.get("hash_used_as_functional_proof", False)),
            telemetry_only=bool(raw.get("telemetry_only", False)),
        ))
    return records


def resolve_under_root(root: Path, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    return path if path.is_absolute() else root / path


def validate_completion(root: Path, record: CompletionRecord, task_ids: Set[str], config: Dict[str, Any]) -> Tuple[bool, str]:
    if record.task_id not in task_ids:
        return False, "unknown_task_id"
    if record.state not in set(config["allowed_completion_states"]):
        return False, "state_not_promotable"
    if record.hash_used_as_functional_proof:
        return False, "hash_used_as_functional_proof"
    if record.telemetry_only:
        return False, "telemetry_only_not_completion"
    receipt = resolve_under_root(root, record.receipt_path)
    if not receipt.exists() or not receipt.is_file():
        return False, "receipt_path_missing"
    return True, "valid_receipt_backed_completion"


def evaluate_progress(root: Path, config: Dict[str, Any]) -> Tuple[List[TaskSpec], Dict[str, CompletionRecord], List[Dict[str, Any]]]:
    tasks = expand_tasks(config)
    task_ids = {task.task_id for task in tasks}
    valid: Dict[str, CompletionRecord] = {}
    invalid: List[Dict[str, Any]] = []
    for record in load_completion_records(root, config):
        ok, reason = validate_completion(root, record, task_ids, config)
        if ok:
            valid[record.task_id] = record
        else:
            invalid.append({"task_id": record.task_id, "reason": reason, **asdict(record)})
    return tasks, valid, invalid


def build_case_study(tasks: List[TaskSpec], completed: Dict[str, CompletionRecord], invalid: List[Dict[str, Any]]) -> Dict[str, Any]:
    group_totals: Dict[str, int] = {}
    group_completed: Dict[str, int] = {}
    for task in tasks:
        group_totals[task.group_id] = group_totals.get(task.group_id, 0) + 1
        if task.task_id in completed:
            group_completed[task.group_id] = group_completed.get(task.group_id, 0) + 1

    group_summary = [
        {
            "group_id": group_id,
            "completed": group_completed.get(group_id, 0),
            "total": total,
            "trajectory": "advancing" if group_completed.get(group_id, 0) else "planned_or_waiting_for_receipt",
        }
        for group_id, total in sorted(group_totals.items())
    ]

    return {
        "trajectory": "receipt_backed_growth" if completed else "planned_growth_pending_receipts",
        "useful_growth": "counts only tasks with existing receipts and allowed completion states",
        "environment_relevance": "separates local software work from M3 target-host, provider, and certification gates",
        "capacity_adequacy": "100-task plan is divided into ten bounded worker lanes of ten tasks each",
        "logical_progression": "task -> receipt -> ledger -> readback -> milestone -> case-study handoff",
        "unmet_needs": "target-host/provider tasks remain incomplete until receipts exist",
        "standards_basis": "ISO/IEC/IEEE 12207 lifecycle, ISO/IEC 42001 AI governance, NIST SSDF, OWASP ASVS, SLSA/CycloneDX and POSIX target-host boundaries are used as control anchors",
        "next_actions": "execute work orders, attach receipts, rerun monitor, and review at 50/100 milestones",
        "group_summary": group_summary,
        "invalid_completion_records": invalid,
    }


def record_completion(root: Path, config: Dict[str, Any], task_id: str, receipt_path: str, completed_by: str, state: str = "LOCAL_PASS") -> None:
    source = root / config["completion_source"]
    records = read_json(source, default=[])
    records.append({
        "task_id": task_id,
        "state": state,
        "receipt_path": receipt_path,
        "completed_by": completed_by,
        "completed_at": time.time(),
        "hash_used_as_functional_proof": False,
        "telemetry_only": False,
    })
    write_json(source, records)


def run_monitor(root: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    root = root.expanduser().resolve()
    config = load_config(root)
    started = time.time()
    tasks, completed, invalid = evaluate_progress(root, config)

    total_tasks = len(tasks)
    if total_tasks != int(config["task_total"]):
        raise ValueError(f"task registry expected {config['task_total']} tasks but expanded {total_tasks}")

    completed_count = len(completed)
    milestones = [int(m) for m in config["milestones"]]
    milestones_reached = [m for m in milestones if completed_count >= m]
    state_path = root / config["state_source"]
    state = read_json(state_path, default={"notified_milestones": []})
    notified = set(int(m) for m in state.get("notified_milestones", []))
    newly_reached = [m for m in milestones_reached if m not in notified]
    notify_required = bool(newly_reached)

    exports_dir = root / "exports"
    evidence_dir = root / "evidence"
    ledger_path = root / "runtime_volume" / "proof_bundles.ledger"
    outbox_dir = root / "runtime_volume" / "outbox" / "task_milestones"
    outbox_dir.mkdir(parents=True, exist_ok=True)

    matrix = []
    for task in tasks:
        record = completed.get(task.task_id)
        matrix.append({
            **asdict(task),
            "completion_state": record.state if record else "NOT_COMPLETED",
            "completed_by": record.completed_by if record else "",
            "receipt_path": record.receipt_path if record else "",
        })
    write_csv(exports_dir / "task_milestone_matrix.csv", matrix)

    case_study = build_case_study(tasks, completed, invalid)
    pre_receipt = {
        "monitor_id": config["registry_id"],
        "completed_count": completed_count,
        "milestones_reached": milestones_reached,
        "newly_reached_milestones": newly_reached,
        "case_study": case_study,
        "timestamp": started,
    }
    receipt_hash = canonical_hash(pre_receipt)
    receipt_path = evidence_dir / "task_milestone_monitor_receipt.json"
    outbox_path = outbox_dir / f"{receipt_hash}.handoff.json"

    handoff = {
        "handoff_id": receipt_hash,
        "source": "KEDDEH_V98_TASK_MILESTONE_MONITOR",
        "payload_path": str(receipt_path),
        "receipt_path": str(ledger_path),
        "next_target": "worker_case_study_review" if notify_required else "continue_work_until_next_milestone",
        "status": "MILESTONE_REVIEW_REQUIRED" if notify_required else "NO_NEW_MILESTONE",
        "created_at": started,
    }
    write_json(outbox_path, handoff)

    append_ledger(ledger_path, {
        "type": "task_milestone_monitor",
        "entry_hash": receipt_hash,
        "payload": pre_receipt,
        "outbox_manifest": str(outbox_path),
    })
    ledger_readback = any(entry.get("entry_hash") == receipt_hash for entry in read_ledger(ledger_path))

    if notify_required and ledger_readback:
        state["notified_milestones"] = sorted(notified.union(newly_reached))
        write_json(state_path, state)

    receipt = TaskMilestoneReceipt(
        monitor_id=config["registry_id"],
        total_tasks=total_tasks,
        valid_completed_tasks=completed_count,
        invalid_completion_records=len(invalid),
        milestones_reached=milestones_reached,
        newly_reached_milestones=newly_reached,
        notify_required=notify_required,
        ledger_readback=ledger_readback,
        outbox_manifest=str(outbox_path),
        case_study=case_study,
        timestamp=started,
    )
    final = {
        "receipt": asdict(receipt),
        "receipt_hash": receipt_hash,
        "hash_used_as_functional_proof": False,
        "telemetry_only_completion_allowed": False,
        "manual_completion_allowed": False,
        "agent_self_promotion_allowed": False,
    }
    if emit_receipt:
        write_json(receipt_path, final)
    return final


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    parser.add_argument("--record-task")
    parser.add_argument("--receipt-path")
    parser.add_argument("--completed-by", default="worker")
    parser.add_argument("--state", default="LOCAL_PASS")
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    config = load_config(root)
    if args.record_task:
        if not args.receipt_path:
            parser.error("--receipt-path is required with --record-task")
        record_completion(root, config, args.record_task, args.receipt_path, args.completed_by, args.state)
    result = run_monitor(root, emit_receipt=args.emit_receipt)
    print(json.dumps(result, indent=2, sort_keys=True))
    receipt = result["receipt"]
    return 0 if receipt["ledger_readback"] and receipt["total_tasks"] == config["task_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
