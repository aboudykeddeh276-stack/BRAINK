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
        required = {
            "runtime_id", "domain", "command", "depends_on", "criticality",
            "timeout_seconds", "expected_artifacts", "supplied_capabilities",
        }
        missing = sorted(required - set(runtime))
        if missing:
            raise ValueError(f"runtime_missing_fields:{runtime.get('runtime_id')}:{','.join(missing)}")
        unknown = sorted(set(runtime["depends_on"]) - known)
        if unknown:
            raise ValueError(f"runtime_unknown_dependencies:{runtime['runtime_id']}:{','.join(unknown)}")
        if not isinstance(runtime["command"], list) or not runtime["command"]:
            raise ValueError(f"runtime_invalid_command:{runtime['runtime_id']}")


def dependency_order(runtimes: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    remaining = {item["runtime_id"]: item for item in runtimes}
    emitted: List[Dict[str, Any]] = []
    resolved: set[str] = set()
    while remaining:
        ready = sorted(
            (item for item in remaining.values() if set(item["depends_on"]) <= resolved),
            key=lambda item: item["runtime_id"],
        )
        if not ready:
            raise ValueError("runtime_dependency_cycle")
        for item in ready:
            emitted.append(item)
            resolved.add(item["runtime_id"])
            del remaining[item["runtime_id"]]
    return emitted


def artifact_paths(root: Path, runtime: Dict[str, Any]) -> List[Path]:
    return [(root / value).resolve() for value in runtime["expected_artifacts"]]


def execute_runtime(root: Path, runtime: Dict[str, Any], states: Dict[str, str]) -> RuntimeResult:
    blocked_by = [dep for dep in runtime["depends_on"] if states.get(dep) != SUCCESS]
    started = time.time()
    workdir = (root / runtime.get("working_directory", ".")).resolve()
    expected = artifact_paths(root, runtime)
    if blocked_by:
        return RuntimeResult(
            runtime_id=runtime["runtime_id"], domain=runtime["domain"],
            criticality=runtime["criticality"], command=runtime["command"],
            working_directory=str(workdir), started_at=started, duration_seconds=0.0,
            exit_code=None, state=SKIPPED_DEPENDENCY, stdout_tail="", stderr_tail="",
            expected_artifacts=[str(path) for path in expected], artifacts_present=False,
            supplied_capabilities=runtime["supplied_capabilities"], blocked_by=blocked_by,
        )
    try:
        completed = subprocess.run(
            runtime["command"], cwd=workdir, text=True, capture_output=True,
            timeout=int(runtime["timeout_seconds"]), check=False,
        )
        present = all(path.is_file() for path in expected)
        state = SUCCESS if completed.returncode == 0 and present else FAILED_BOUNDED
        return RuntimeResult(
            runtime_id=runtime["runtime_id"], domain=runtime["domain"],
            criticality=runtime["criticality"], command=runtime["command"],
            working_directory=str(workdir), started_at=started,
            duration_seconds=round(time.time() - started, 6), exit_code=completed.returncode,
            state=state, stdout_tail=completed.stdout[-4000:], stderr_tail=completed.stderr[-4000:],
            expected_artifacts=[str(path) for path in expected], artifacts_present=present,
            supplied_capabilities=runtime["supplied_capabilities"], blocked_by=[],
        )
    except subprocess.TimeoutExpired as exc:
        return RuntimeResult(
            runtime_id=runtime["runtime_id"], domain=runtime["domain"],
            criticality=runtime["criticality"], command=runtime["command"],
            working_directory=str(workdir), started_at=started,
            duration_seconds=round(time.time() - started, 6), exit_code=None,
            state=TIMEOUT_BOUNDED, stdout_tail=(exc.stdout or "")[-4000:],
            stderr_tail=(exc.stderr or "")[-4000:],
            expected_artifacts=[str(path) for path in expected], artifacts_present=False,
            supplied_capabilities=runtime["supplied_capabilities"], blocked_by=[],
        )


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
    all_artifacts = all(item.artifacts_present for item in results if item.state == SUCCESS)
    global_stop = False
    overall = "OPERATIONAL" if succeeded == len(results) else "OPERATIONAL_DEGRADED"
    seed = {
        "registry_id": registry["registry_id"],
        "version": registry["version"],
        "results": result_rows,
        "global_stop": global_stop,
    }
    receipt_id = "receipt://keddeh/unified-runtime/" + canonical_hash(seed)
    ledger_path = root / "runtime_volume" / "unified_runtime.ledger.jsonl"
    append_ledger(ledger_path, {"receipt_id": receipt_id, "results": result_rows, "overall_state": overall})
    readback = ledger_contains(ledger_path, receipt_id)
    receipt = UnifiedRuntimeReceipt(
        receipt_id=receipt_id, registry_id=registry["registry_id"], version=registry["version"],
        runtimes_declared=len(results), runtimes_executed=sum(item.exit_code is not None for item in results),
        runtimes_succeeded=succeeded, runtimes_failed_bounded=failed,
        runtimes_skipped_dependency=skipped, artifacts_readback_passed=all_artifacts,
        ledger_readback_passed=readback, global_stop=global_stop,
        overall_state=overall if readback else "FAILED_CLOSED_RECEIPT",
        timestamp=time.time(),
    )
    payload = {"receipt": asdict(receipt), "runtime_results": result_rows}
    if emit_receipt:
        evidence_path = root / "evidence" / "unified_codebase_runtime_receipt.json"
        write_json(evidence_path, payload)
        outbox = root / "runtime_volume" / "outbox" / "unified_runtime" / "current.handoff.json"
        write_json(outbox, {
            "receipt_id": receipt_id,
            "receipt_path": str(evidence_path),
            "overall_state": receipt.overall_state,
            "global_stop": False,
            "next_target": "provider-specific-runtime-extension",
        })
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
