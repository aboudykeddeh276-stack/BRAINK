from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Mapping, Any
import hashlib, json, os

ZEROLESS = (-3,-2,1,2,3)
BLOCK_SIZE = 4096
SUPERBLOCK_SLOT = 0
BRAINK_ROOT_SLOT = 256
SERVICE_ROOT_SLOT = 768
MUTATION_SLOT = 1024

class BrainkError(RuntimeError): pass
class IntegrityError(BrainkError): pass
class AuthorityError(BrainkError): pass
class StateConflict(BrainkError): pass

def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

@dataclass(frozen=True)
class ObjectEnvelope:
    object_id: str
    object_type: str
    lexical_id: str
    lineage_id: str
    revision: int
    payload: Mapping[str, Any]
    payload_sha256: str

    @classmethod
    def create(cls, *, object_id: str, object_type: str, lexical_id: str,
               lineage_id: str, revision: int, payload: Mapping[str, Any]):
        digest = sha256(canonical_bytes(payload))
        return cls(object_id, object_type, lexical_id, lineage_id, revision, dict(payload), digest)

    def verify(self) -> None:
        if sha256(canonical_bytes(self.payload)) != self.payload_sha256:
            raise IntegrityError(f"payload digest mismatch: {self.object_id}")

@dataclass(frozen=True)
class MachineIdentity:
    machine_id: str
    braink_id: str
    lineage_root: str
    parent_machine: str | None = None
    parent_braink: str | None = None

@dataclass(frozen=True)
class BrainkRoot:
    identity: MachineIdentity
    medium_root: str
    controller_root: str
    storage_root: str
    vfs_root: str
    vfs_role: str
    network_root: str
    vector_root: str
    observer_root: str
    proof_root: str
    zero_less_geometry: tuple[int, ...] = ZEROLESS

    def validate(self) -> None:
        if self.vfs_role != "RESOLVER_ONLY":
            raise IntegrityError("VFS cannot be promoted to storage-medium authority")
        if tuple(self.zero_less_geometry) != ZEROLESS:
            raise IntegrityError("zero-less geometry contract violation")

class StorageController(Protocol):
    def read_object(self, slot: int) -> dict[str, Any] | None: ...
    def write_object(self, slot: int, value: Mapping[str, Any]) -> str: ...
    def sync(self) -> None: ...

class BlockFileController:
    """Materialised carrier for encoded machine state; carrier bytes are not logical BRAINK capacity."""
    def __init__(self, path: Path, *, disk_bytes: int = 64*1024*1024, create: bool = False):
        self.path = Path(path)
        flags = os.O_RDWR | (os.O_CREAT | os.O_TRUNC if create else 0)
        self.fd = os.open(self.path, flags, 0o644)
        if create:
            os.ftruncate(self.fd, disk_bytes)

    def close(self):
        if self.fd is not None:
            os.close(self.fd); self.fd = None
    def __enter__(self): return self
    def __exit__(self, *exc): self.close()

    def read_object(self, slot: int):
        off = slot * BLOCK_SIZE
        head = os.pread(self.fd, 8, off)
        if len(head) < 8: return None
        n = int.from_bytes(head[:4], "big")
        if n == 0: return None
        if n > BLOCK_SIZE-8: raise IntegrityError(f"invalid block length at slot {slot}")
        raw = os.pread(self.fd, n, off+8)
        if len(raw) != n: raise IntegrityError(f"short read at slot {slot}")
        return {"value": json.loads(raw.decode()), "sha256": sha256(raw)}

    def write_object(self, slot: int, value: Mapping[str, Any]) -> str:
        raw = canonical_bytes(value)
        if len(raw) > BLOCK_SIZE-8: raise BrainkError("E_BLOCK_TOO_LARGE")
        buf = bytearray(BLOCK_SIZE)
        buf[:4] = len(raw).to_bytes(4, "big")
        buf[8:8+len(raw)] = raw
        os.pwrite(self.fd, bytes(buf), slot*BLOCK_SIZE)
        return sha256(raw)

    def sync(self): os.fsync(self.fd)

@dataclass(frozen=True)
class ServiceDescriptor:
    object_type: str
    lexical_id: str
    vector_id: str
    route_id: str
    adapter_id: str
    authority_class: str

@dataclass
class ServiceFabric:
    machine: MachineIdentity
    services: dict[str, ServiceDescriptor]
    def resolve(self, lexical_id: str) -> ServiceDescriptor:
        hits = [v for v in self.services.values() if v.lexical_id == lexical_id]
        if len(hits) != 1:
            raise BrainkError(f"semantic resolution expected exactly one hit: {lexical_id}")
        return hits[0]

class AuthorityPort(Protocol):
    authority_class: str
    def observe(self, target: str) -> Mapping[str, Any]: ...
    def mutate(self, target: str, operation: Mapping[str, Any]) -> Mapping[str, Any]: ...

class ReadOnlyBoundaryPort:
    def __init__(self, authority_class: str, observer):
        self.authority_class = authority_class
        self._observer = observer
    def observe(self, target: str): return self._observer(target)
    def mutate(self, target: str, operation: Mapping[str, Any]):
        raise AuthorityError(f"{self.authority_class} mutation authority not installed")

class Replicator:
    @staticmethod
    def replicate(envelope: ObjectEnvelope, destination_lineage: str) -> ObjectEnvelope:
        envelope.verify()
        return ObjectEnvelope(envelope.object_id, envelope.object_type, envelope.lexical_id,
                              destination_lineage, envelope.revision, dict(envelope.payload), envelope.payload_sha256)

class Reconciler:
    @staticmethod
    def reconcile(local: ObjectEnvelope, remote: ObjectEnvelope) -> ObjectEnvelope:
        local.verify(); remote.verify()
        if local.object_id != remote.object_id or local.object_type != remote.object_type:
            raise StateConflict("cannot reconcile different canonical objects")
        if remote.revision < local.revision:
            raise StateConflict("remote revision is stale")
        return ObjectEnvelope(local.object_id, local.object_type, local.lexical_id, local.lineage_id,
                              remote.revision, dict(remote.payload), remote.payload_sha256)
