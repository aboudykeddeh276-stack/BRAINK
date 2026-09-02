#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

SUCCESS = "SUCCESS"
FAILED_BOUNDED = "FAILED_BOUNDED"
SKIPPED_DEPENDENCY = "SKIPPED_DEPENDENCY"
TIMEOUT_BOUNDED = "TIMEOUT_BOUNDED"
NOT_DECLARED = "NOT_DECLARED"
CONTINUED = "CONTINUED"
CONTINUATION_STOPPED = "CONTINUATION_STOPPED"

@dataclass(frozen=True)
class RuntimeResult:
    runtime_id: str
    domain: str
    criticality: str
    command: List[str]
    working_directory: str
    started_at: float
    duration_seconds: float
    exit_code: int | None
    state: str
    stdout_tail: str
    stderr_tail: str
    expected_artifacts: List[str]
    artifacts_present: bool
    supplied_capabilities: List[str]
    blocked_by: List[str]
    continuation_state: str = NOT_DECLARED
    continuation_steps: int = 0
    continuation_receipts: List[Dict[str, Any]] | None = None

@dataclass(frozen=True)
class UnifiedRuntimeReceipt:
    receipt_id: str
    registry_id: str
    version: str
    runtimes_declared: int
    runtimes_executed: int
    runtimes_succeeded: int
    runtimes_failed_bounded: int
    runtimes_skipped_dependency: int
    continuation_steps_executed: int
    artifacts_readback_passed: bool
    ledger_readback_passed: bool
    global_stop: bool
    overall_state: str
    timestamp: float

def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def append_ledger(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")

def ledger_contains(path: Path, receipt_id: str) -> bool:
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and json.loads(line).get("receipt_id") == receipt_id:
            return True
    return False

def validate_registry(registry: Dict[str, Any]) -> None:
    runtimes = registry.get("runtimes")
    if not isinstance(runtimes, list) or not runtimes:
        raise ValueError("registry_requires_runtimes")
    ids = [item.get("runtime_id") for item in runtimes]
    if any(not item for item in ids):
        raise ValueError("runtime_identity_required")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_runtime_identity")
    known = set(ids)
    for runtime in runtimes:
        required = {"runtime_id", "domain", "command", "depends_on", "criticality", "timeout_seconds", "expected_artifacts", "supplied_capabilities"}
        missing = sorted(required - set(runtime))
        if missing:
            raise ValueError(f"runtime_missing_fields:{runtime.get('runtime_id')}:{','.join(missing)}")
        unknown = sorted(set(runtime["depends_on"]) - known)
        if unknown:
            raise ValueError(f"runtime_unknown_dependencies:{runtime['runtime_id']}:{','.join(unknown)}")
        if not isinstance(runtime["command"], list) or not runtime["command"]:
            raise ValueError(f"runtime_invalid_command:{runtime['runtime_id']}")
        continuation = runtime.get("continuation")
        if continuation is not None:
            continuation_required = {"handoff_path", "command", "max_steps", "expected_artifacts", "state_field", "executable_state", "operation_field", "executable_operation"}
            missing_continuation = sorted(continuation_required - set(continuation))
            if missing_continuation:
                raise ValueError(f"continuation_missing_fields:{runtime['runtime_id']}:{','.join(missing_continuation)}")
            if not isinstance(continuation["command"], list) or not continuation["command"]:
                raise ValueError(f"continuation_invalid_command:{runtime['runtime_id']}")
            if int(continuation["max_steps"]) < 1:
                raise ValueError(f"continuation_invalid_max_steps:{runtime['runtime_id']}")

def dependency_order(runtimes: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    remaining = {item["runtime_id"]: item for item in runtimes}
    emitted: List[Dict[str, Any]] = []
    resolved: set[str] = set()
    while remaining:
        ready = sorted((item for item in remaining.values() if set(item["depends_on"]) <= resolved), key=lambda item: item["runtime_id"])
        if not ready:
            raise ValueError("runtime_dependency_cycle")
        for item in ready:
            emitted.append(item)
            resolved.add(item["runtime_id"])
            del remaining[item["runtime_id"]]
    return emitted

def artifact_paths(root: Path, runtime: Dict[str, Any]) -> List[Path]:
    return [(root / value).resolve() for value in runtime["expected_artifacts"]]

def _handoff_executable(handoff: Dict[str, Any], continuation: Dict[str, Any]) -> bool:
    return handoff.get(continuation["state_field"]) == continuation["executable_state"] and handoff.get(continuation["operation_field"]) == continuation["executable_operation"]

def execute_continuations(root: Path, workdir: Path, runtime: Dict[str, Any]) -> tuple[str, int, List[Dict[str, Any]], str, str]:
    continuation = runtime.get("continuation")
    if continuation is None:
        return NOT_DECLARED, 0, [], "", ""
    handoff_path = (root / continuation["handoff_path"]).resolve()
    receipts: List[Dict[str, Any]] = []
    stdout_tail = ""
    stderr_tail = ""
    for step in range(1, int(continuation["max_steps"]) + 1):
        if not handoff_path.is_file():
            return FAILED_BOUNDED, step - 1, receipts, stdout_tail, f"continuation handoff missing: {handoff_path}"
        handoff_before = read_json(handoff_path)
        if not _handoff_executable(handoff_before, continuation):
            return CONTINUATION_STOPPED, step - 1, receipts, stdout_tail, stderr_tail
        proof_before = handoff_before.get("proof")
        try:
            completed = subprocess.run(continuation["command"], cwd=workdir, text=True, capture_output=True, timeout=int(continuation.get("timeout_seconds", runtime["timeout_seconds"])), check=False)
        except subprocess.TimeoutExpired as exc:
            return TIMEOUT_BOUNDED, step - 1, receipts, (exc.stdout or "")[-4000:], (exc.stderr or "")[-4000:]
        stdout_tail = completed.stdout[-4000:]
        stderr_tail = completed.stderr[-4000:]
        expected = [(root / value).resolve() for value in continuation["expected_artifacts"]]
        if completed.returncode != 0 or not all(path.is_file() for path in expected):
            return FAILED_BOUNDED, step - 1, receipts, stdout_tail, stderr_tail
        handoff_after = read_json(handoff_path)
        proof_after = handoff_after.get("proof")
        if not proof_after or proof_after == proof_before:
            return FAILED_BOUNDED, step - 1, receipts, stdout_tail, "continuation handoff proof did not advance"
        receipts.append({
            "step": step,
            "proof_before": proof_before,
            "proof_after": proof_after,
            "current_machine": handoff_after.get("current_machine"),
            "next_generation": handoff_after.get("next_generation"),
        })
    return CONTINUED, int(continuation["max_steps"]), receipts, stdout_tail, stderr_tail

def execute_runtime(root: Path, runtime: Dict[str, Any], states: Dict[str, str]) -> RuntimeResult:
    blocked_by = [dep for dep in runtime["depends_on"] if states.get(dep) != SUCCESS]
    started = time.time()
    workdir = (root / runtime.get("working_directory", ".")).resolve()
    expected = artifact_paths(root, runtime)
    if blocked_by:
        return RuntimeResult(runtime_id=runtime["runtime_id"], domain=runtime["domain"], criticality=runtime["criticality"], command=runtime["command"], working_directory=str(workdir), started_at=started, duration_seconds=0.0, exit_code=None, state=SKIPPED_DEPENDENCY, stdout_tail="", stderr_tail="", expected_artifacts=[str(path) for path in expected], artifacts_present=False, supplied_capabilities=runtime["supplied_capabilities"], blocked_by=blocked_by)
    try:
        completed = subprocess.run(runtime["command"], cwd=workdir, text=True, capture_output=True, timeout=int(runtime["timeout_seconds"]), check=False)
        present = all(path.is_file() for path in expected)
        state = SUCCESS if completed.returncode == 0 and present else FAILED_BOUNDED
        continuation_state = NOT_DECLARED
        continuation_steps = 0
        continuation_receipts: List[Dict[str, Any]] = []
        stdout_tail = completed.stdout[-4000:]
        stderr_tail = completed.stderr[-4000:]
        if state == SUCCESS and runtime.get("continuation") is not None:
            continuation_state, continuation_steps, continuation_receipts, continuation_stdout, continuation_stderr = execute_continuations(root, workdir, runtime)
            stdout_tail = continuation_stdout or stdout_tail
            stderr_tail = continuation_stderr or stderr_tail
            if continuation_state in {FAILED_BOUNDED, TIMEOUT_BOUNDED}:
                state = continuation_state
        return RuntimeResult(runtime_id=runtime["runtime_id"], domain=runtime["domain"], criticality=runtime["criticality"], command=runtime["command"], working_directory=str(workdir), started_at=started, duration_seconds=round(time.time() - started, 6), exit_code=completed.returncode, state=state, stdout_tail=stdout_tail, stderr_tail=stderr_tail, expected_artifacts=[str(path) for path in expected], artifacts_present=present, supplied_capabilities=runtime["supplied_capabilities"], blocked_by=[], continuation_state=continuation_state, continuation_steps=continuation_steps, continuation_receipts=continuation_receipts)
    except subprocess.TimeoutExpired as exc:
        return RuntimeResult(runtime_id=runtime["runtime_id"], domain=runtime["domain"], criticality=runtime["criticality"], command=runtime["command"], working_directory=str(workdir), started_at=started, duration_seconds=round(time.time() - started, 6), exit_code=None, state=TIMEOUT_BOUNDED, stdout_tail=(exc.stdout or "")[-4000:], stderr_tail=(exc.stderr or "")[-4000:], expected_artifacts=[str(path) for path in expected], artifacts_present=False, supplied_capabilities=runtime["supplied_capabilities"], blocked_by=[])

def run_all(root: Path, registry_path: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    root = root.expanduser().resolve()
    registry_path = registry_path if registry_path.is_absolute() else root / registry_path
    registry = read_json(registry_path)
    validate_registry(registry)
    ordered = dependency_order(registry["runtimes"])
    states: Dict[str, str] = {}
    results: List[RuntimeResult] = []
    for runtime in ordered:
        result = execute_runtime(root, runtime, states)
        results.append(result)
        states[result.runtime_id] = result.state
    result_rows = [asdict(item) for item in results]
    succeeded = sum(item.state == SUCCESS for item in results)
    failed = sum(item.state in {FAILED_BOUNDED, TIMEOUT_BOUNDED} for item in results)
    skipped = sum(item.state == SKIPPED_DEPENDENCY for item in results)
    continuation_steps = sum(item.continuation_steps for item in results)
    all_artifacts = all(item.artifacts_present for item in results if item.state == SUCCESS)
    global_stop = False
    overall = "OPERATIONAL" if succeeded == len(results) else "OPERATIONAL_DEGRADED"
    seed = {"registry_id": registry["registry_id"], "version": registry["version"], "results": result_rows, "global_stop": global_stop}
    receipt_id = "receipt://keddeh/unified-runtime/" + canonical_hash(seed)
    ledger_path = root / "runtime_volume" / "unified_runtime.ledger.jsonl"
    append_ledger(ledger_path, {"receipt_id": receipt_id, "results": result_rows, "overall_state": overall})
    readback = ledger_contains(ledger_path, receipt_id)
    receipt = UnifiedRuntimeReceipt(receipt_id=receipt_id, registry_id=registry["registry_id"], version=registry["version"], runtimes_declared=len(results), runtimes_executed=sum(item.exit_code is not None for item in results), runtimes_succeeded=succeeded, runtimes_failed_bounded=failed, runtimes_skipped_dependency=skipped, continuation_steps_executed=continuation_steps, artifacts_readback_passed=all_artifacts, ledger_readback_passed=readback, global_stop=global_stop, overall_state=overall if readback else "FAILED_CLOSED_RECEIPT", timestamp=time.time())
    payload = {"receipt": asdict(receipt), "runtime_results": result_rows}
    if emit_receipt:
        evidence_path = root / "evidence" / "unified_codebase_runtime_receipt.json"
        write_json(evidence_path, payload)
        outbox = root / "runtime_volume" / "outbox" / "unified_runtime" / "current.handoff.json"
        write_json(outbox, {"receipt_id": receipt_id, "receipt_path": str(evidence_path), "overall_state": receipt.overall_state, "global_stop": False, "continuation_steps_executed": continuation_steps, "next_target": "follow-runtime-handoffs-or-provider-boundary"})
    return payload

def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--registry", default="config/codebase_runtime_registry.json")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    payload = run_all(Path(args.root), Path(args.registry), args.emit_receipt)
    print(json.dumps(payload["receipt"], indent=2, sort_keys=True))
    return 0 if payload["receipt"]["overall_state"] in {"OPERATIONAL", "OPERATIONAL_DEGRADED"} else 1

if __name__ == "__main__":
    raise SystemExit(main())
