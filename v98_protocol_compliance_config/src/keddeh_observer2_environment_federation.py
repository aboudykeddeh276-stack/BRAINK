#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
import hashlib
import json
import os
import platform
import subprocess
import sys


def canonical_root(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


class EnvironmentProbe(Protocol):
    probe_id: str
    environment_class: str

    def sample(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class FilesystemProcessProbe:
    probe_id: str
    root: str
    paths: tuple[str, ...] = ()
    process_match: tuple[str, ...] = ()
    environment_class: str = "FILESYSTEM_PROCESS_ENVIRONMENT"

    def sample(self) -> dict[str, Any]:
        base = Path(self.root).expanduser().resolve()
        files: list[dict[str, Any]] = []
        for relative in sorted(set(self.paths)):
            path = base / relative
            exists = path.is_file()
            files.append(
                {
                    "path": relative,
                    "exists": exists,
                    "bytes": path.stat().st_size if exists else 0,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if exists else "MISSING",
                }
            )

        current_pid = os.getpid()
        parent_pid = os.getppid()
        completed = subprocess.run(
            ["ps", "-eo", "pid=,ppid=,stat=,comm=,args="],
            capture_output=True,
            text=True,
            check=True,
        )
        needles = tuple(value.lower() for value in self.process_match)
        processes: list[dict[str, Any]] = []
        for raw in completed.stdout.splitlines():
            parts = raw.strip().split(None, 4)
            if len(parts) < 5:
                continue
            pid, ppid, stat, comm, args = parts
            if int(pid) in {current_pid, parent_pid}:
                continue
            if needles and not any(needle in args.lower() or needle in comm.lower() for needle in needles):
                continue
            processes.append(
                {
                    "pid": int(pid),
                    "ppid": int(ppid),
                    "stat": stat,
                    "comm": comm,
                    "args": args,
                }
            )

        payload = {
            "root": str(base),
            "files": files,
            "processes": processes,
            "runtime": {
                "python_executable": sys.executable,
                "python_version": platform.python_version(),
                "cwd": os.getcwd(),
                "root_exists": base.is_dir(),
            },
        }
        payload["probe_root"] = canonical_root(payload)
        return payload


@dataclass(frozen=True)
class MappingProbe:
    """Read-only projection for an environment sampled by an external substrate adapter.

    The mapping must be supplied by the adapter that actually interrogated that environment.
    This object does not upgrade recorded data into a live observation claim.
    """

    probe_id: str
    mapping: dict[str, Any]
    environment_class: str = "EXTERNAL_OBSERVED_ENVIRONMENT"

    def sample(self) -> dict[str, Any]:
        payload = {"mapping": self.mapping}
        payload["probe_root"] = canonical_root(payload)
        return payload


class EnvironmentFederation:
    """Read-only federation of substrate-aware environment probes.

    Observer² owns the interrogation frame. Probes remain substrate-specific and have no
    mutation authority. The federation root is a canonical composition of fresh probe roots.
    """

    def __init__(self, federation_id: str, probes: list[EnvironmentProbe] | None = None):
        self.federation_id = federation_id
        self._probes: dict[str, EnvironmentProbe] = {}
        for probe in probes or []:
            self.register(probe)

    def register(self, probe: EnvironmentProbe) -> None:
        if probe.probe_id in self._probes:
            raise ValueError(f"duplicate_probe:{probe.probe_id}")
        self._probes[probe.probe_id] = probe

    def sample(self) -> dict[str, Any]:
        environments: list[dict[str, Any]] = []
        for probe_id in sorted(self._probes):
            probe = self._probes[probe_id]
            observed_state = probe.sample()
            environments.append(
                {
                    "probe_id": probe_id,
                    "environment_class": probe.environment_class,
                    "observed_state": observed_state,
                    "probe_root": observed_state["probe_root"],
                }
            )
        payload = {
            "federation_id": self.federation_id,
            "sampling_mode": "LIVE_FEDERATED_INTERROGATION",
            "environments": environments,
        }
        payload["federation_root"] = canonical_root(payload)
        return payload
