from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import os
import shutil
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


class PhysicalResourceScheduler:
    """Admission/accounting scheduler. It does not falsely claim OS/GPU hard quotas."""

    def __init__(self, pool: ResourceVector):
        pool.validate(); self.pool = pool; self.allocations: dict[str, ResourceEnvelope] = {}; self._lock = threading.RLock()

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
        return cls(ResourceVector(cpu, memory, storage, gpu, network))

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
            return envelope

    def release(self, node_id: str) -> bool:
        with self._lock: return self.allocations.pop(node_id, None) is not None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "pool": asdict(self.pool),
                "available": asdict(self.available()),
                "allocations": {node_id: envelope.to_dict() for node_id, envelope in sorted(self.allocations.items())},
                "enforcement_boundary": "ACCOUNTING_ENVELOPE_ONLY; host-specific hard quota enforcement requires an adapter and is not claimed here.",
            }
