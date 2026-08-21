"""Importable BRAINK^6 Python skill/runtime adapter.

One runtime core, multiple callable surfaces. This module deliberately delegates
capability admission and execution to braink6_tool.BrainK6 rather than creating
an independent implementation.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from braink6_tool import BrainK6, Capability, TaskEnvelope


@dataclass(frozen=True)
class Workspace:
    root: Path

    @classmethod
    def open(cls, path: str | Path) -> "Workspace":
        root = Path(path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise FileNotFoundError(root)
        return cls(root)

    def python_files(self) -> list[str]:
        return [str(p.relative_to(self.root)) for p in sorted(self.root.rglob("*.py")) if ".git" not in p.parts]


class BrainK6Runtime:
    """Callable Python API over the canonical BRAINK^6 runtime."""

    def __init__(self, state_dir: str | Path | None = None):
        self.core = BrainK6(Path(state_dir) if state_dir else None) if state_dir else BrainK6()

    def task(self, task_id: str, title: str, goal: str, *, acceptance: Iterable[str] = (),
             constraints: Iterable[str] = (), obligations: Iterable[str] = (),
             parent_task_id: str | None = None) -> dict:
        return self.core.put_task(TaskEnvelope(
            task_id=task_id,
            title=title,
            goal=goal,
            acceptance=list(acceptance),
            parent_task_id=parent_task_id,
            constraints=list(constraints),
            obligations=list(obligations),
        ))

    def define_python(self, capability_id: str = "PYTHON", *, validators: Iterable[list[str]] | None = None) -> dict:
        checks = list(validators or [[sys.executable, "-c", "import sys; assert sys.version_info >= (3, 10)"]])
        return self.core.put_capability(Capability(capability_id, "Validated Python execution", ["python"], checks))

    def unlock(self, capability_id: str) -> dict:
        return self.core.unlock(capability_id)

    def execute(self, capability_id: str, command: list[str]) -> dict:
        return self.core.execute(capability_id, command)

    def run_python(self, source: str, capability_id: str = "PYTHON") -> dict:
        return self.execute(capability_id, [sys.executable, "-c", source])

    def inspect_workspace(self, path: str | Path) -> dict:
        ws = Workspace.open(path)
        files = ws.python_files()
        return {"root": str(ws.root), "python_files": files, "python_file_count": len(files)}

    def test_workspace(self, path: str | Path, capability_id: str = "PYTHON") -> dict:
        ws = Workspace.open(path)
        return self.execute(capability_id, [sys.executable, "-m", "pytest", "-q", str(ws.root)])

    def status(self) -> dict:
        return self.core.status()
