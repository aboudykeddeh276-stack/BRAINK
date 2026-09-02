from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Protocol
import json
import os
import subprocess
import time
import urllib.request


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(obj: Any) -> str:
    return sha256(_canon(obj)).hexdigest()


@dataclass(frozen=True)
class ProbeReceipt:
    observer_id: str
    environment_id: str
    probe_id: str
    substrate: str
    sampled_at_ns: int
    status: str
    payload: Mapping[str, Any]
    payload_sha256: str
    error: Optional[str] = None

    @staticmethod
    def make(*, observer_id: str, environment_id: str, probe_id: str, substrate: str,
             status: str, payload: Mapping[str, Any], sampled_at_ns: Optional[int] = None,
             error: Optional[str] = None) -> "ProbeReceipt":
        ts = int(time.time_ns() if sampled_at_ns is None else sampled_at_ns)
        frozen_payload = json.loads(json.dumps(payload, sort_keys=True, default=str))
        return ProbeReceipt(
            observer_id=observer_id,
            environment_id=environment_id,
            probe_id=probe_id,
            substrate=substrate,
            sampled_at_ns=ts,
            status=status,
            payload=frozen_payload,
            payload_sha256=_digest(frozen_payload),
            error=error,
        )


@dataclass(frozen=True)
class FederatedFrame:
    observer_id: str
    logical_time: int
    receipts: tuple[ProbeReceipt, ...]
    environment_root_sha256: str
    continuation: Mapping[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema": "kex.observer2.federated-frame.r29",
            "observer_id": self.observer_id,
            "logical_time": self.logical_time,
            "environment_root_sha256": self.environment_root_sha256,
            "receipts": [asdict(r) for r in self.receipts],
            "continuation": dict(self.continuation),
        }


class ReadOnlyProbe(Protocol):
    probe_id: str
    environment_id: str
    substrate: str

    def sample(self, observer_id: str) -> Mapping[str, Any]: ...


class FilesystemProbe:
    substrate = "filesystem"

    def __init__(self, root: Path | str, *, environment_id: str = "env://filesystem/local",
                 probe_id: str = "probe://filesystem/root") -> None:
        self.root = Path(root).resolve()
        self.environment_id = environment_id
        self.probe_id = probe_id

    def sample(self, observer_id: str) -> Mapping[str, Any]:
        if not self.root.exists():
            return {"root": str(self.root), "exists": False, "entries": []}
        entries = []
        for child in sorted(self.root.iterdir(), key=lambda p: p.name):
            try:
                st = child.stat()
                entries.append({
                    "name": child.name,
                    "kind": "dir" if child.is_dir() else "file",
                    "size": st.st_size,
                    "mtime_ns": st.st_mtime_ns,
                })
            except OSError as exc:
                entries.append({"name": child.name, "status": "UNREADABLE", "error": str(exc)})
        return {"root": str(self.root), "exists": True, "entries": entries}


class ProcessProbe:
    substrate = "process"

    def __init__(self, *, environment_id: str = "env://process/local",
                 probe_id: str = "probe://process/self") -> None:
        self.environment_id = environment_id
        self.probe_id = probe_id

    def sample(self, observer_id: str) -> Mapping[str, Any]:
        return {
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "cwd": os.getcwd(),
            "python": os.sys.version.split()[0],
        }


class GitRepositoryProbe:
    substrate = "git"

    def __init__(self, repo: Path | str, *, environment_id: str = "env://repository/local",
                 probe_id: str = "probe://git/repository") -> None:
        self.repo = Path(repo).resolve()
        self.environment_id = environment_id
        self.probe_id = probe_id

    def _git(self, *args: str) -> str:
        cp = subprocess.run(
            ["git", "-C", str(self.repo), *args], check=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True
        )
        return cp.stdout.strip()

    def sample(self, observer_id: str) -> Mapping[str, Any]:
        return {
            "repo": str(self.repo),
            "head": self._git("rev-parse", "HEAD"),
            "branch": self._git("rev-parse", "--abbrev-ref", "HEAD"),
            "status_porcelain": self._git("status", "--porcelain=v1"),
        }


class HttpProjectionProbe:
    substrate = "http"

    def __init__(self, url: str, *, environment_id: str,
                 probe_id: str = "probe://http/projection", timeout: float = 3.0) -> None:
        self.url = url
        self.environment_id = environment_id
        self.probe_id = probe_id
        self.timeout = timeout

    def sample(self, observer_id: str) -> Mapping[str, Any]:
        req = urllib.request.Request(self.url, method="GET", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read()
            return {
                "url": self.url,
                "status": resp.status,
                "content_type": resp.headers.get("Content-Type"),
                "body_sha256": sha256(raw).hexdigest(),
                "body": json.loads(raw.decode("utf-8")) if "json" in (resp.headers.get("Content-Type") or "") else raw.decode("utf-8", "replace"),
            }


class CallableProbe:
    """Adapter for resident environment samplers without giving them mutation authority."""

    def __init__(self, fn: Callable[[], Mapping[str, Any]], *, environment_id: str,
                 substrate: str, probe_id: str) -> None:
        self.fn = fn
        self.environment_id = environment_id
        self.substrate = substrate
        self.probe_id = probe_id

    def sample(self, observer_id: str) -> Mapping[str, Any]:
        return dict(self.fn())


class EnvironmentFederation:
    """Read-only federation of substrate-specific probes under one Observer² identity."""

    def __init__(self, observer_id: str = "observer2://federated/r29") -> None:
        self.observer_id = observer_id
        self._probes: Dict[str, ReadOnlyProbe] = {}
        self._logical_time = 0

    def register(self, probe: ReadOnlyProbe) -> None:
        if probe.probe_id in self._probes:
            raise ValueError(f"duplicate probe_id: {probe.probe_id}")
        if any(callable(getattr(probe, name, None)) for name in ("write", "mutate", "delete", "commit", "actuate")):
            raise TypeError(f"probe exposes mutation surface: {probe.probe_id}")
        self._probes[probe.probe_id] = probe

    def probe_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._probes))

    def sample(self, continuation: Optional[Mapping[str, Any]] = None) -> FederatedFrame:
        self._logical_time += 1
        receipts: list[ProbeReceipt] = []
        for probe_id in sorted(self._probes):
            p = self._probes[probe_id]
            try:
                payload = p.sample(self.observer_id)
                receipts.append(ProbeReceipt.make(
                    observer_id=self.observer_id, environment_id=p.environment_id,
                    probe_id=p.probe_id, substrate=p.substrate,
                    status="OBSERVED", payload=payload,
                ))
            except Exception as exc:
                receipts.append(ProbeReceipt.make(
                    observer_id=self.observer_id, environment_id=p.environment_id,
                    probe_id=p.probe_id, substrate=p.substrate,
                    status="UNAVAILABLE", payload={"exception_type": type(exc).__name__}, error=str(exc),
                ))

        root_material = [
            {
                "environment_id": r.environment_id,
                "probe_id": r.probe_id,
                "substrate": r.substrate,
                "status": r.status,
                "payload_sha256": r.payload_sha256,
                "error": r.error,
            }
            for r in receipts
        ]
        return FederatedFrame(
            observer_id=self.observer_id,
            logical_time=self._logical_time,
            receipts=tuple(receipts),
            environment_root_sha256=_digest(root_material),
            continuation=dict(continuation or {}),
        )


class Observer2Runtime:
    """
    Observer² runtime with a federation sampler and a compatible single-root mode.

    The observer produces evidence only. No actuator is reachable from this object.
    """

    def __init__(self, *, federation: Optional[EnvironmentFederation] = None,
                 root: Optional[Path | str] = None,
                 observer_id: str = "observer2://runtime/r29") -> None:
        if federation is None and root is None:
            raise ValueError("federation or root required")
        if federation is not None and root is not None:
            raise ValueError("choose federation or root, not both")
        if federation is None:
            federation = EnvironmentFederation(observer_id=observer_id)
            federation.register(FilesystemProbe(root, environment_id="env://legacy-root", probe_id="probe://legacy-root"))
        self.federation = federation

    def observe(self, continuation: Optional[Mapping[str, Any]] = None) -> FederatedFrame:
        return self.federation.sample(continuation=continuation)
