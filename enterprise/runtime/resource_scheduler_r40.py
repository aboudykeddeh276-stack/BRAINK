from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json
import os
import shutil
import tempfile
import threading


@dataclass(frozen=True)
class ResourceVector:
    cpu_units: int = 0
    memory_bytes: int = 0
    storage_bytes: int = 0
    gpu_units: int = 0
    network_mbps: int = 0

    def validate(self) -> None:
        if min(self.cpu_units, self.memory_bytes, self.storage_bytes, self.gpu_units, self.network_mbps) < 0:
            raise ValueError("NEGATIVE_RESOURCE_REQUIREMENT")


@dataclass(frozen=True)
class ResourceRequirement:
    minimum: ResourceVector
    target: ResourceVector
    maximum: ResourceVector
    priority: int = 50
    latency_class: str = "STANDARD"
    persistence_required: bool = True

    def validate(self) -> None:
        self.minimum.validate(); self.target.validate(); self.maximum.validate()
        for field in ResourceVector.__dataclass_fields__:
            lo = getattr(self.minimum, field); target = getattr(self.target, field); hi = getattr(self.maximum, field)
            if not (lo <= target <= hi):
                raise ValueError(f"RESOURCE_RANGE_INVALID:{field}")
        if not 0 <= self.priority <= 100:
            raise ValueError("RESOURCE_PRIORITY_OUT_OF_RANGE")


@dataclass(frozen=True)
class ResourceEnvelope:
    node_id: str
    granted: ResourceVector
    priority: int
    latency_class: str
    persistence_required: bool
    enforcement: str

    def to_dict(self) -> dict[str, Any]:
        body = asdict(self); body["granted"] = asdict(self.granted); return body

    @classmethod
    def from_dict(cls, body: dict[str, Any]) -> "ResourceEnvelope":
        return cls(
            node_id=str(body["node_id"]), granted=ResourceVector(**body["granted"]),
            priority=int(body["priority"]), latency_class=str(body["latency_class"]),
            persistence_required=bool(body["persistence_required"]), enforcement=str(body["enforcement"]),
        )


class PhysicalResourceScheduler:
    """Persistent admission/accounting scheduler. Hard host quotas remain adapter-owned and are not claimed here."""

    SCHEMA = "braink.resource-scheduler.r40/v1"

    def __init__(self, pool: ResourceVector, state_path: str | Path | None = None):
        pool.validate(); self.pool = pool; self.state_path = None if state_path is None else Path(state_path)
        self.allocations: dict[str, ResourceEnvelope] = {}; self._lock = threading.RLock()
        if self.state_path is not None:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self._restore()

    @classmethod
    def probe_host(cls, state_root: str | Path) -> "PhysicalResourceScheduler":
        cpu = int(os.cpu_count() or 1)
        try:
            memory = int(os.sysconf("SC_PHYS_PAGES")) * int(os.sysconf("SC_PAGE_SIZE"))
        except (ValueError, OSError, AttributeError):
            memory = int(os.environ.get("BRAINK_MEMORY_BYTES", "0"))
        storage = shutil.disk_usage(Path(state_root)).free
        gpu = int(os.environ.get("BRAINK_GPU_UNITS", "0"))
        network = int(os.environ.get("BRAINK_NETWORK_MBPS", "0"))
        return cls(ResourceVector(cpu, memory, storage, gpu, network), Path(state_root) / "control" / "resource-scheduler-r40.json")

    def _restore(self) -> None:
        if self.state_path is None or not self.state_path.exists(): return
        body = json.loads(self.state_path.read_text(encoding="utf-8"))
        if body.get("schema") != self.SCHEMA: raise RuntimeError("RESOURCE_SCHEDULER_SCHEMA_MISMATCH")
        allocations = body.get("allocations", {})
        if not isinstance(allocations, dict): raise RuntimeError("RESOURCE_SCHEDULER_STATE_INVALID")
        restored = {str(node_id): ResourceEnvelope.from_dict(value) for node_id, value in allocations.items()}
        for node_id, envelope in restored.items():
            if envelope.node_id != node_id: raise RuntimeError("RESOURCE_SCHEDULER_NODE_ID_MISMATCH")
            envelope.granted.validate()
        self.allocations = restored

    def _persist(self) -> None:
        if self.state_path is None: return
        body = {"schema": self.SCHEMA, "allocations": {k: v.to_dict() for k, v in sorted(self.allocations.items())}}
        raw = (json.dumps(body, indent=2, sort_keys=True) + "\n").encode("utf-8")
        fd, tmp_name = tempfile.mkstemp(prefix=self.state_path.name + ".", dir=self.state_path.parent)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(raw); fh.flush(); os.fsync(fh.fileno())
            os.replace(tmp_name, self.state_path)
            dir_fd = os.open(self.state_path.parent, os.O_RDONLY)
            try: os.fsync(dir_fd)
            finally: os.close(dir_fd)
        finally:
            if os.path.exists(tmp_name): os.unlink(tmp_name)

    def _used(self) -> ResourceVector:
        values = {field: 0 for field in ResourceVector.__dataclass_fields__}
        for envelope in self.allocations.values():
            for field in values: values[field] += getattr(envelope.granted, field)
        return ResourceVector(**values)

    def available(self) -> ResourceVector:
        used = self._used()
        return ResourceVector(**{field: max(0, getattr(self.pool, field) - getattr(used, field)) for field in ResourceVector.__dataclass_fields__})

    def allocate(self, node_id: str, requirement: ResourceRequirement) -> ResourceEnvelope:
        requirement.validate(); node_id = str(node_id).strip()
        if not node_id: raise ValueError("NODE_ID_REQUIRED")
        with self._lock:
            if node_id in self.allocations: return self.allocations[node_id]
            available = self.available(); grant = {}
            for field in ResourceVector.__dataclass_fields__:
                lo = getattr(requirement.minimum, field); target = getattr(requirement.target, field); free = getattr(available, field)
                if free < lo: raise RuntimeError(f"RESOURCE_BLOCKED:{field}:required={lo}:available={free}")
                grant[field] = min(target, free)
            envelope = ResourceEnvelope(node_id, ResourceVector(**grant), requirement.priority, requirement.latency_class, requirement.persistence_required, "ACCOUNTING_ENVELOPE")
            self.allocations[node_id] = envelope
            try: self._persist()
            except Exception:
                self.allocations.pop(node_id, None)
                raise
            return envelope

    def release(self, node_id: str) -> bool:
        with self._lock:
            previous = self.allocations.pop(node_id, None)
            if previous is None: return False
            try: self._persist()
            except Exception:
                self.allocations[node_id] = previous
                raise
            return True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "pool": asdict(self.pool), "available": asdict(self.available()),
                "allocations": {node_id: envelope.to_dict() for node_id, envelope in sorted(self.allocations.items())},
                "state_path": None if self.state_path is None else str(self.state_path),
                "enforcement_boundary": "ACCOUNTING_ENVELOPE_ONLY; host-specific hard quota enforcement requires an adapter and is not claimed here.",
            }
