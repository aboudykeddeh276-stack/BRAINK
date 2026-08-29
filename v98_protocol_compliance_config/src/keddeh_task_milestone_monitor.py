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
    source_path: str = ""
    command_path: str = ""
    positive_tests: int = 0
    negative_tests: int = 0
    ledger_path: str = "runtime_volume/proof_bundles.ledger"
    ledger_entry_hash: str = ""
    outbox_path: str = ""
    target_host_evidence_path: str = ""
    provider_evidence_path: str = ""
    certification_evidence_path: str = ""
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
            source_path=str(raw.get("source_path", "")),
            command_path=str(raw.get("command_path", "")),
            positive_tests=int(raw.get("positive_tests", 0) or 0),
            negative_tests=int(raw.get("negative_tests", 0) or 0),
            ledger_path=str(raw.get("ledger_path", "runtime_volume/proof_bundles.ledger")),
            ledger_entry_hash=str(raw.get("ledger_entry_hash", "")),
            outbox_path=str(raw.get("outbox_path", "")),
            target_host_evidence_path=str(raw.get("target_host_evidence_path", "")),
            provider_evidence_path=str(raw.get("provider_evidence_path", "")),
            certification_evidence_path=str(raw.get("certification_evidence_path", "")),
            hash_used_as_functional_proof=bool(raw.get("hash_used_as_functional_proof", False)),
            telemetry_only=bool(raw.get("telemetry_only", False)),
        ))
    return records


def resolve_under_root(root: Path, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    return path if path.is_absolute() else root / path


def path_is_file(root: Path, raw_path: str) -> bool:
    if not raw_path:
        return False
    path = resolve_under_root(root, raw_path)
    return path.exists() and path.is_file()


def ledger_contains_hash(root: Path, ledger_path: str, entry_hash: str) -> bool:
    if not ledger_path or not entry_hash:
        return False
    path = resolve_under_root(root, ledger_path)
    if not path.exists() or not path.is_file():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("entry_hash") == entry_hash or entry.get("receipt_hash") == entry_hash:
            return True
    return False


def receipt_has_local_pass(root: Path, receipt_path: str, task_id: str) -> bool:
    path = resolve_under_root(root, receipt_path)
    try:
        payload = read_json(path)
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(payload, dict):
        return False
    candidates = [
        payload.get("state"),
        payload.get("status"),
        payload.get("promotion_state"),
        (payload.get("receipt") or {}).get("state") if isinstance(payload.get("receipt"), dict) else None,
        (payload.get("receipt") or {}).get("promotion_state") if isinstance(payload.get("receipt"), dict) else None,
    ]
    if "LOCAL_PASS" not in candidates:
        return False
    receipt_task = payload.get("task_id")
    if receipt_task is not None and str(receipt_task) != task_id:
        return False
    return True


def validate_completion(root: Path, record: CompletionRecord, tasks_by_id: Dict[str, TaskSpec], config: Dict[str, Any]) -> Tuple[bool, str]:
    task = tasks_by_id.get(record.task_id)
    if task is None:
        return False, "unknown_task_id"
    if record.state not in set(config["allowed_completion_states"]):
        return False, "state_not_promotable"
    if record.hash_used_as_functional_proof:
        return False, "hash_used_as_functional_proof"
    if record.telemetry_only:
        return False, "telemetry_only_not_completion"
    if not path_is_file(root, record.source_path):
        return False, "executable_source_missing"
    if not path_is_file(root, record.command_path):
        return False, "command_path_missing"
    if record.positive_tests <= 0:
        return False, "positive_tests_missing"
    if record.negative_tests <= 0:
        return False, "negative_tests_missing"
    if not path_is_file(root, record.receipt_path):
        return False, "receipt_path_missing"
    if not receipt_has_local_pass(root, record.receipt_path, record.task_id):
        return False, "receipt_not_local_pass"
    if not ledger_contains_hash(root, record.ledger_path, record.ledger_entry_hash):
        return False, "ledger_readback_missing"
    if not path_is_file(root, record.outbox_path):
        return False, "outbox_handoff_missing"
    if task.deployment_state == "TARGET_HOST_GATED" and not path_is_file(root, record.target_host_evidence_path):
        return False, "target_host_evidence_missing"
    if task.deployment_state == "PROVIDER_GATED" and not path_is_file(root, record.provider_evidence_path):
        return False, "provider_evidence_missing"
    return True, "valid_executable_receipt_backed_completion"


def evaluate_progress(root: Path, config: Dict[str, Any]) -> Tuple[List[TaskSpec], Dict[str, CompletionRecord], List[Dict[str, Any]]]:
    tasks = expand_tasks(config)
    tasks_by_id = {task.task_id: task for task in tasks}
    valid: Dict[str, CompletionRecord] = {}
    invalid: List[Dict[str, Any]] = []
    for record in load_completion_records(root, config):
        ok, reason = validate_completion(root, record, tasks_by_id, config)
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
        "useful_growth": "counts only tasks with executable source, command path, positive and negative tests, LOCAL_PASS receipt, ledger readback and outbox handoff",
        "environment_relevance": "separates local software work from M3 target-host, provider and certification gates",
        "capacity_adequacy": "100-task plan is divided into ten bounded worker lanes of ten tasks each and reviewed every five verified completions",
        "logical_progression": "task -> executable source -> command -> positive/negative tests -> receipt -> ledger readback -> outbox -> environment gate -> milestone",
        "unmet_needs": "target-host/provider tasks remain incomplete until their authority-specific evidence files exist",
        "standards_basis": "ISO/IEC/IEEE 12207 lifecycle, ISO/IEC 25010 quality, ISO/IEC 42001 AI governance, NIST SSDF, OWASP ASVS, SLSA/CycloneDX and POSIX target-host boundaries are control anchors, not certification claims",
        "executable_receipts": [record.receipt_path for record in completed.values()],
        "failures": invalid,
        "next_actions": "execute separately reviewable work orders, persist complete evidence chains, rerun monitor, and emit one case study only at each newly reached multiple of five",
        "group_summary": group_summary,
        "invalid_completion_records": invalid,
    }


def record_completion(root: Path, config: Dict[str, Any], task_id: str, receipt_path: str, completed_by: str, state: str = "LOCAL_PASS") -> None:
    raise RuntimeError("Direct --record-task promotion is disabled. Completion records must be written by the acceptance harness with the full executable evidence contract.")


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
        record_completion(root, config, args.record_task, args.receipt_path or "", args.completed_by, args.state)
    result = run_monitor(root, emit_receipt=args.emit_receipt)
    print(json.dumps(result, indent=2, sort_keys=True))
    receipt = result["receipt"]
    return 0 if receipt["ledger_readback"] and receipt["total_tasks"] == config["task_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
