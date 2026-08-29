#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

PENDING = "PENDING"
RUNNING = "RUNNING"
COMPLETED = "COMPLETED"
CANCELLED = "CANCELLED"
TIMED_OUT = "TIMED_OUT"
FAILED = "FAILED"
TERMINAL_STATES = {COMPLETED, CANCELLED, TIMED_OUT, FAILED}


class SchedulerError(ValueError):
    pass


class DuplicateWorkerError(SchedulerError):
    pass


class DuplicateTaskError(SchedulerError):
    pass


class UnknownWorkerError(SchedulerError):
    pass


class UnknownTaskError(SchedulerError):
    pass


class InvalidTransitionError(SchedulerError):
    pass


@dataclass
class Worker:
    worker_id: str
    capabilities: Set[str]
    capacity: int
    load: int = 0
    available: bool = True
    running_tasks: List[str] = field(default_factory=list)

    def can_run(self, task: "Task") -> bool:
        return (
            self.available
            and task.required_capabilities.issubset(self.capabilities)
            and self.load + task.demand <= self.capacity
        )

    def allocation_key(self) -> tuple[int, int, str]:
        # Fixed-point utilization keeps ordering deterministic without floats.
        utilization_ppm = (self.load * 1_000_000) // self.capacity
        return utilization_ppm, self.load, self.worker_id


@dataclass
class Task:
    task_id: str
    required_capabilities: Set[str]
    demand: int
    priority: int
    submitted_at: int
    deadline: Optional[int] = None
    state: str = PENDING
    assigned_worker: Optional[str] = None
    started_at: Optional[int] = None
    finished_at: Optional[int] = None
    result: Optional[Dict[str, Any]] = None

    def queue_key(self) -> tuple[int, int, str]:
        # Higher priority first, then submission order, then stable task id.
        return -self.priority, self.submitted_at, self.task_id


class DeterministicMeshScheduler:
    """Portable deterministic control-plane scheduler.

    The scheduler models registration, admission, allocation, completion,
    cancellation and timeout transitions. It does not create OS threads,
    contact remote workers, reserve host resources or execute task payloads.
    """

    def __init__(self) -> None:
        self.workers: Dict[str, Worker] = {}
        self.tasks: Dict[str, Task] = {}
        self.logical_time = 0
        self.events: List[Dict[str, Any]] = []

    def _event(self, kind: str, **payload: Any) -> None:
        self.events.append({"seq": len(self.events) + 1, "time": self.logical_time, "kind": kind, **payload})

    def register_worker(self, worker_id: str, capabilities: Iterable[str], capacity: int) -> Worker:
        worker_id = worker_id.strip()
        capability_set = {item.strip() for item in capabilities if item.strip()}
        if not worker_id:
            raise SchedulerError("worker_id is required")
        if worker_id in self.workers:
            raise DuplicateWorkerError(worker_id)
        if capacity <= 0:
            raise SchedulerError("worker capacity must be positive")
        if not capability_set:
            raise SchedulerError("worker must declare at least one capability")
        worker = Worker(worker_id, capability_set, capacity)
        self.workers[worker_id] = worker
        self._event("worker_registered", worker_id=worker_id, capacity=capacity, capabilities=sorted(capability_set))
        return worker

    def set_worker_available(self, worker_id: str, available: bool) -> None:
        worker = self._worker(worker_id)
        worker.available = bool(available)
        self._event("worker_availability_changed", worker_id=worker_id, available=worker.available)

    def submit_task(
        self,
        task_id: str,
        required_capabilities: Iterable[str],
        demand: int,
        priority: int = 0,
        deadline: Optional[int] = None,
    ) -> Task:
        task_id = task_id.strip()
        capability_set = {item.strip() for item in required_capabilities if item.strip()}
        if not task_id:
            raise SchedulerError("task_id is required")
        if task_id in self.tasks:
            raise DuplicateTaskError(task_id)
        if demand <= 0:
            raise SchedulerError("task demand must be positive")
        if not capability_set:
            raise SchedulerError("task must require at least one capability")
        if deadline is not None and deadline <= self.logical_time:
            raise SchedulerError("deadline must be greater than current logical time")
        task = Task(task_id, capability_set, demand, int(priority), self.logical_time, deadline)
        self.tasks[task_id] = task
        self._event(
            "task_submitted",
            task_id=task_id,
            demand=demand,
            priority=priority,
            required_capabilities=sorted(capability_set),
            deadline=deadline,
        )
        return task

    def schedule(self) -> List[Dict[str, str]]:
        allocations: List[Dict[str, str]] = []
        pending = sorted((task for task in self.tasks.values() if task.state == PENDING), key=Task.queue_key)
        for task in pending:
            candidates = sorted((worker for worker in self.workers.values() if worker.can_run(task)), key=Worker.allocation_key)
            if not candidates:
                self._event("task_deferred", task_id=task.task_id, reason="no_eligible_capacity")
                continue
            worker = candidates[0]
            worker.load += task.demand
            worker.running_tasks.append(task.task_id)
            worker.running_tasks.sort()
            task.state = RUNNING
            task.assigned_worker = worker.worker_id
            task.started_at = self.logical_time
            allocation = {"task_id": task.task_id, "worker_id": worker.worker_id}
            allocations.append(allocation)
            self._event("task_allocated", **allocation, demand=task.demand)
        return allocations

    def complete_task(self, task_id: str, result: Optional[Dict[str, Any]] = None) -> Task:
        task = self._task(task_id)
        if task.state != RUNNING or task.assigned_worker is None:
            raise InvalidTransitionError(f"task {task_id} is not running")
        worker = self._worker(task.assigned_worker)
        worker.load -= task.demand
        worker.running_tasks.remove(task.task_id)
        task.state = COMPLETED
        task.finished_at = self.logical_time
        task.result = result or {}
        self._event("task_completed", task_id=task_id, worker_id=worker.worker_id)
        return task

    def cancel_task(self, task_id: str) -> Task:
        task = self._task(task_id)
        if task.state in TERMINAL_STATES:
            raise InvalidTransitionError(f"task {task_id} is already terminal")
        if task.state == RUNNING and task.assigned_worker is not None:
            worker = self._worker(task.assigned_worker)
            worker.load -= task.demand
            worker.running_tasks.remove(task.task_id)
        task.state = CANCELLED
        task.finished_at = self.logical_time
        self._event("task_cancelled", task_id=task_id, worker_id=task.assigned_worker)
        return task

    def advance_time(self, logical_time: int) -> List[str]:
        if logical_time < self.logical_time:
            raise SchedulerError("logical time cannot move backwards")
        self.logical_time = logical_time
        timed_out: List[str] = []
        for task in sorted(self.tasks.values(), key=lambda item: item.task_id):
            if task.state in {PENDING, RUNNING} and task.deadline is not None and task.deadline <= logical_time:
                if task.state == RUNNING and task.assigned_worker is not None:
                    worker = self._worker(task.assigned_worker)
                    worker.load -= task.demand
                    worker.running_tasks.remove(task.task_id)
                task.state = TIMED_OUT
                task.finished_at = logical_time
                timed_out.append(task.task_id)
                self._event("task_timed_out", task_id=task.task_id, worker_id=task.assigned_worker)
        return timed_out

    def _worker(self, worker_id: str) -> Worker:
        try:
            return self.workers[worker_id]
        except KeyError as exc:
            raise UnknownWorkerError(worker_id) from exc

    def _task(self, task_id: str) -> Task:
        try:
            return self.tasks[task_id]
        except KeyError as exc:
            raise UnknownTaskError(task_id) from exc

    def snapshot(self) -> Dict[str, Any]:
        workers = []
        for worker in sorted(self.workers.values(), key=lambda item: item.worker_id):
            row = asdict(worker)
            row["capabilities"] = sorted(worker.capabilities)
            workers.append(row)
        tasks = []
        for task in sorted(self.tasks.values(), key=lambda item: item.task_id):
            row = asdict(task)
            row["required_capabilities"] = sorted(task.required_capabilities)
            tasks.append(row)
        return {
            "logical_time": self.logical_time,
            "workers": workers,
            "tasks": tasks,
            "events": list(self.events),
            "os_threads_created": False,
            "remote_workers_contacted": False,
            "host_resources_reserved": False,
        }


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def run_mesh_scheduler_acceptance(root: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    root = root.expanduser().resolve()
    scheduler = DeterministicMeshScheduler()
    scheduler.register_worker("alpha", {"cpu", "network"}, capacity=4)
    scheduler.register_worker("beta", {"cpu", "gpu"}, capacity=4)
    scheduler.register_worker("gamma", {"cpu", "network", "gpu"}, capacity=2)

    scheduler.submit_task("route-index", {"cpu", "network"}, demand=2, priority=20)
    scheduler.submit_task("frame-plan", {"cpu", "gpu"}, demand=2, priority=10)
    scheduler.submit_task("route-batch", {"cpu", "network"}, demand=3, priority=5)
    first_allocations = scheduler.schedule()
    scheduler.complete_task("route-index", {"routes": 3})
    second_allocations = scheduler.schedule()

    scheduler.submit_task("deadline-vector", {"cpu"}, demand=1, priority=1, deadline=5)
    scheduler.advance_time(5)

    duplicate_rejected = False
    impossible_task_deferred = False
    invalid_transition_rejected = False
    try:
        scheduler.register_worker("alpha", {"cpu"}, capacity=1)
    except DuplicateWorkerError:
        duplicate_rejected = True

    scheduler.submit_task("unsupported-capability", {"quantum"}, demand=1)
    scheduler.schedule()
    impossible_task_deferred = scheduler.tasks["unsupported-capability"].state == PENDING

    try:
        scheduler.complete_task("unsupported-capability")
    except InvalidTransitionError:
        invalid_transition_rejected = True

    snapshot = scheduler.snapshot()
    allocation_map = {
        item["task_id"]: item["worker_id"] for item in first_allocations + second_allocations
    }
    positive_test_passed = (
        allocation_map.get("route-index") == "alpha"
        and allocation_map.get("frame-plan") == "beta"
        and allocation_map.get("route-batch") == "alpha"
        and scheduler.tasks["route-index"].state == COMPLETED
        and scheduler.tasks["deadline-vector"].state == TIMED_OUT
    )
    negative_test_passed = duplicate_rejected and impossible_task_deferred and invalid_transition_rejected

    evidence_path = root / "evidence" / "mesh_scheduler_receipt.json"
    snapshot_path = root / "exports" / "mesh_scheduler_snapshot.json"
    ledger_path = root / "runtime_volume" / "proof_bundles.ledger"
    outbox_dir = root / "runtime_volume" / "outbox" / "mesh_scheduler"

    pre_receipt = {
        "component_id": "hyper_explicit_mesh_runtime",
        "classification": "LOCAL_PASS" if positive_test_passed and negative_test_passed else "LOCAL_FAIL",
        "positive_test_passed": positive_test_passed,
        "negative_test_passed": negative_test_passed,
        "allocation_map": allocation_map,
        "timed_out_tasks": [task.task_id for task in scheduler.tasks.values() if task.state == TIMED_OUT],
        "deferred_tasks": [task.task_id for task in scheduler.tasks.values() if task.state == PENDING],
        "duplicate_worker_rejected": duplicate_rejected,
        "invalid_transition_rejected": invalid_transition_rejected,
        "os_threads_created": False,
        "remote_workers_contacted": False,
        "host_resources_reserved": False,
        "boundary": "Portable deterministic scheduler model; no OS thread execution, remote transport, process launch or host resource reservation.",
    }
    receipt_hash = canonical_hash(pre_receipt)
    outbox_path = outbox_dir / f"{receipt_hash}.handoff.json"
    handoff = {
        "handoff_id": receipt_hash,
        "source": "KEDDEH_V98_MESH_SCHEDULER",
        "classification": pre_receipt["classification"],
        "payload_path": str(evidence_path),
        "receipt_path": str(ledger_path),
        "next_target": "service_probe_integration_then_target_host_worker_adapter",
        "status": "READY" if pre_receipt["classification"] == "LOCAL_PASS" else "FAILED_CLOSED",
    }

    if emit_receipt:
        write_json(snapshot_path, snapshot)
        write_json(evidence_path, pre_receipt)
        write_json(outbox_path, handoff)
        append_jsonl(
            ledger_path,
            {
                "type": "mesh_scheduler_receipt",
                "entry_hash": receipt_hash,
                "classification": pre_receipt["classification"],
                "evidence_path": str(evidence_path),
                "outbox_manifest": str(outbox_path),
            },
        )

    ledger_readback = emit_receipt and any(
        entry.get("entry_hash") == receipt_hash and entry.get("type") == "mesh_scheduler_receipt"
        for entry in read_jsonl(ledger_path)
    )
    return {
        **pre_receipt,
        "receipt_hash": receipt_hash,
        "receipt_path": str(evidence_path),
        "snapshot_path": str(snapshot_path),
        "outbox_manifest": str(outbox_path),
        "ledger_readback": ledger_readback,
        "hash_used_as_functional_proof": False,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    result = run_mesh_scheduler_acceptance(Path(args.root), emit_receipt=args.emit_receipt)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["classification"] == "LOCAL_PASS" and (result["ledger_readback"] or not args.emit_receipt) else 1


if __name__ == "__main__":
    raise SystemExit(main())
