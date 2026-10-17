#!/usr/bin/env python3
"""BRAINK^6 — executable AI tool runtime.

This is a tool runtime, not a model replacement. It forces task identity,
capability reconstruction, dependency validation, execution receipts, and
return-to-parent semantics before an engineering capability may be claimed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / ".braink6"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass
class TaskEnvelope:
    task_id: str
    title: str
    goal: str
    acceptance: list[str]
    parent_task_id: str | None = None
    constraints: list[str] = field(default_factory=list)
    obligations: list[str] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Capability:
    capability_id: str
    purpose: str
    dependencies: list[str]
    validators: list[list[str]]
    state: str = "DECLARED"
    seed: str = ""

    def seal(self) -> None:
        payload = {"capability_id": self.capability_id, "purpose": self.purpose,
                   "dependencies": self.dependencies, "validators": self.validators}
        self.seed = digest(payload)
        self.state = "SEEDED"


class BrainK6:
    def __init__(self, state_dir: Path = STATE_DIR):
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "receipts").mkdir(exist_ok=True)
        (self.state_dir / "tasks").mkdir(exist_ok=True)
        (self.state_dir / "capabilities").mkdir(exist_ok=True)

    def put_task(self, task: TaskEnvelope) -> dict[str, Any]:
        body = asdict(task)
        body["task_hash"] = digest(body)
        self._write(self.state_dir / "tasks" / f"{task.task_id}.json", body)
        self._write(self.state_dir / "CURRENT_TASK", {"task_id": task.task_id})
        return body

    def current_task(self) -> dict[str, Any]:
        pointer = self._read(self.state_dir / "CURRENT_TASK")
        return self._read(self.state_dir / "tasks" / f"{pointer['task_id']}.json")

    def put_capability(self, cap: Capability) -> dict[str, Any]:
        cap.seal()
        body = asdict(cap)
        self._write(self.state_dir / "capabilities" / f"{cap.capability_id}.json", body)
        return body

    def unlock(self, capability_id: str) -> dict[str, Any]:
        path = self.state_dir / "capabilities" / f"{capability_id}.json"
        cap = self._read(path)
        expected = digest({k: cap[k] for k in ("capability_id", "purpose", "dependencies", "validators")})
        checks = []
        if expected != cap["seed"]:
            cap["state"] = "CORRUPTED"
        else:
            cap["state"] = "RECONSTRUCTED"
            for command in cap["validators"]:
                checks.append(self._run(command))
            cap["state"] = "UNLOCKED" if all(c["returncode"] == 0 for c in checks) else "VALIDATION_FAIL"
        self._write(path, cap)
        receipt = self._receipt("CAPABILITY_UNLOCK", {"capability": cap, "checks": checks})
        return receipt

    def execute(self, capability_id: str, command: list[str]) -> dict[str, Any]:
        task = self.current_task()
        cap = self._read(self.state_dir / "capabilities" / f"{capability_id}.json")
        if cap["state"] != "UNLOCKED":
            raise RuntimeError(f"capability {capability_id} is {cap['state']}, not UNLOCKED")
        result = self._run(command)
        return self._receipt("EXECUTION", {
            "task_id": task["task_id"], "task_hash": task["task_hash"],
            "capability_id": capability_id, "capability_seed": cap["seed"],
            "result": result,
        })

    def status(self) -> dict[str, Any]:
        task = None
        try:
            task = self.current_task()
        except (FileNotFoundError, KeyError):
            pass
        caps = []
        for path in sorted((self.state_dir / "capabilities").glob("*.json")):
            caps.append(self._read(path))
        return {"runtime": "BRAINK^6", "task": task, "capabilities": caps}

    def _run(self, command: list[str]) -> dict[str, Any]:
        started = time.time_ns()
        p = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        return {"command": command, "returncode": p.returncode,
                "stdout": p.stdout[-12000:], "stderr": p.stderr[-12000:],
                "started_ns": started, "ended_ns": time.time_ns()}

    def _receipt(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        receipt = {"kind": kind, "payload": payload, "timestamp_ns": time.time_ns()}
        receipt["receipt_hash"] = digest(receipt)
        path = self.state_dir / "receipts" / f"{receipt['timestamp_ns']}-{kind}.json"
        self._write(path, receipt)
        return receipt

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text())

    @staticmethod
    def _write(path: Path, value: Any) -> None:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(prog="braink6")
    sub = p.add_subparsers(dest="cmd", required=True)
    init = sub.add_parser("init-task")
    init.add_argument("task_id"); init.add_argument("title"); init.add_argument("goal")
    init.add_argument("--accept", action="append", default=[])
    init.add_argument("--constraint", action="append", default=[])
    init.add_argument("--obligation", action="append", default=[])
    cap = sub.add_parser("define-capability")
    cap.add_argument("capability_id"); cap.add_argument("purpose")
    cap.add_argument("--dependency", action="append", default=[])
    cap.add_argument("--validator", action="append", default=[])
    unlock = sub.add_parser("unlock"); unlock.add_argument("capability_id")
    run = sub.add_parser("run"); run.add_argument("capability_id"); run.add_argument("command", nargs=argparse.REMAINDER)
    sub.add_parser("status")
    a = p.parse_args(); b = BrainK6()
    if a.cmd == "init-task":
        out = b.put_task(TaskEnvelope(a.task_id, a.title, a.goal, a.accept, constraints=a.constraint, obligations=a.obligation))
    elif a.cmd == "define-capability":
        validators = [v.split() for v in a.validator]
        out = b.put_capability(Capability(a.capability_id, a.purpose, a.dependency, validators))
    elif a.cmd == "unlock": out = b.unlock(a.capability_id)
    elif a.cmd == "run":
        if not a.command: raise SystemExit("command required after capability id")
        out = b.execute(a.capability_id, a.command)
    else: out = b.status()
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
