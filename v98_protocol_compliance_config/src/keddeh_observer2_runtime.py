#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import platform
import subprocess
import sys

from keddeh_observer2_environment_federation import EnvironmentFederation


def canonical_root(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class ObserverIdentity:
    observer_id: str
    observer_class: str
    role: str


@dataclass(frozen=True)
class ObserverScope:
    environment_root: str
    paths: tuple[str, ...]
    process_match: tuple[str, ...]


class Observer2Runtime:
    """Situated read-only observer.

    The observer actively interrogates its bound environment or federation. OBSERVED_STATE is
    an output artifact; it is never treated as the observer itself. Mutation authority remains
    outside this class.
    """

    def __init__(
        self,
        identity: ObserverIdentity,
        scope: ObserverScope,
        federation: EnvironmentFederation | None = None,
    ):
        self.identity = identity
        self.scope = scope
        self.environment_root = Path(scope.environment_root).expanduser().resolve()
        self.federation = federation
        self.prior_frame: dict[str, Any] | None = None

    def _sample_files(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for relative in sorted(set(self.scope.paths)):
            path = self.environment_root / relative
            exists = path.is_file()
            rows.append(
                {
                    "path": relative,
                    "exists": exists,
                    "bytes": path.stat().st_size if exists else 0,
                    "sha256": file_sha256(path) if exists else "MISSING",
                }
            )
        return rows

    def _sample_processes(self) -> list[dict[str, Any]]:
        completed = subprocess.run(
            ["ps", "-eo", "pid=,ppid=,stat=,comm=,args="],
            capture_output=True,
            text=True,
            check=True,
        )
        current_pid = os.getpid()
        parent_pid = os.getppid()
        needles = tuple(value.lower() for value in self.scope.process_match)
        rows: list[dict[str, Any]] = []
        for raw in completed.stdout.splitlines():
            parts = raw.strip().split(None, 4)
            if len(parts) < 5:
                continue
            pid, ppid, stat, comm, args = parts
            if int(pid) in {current_pid, parent_pid}:
                continue
            if needles and not any(needle in args.lower() or needle in comm.lower() for needle in needles):
                continue
            rows.append(
                {
                    "pid": int(pid),
                    "ppid": int(ppid),
                    "stat": stat,
                    "comm": comm,
                    "args": args,
                }
            )
        return rows

    def sample(self, *, expected: dict[str, Any] | None = None, label: str = "SAMPLE") -> dict[str, Any]:
        if self.federation is not None:
            federation_state = self.federation.sample()
            observed_state = {"federation": federation_state}
            environment = {
                "federation_id": federation_state["federation_id"],
                "sampling_mode": federation_state["sampling_mode"],
            }
        else:
            observed_state = {
                "files": self._sample_files(),
                "processes": self._sample_processes(),
                "runtime": {
                    "python_executable": sys.executable,
                    "python_version": platform.python_version(),
                    "cwd": os.getcwd(),
                    "environment_root_exists": self.environment_root.is_dir(),
                },
            }
            environment = {
                "root": str(self.environment_root),
                "sampling_mode": "LIVE_INTERROGATION",
            }

        frame: dict[str, Any] = {
            "observer_identity": asdict(self.identity),
            "scope": asdict(self.scope),
            "environment": environment,
            "label": label,
            "observed_state": observed_state,
            "expected": expected or {},
        }
        frame["frame_root"] = canonical_root(frame)
        self.prior_frame = frame
        return frame

    @staticmethod
    def compare(left: dict[str, Any], right: dict[str, Any], *, mode: str) -> dict[str, Any]:
        payload = {
            "mode": mode,
            "left_frame_root": left.get("frame_root"),
            "right_frame_root": right.get("frame_root"),
            "left_observed_state_root": canonical_root(left.get("observed_state", {})),
            "right_observed_state_root": canonical_root(right.get("observed_state", {})),
        }
        payload["changed"] = payload["left_observed_state_root"] != payload["right_observed_state_root"]
        payload["comparison_root"] = canonical_root(payload)
        return payload

    @staticmethod
    def continuation(
        pre: dict[str, Any],
        post: dict[str, Any],
        unresolved_discrepancy: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        comparison = Observer2Runtime.compare(pre, post, mode="PRE_POST")
        unresolved = unresolved_discrepancy or []
        payload = {
            "pre_frame_root": pre.get("frame_root"),
            "post_frame_root": post.get("frame_root"),
            "environment_delta": comparison,
            "unresolved_target_discrepancy": unresolved,
            "next": "CONTINUE_DISCREPANCY_RESOLUTION" if unresolved else "FOLLOW_SUCCESSOR_STATE",
        }
        payload["continuation_root"] = canonical_root(payload)
        return payload
