from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

SCHEMA = "braink.gcs-content-replica.r40/v1"

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _segment(value: str) -> str:
    value = str(value).strip()
    if not value or value in {".", ".."} or "/" in value or "\\" in value or "\x00" in value:
        raise ValueError("INVALID_SEGMENT")
    return value

@dataclass(frozen=True)
class ReplicaReceipt:
    schema: str
    bucket: str
    namespace: str
    kind: str
    sha256: str
    bytes: int
    relative_object: str
    gs_uri: str
    local_mount_path: str
    state: str = "REPLICATED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

class ContentAddressedGCSReplica:
    """Write-once content-addressed replica target over a mounted GCS bucket.

    This is deliberately not a canonical ledger, database, or POSIX authority.
    Local canonical state is committed first; this target receives immutable
    replicas keyed by content hash.
    """

    def __init__(self, *, mount_root: str | os.PathLike[str], bucket: str, namespace: str = "braink-r40",
                 require_mount: bool = True):
        self.mount_root = Path(mount_root).expanduser()
        self.bucket = _segment(bucket)
        self.namespace = _segment(namespace)
        self.require_mount = bool(require_mount)
        self.mount_root.mkdir(parents=True, exist_ok=True)
        if self.require_mount and not self._is_mountpoint():
            raise RuntimeError(f"BLOCKED:GCSFUSE_NOT_MOUNTED:{self.mount_root}")

    def _is_mountpoint(self) -> bool:
        if os.path.ismount(self.mount_root):
            return True
        try:
            resolved = self.mount_root.resolve()
            for line in Path("/proc/mounts").read_text(encoding="utf-8").splitlines():
                fields = line.split()
                if len(fields) >= 3 and Path(fields[1]).resolve() == resolved:
                    return "fuse" in fields[2].lower() or "gcs" in fields[2].lower()
        except Exception:
            pass
        return False

    def probe(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "mount_root": str(self.mount_root),
            "bucket": self.bucket,
            "namespace": self.namespace,
            "is_mountpoint": self._is_mountpoint(),
            "authority": "REPLICA_ONLY",
            "capacity_model": "CLOUD_OBJECT_STORAGE_NO_FIXED_VOLUME_CAPACITY_CLAIM",
            "semantics": "WRITE_ONCE_CONTENT_ADDRESSED_OBJECTS",
        }

    def _target(self, kind: str, digest: str) -> tuple[Path, str]:
        kind = _segment(kind)
        rel = Path(self.namespace) / "objects" / kind / "sha256" / digest[:2] / digest
        return self.mount_root / rel, rel.as_posix()

    def put_bytes(self, *, kind: str, payload: bytes | bytearray | memoryview) -> ReplicaReceipt:
        data = bytes(payload)
        digest = _sha256_bytes(data)
        target, rel = self._target(kind, digest)
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            observed = target.read_bytes()
            if _sha256_bytes(observed) != digest:
                raise RuntimeError(f"FAILED:REPLICA_EXISTING_OBJECT_HASH_MISMATCH:{rel}")
        else:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            fd = os.open(target, flags, 0o600)
            try:
                with os.fdopen(fd, "wb", closefd=False) as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
            finally:
                os.close(fd)

        observed = target.read_bytes()
        if observed != data or _sha256_bytes(observed) != digest:
            raise RuntimeError(f"FAILED:REPLICA_READBACK_MISMATCH:{rel}")

        return ReplicaReceipt(
            schema=SCHEMA,
            bucket=self.bucket,
            namespace=self.namespace,
            kind=_segment(kind),
            sha256=digest,
            bytes=len(data),
            relative_object=rel,
            gs_uri=f"gs://{self.bucket}/{rel}",
            local_mount_path=str(target),
        )

    def put_json(self, *, kind: str, value: Any) -> ReplicaReceipt:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return self.put_bytes(kind=kind, payload=payload)

    def replicate_file(self, *, kind: str, source_path: str | os.PathLike[str]) -> ReplicaReceipt:
        path = Path(source_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        return self.put_bytes(kind=kind, payload=path.read_bytes())

    def verify(self, receipt: ReplicaReceipt | dict[str, Any]) -> dict[str, Any]:
        record = receipt if isinstance(receipt, ReplicaReceipt) else ReplicaReceipt(**receipt)
        if record.bucket != self.bucket or record.namespace != self.namespace:
            return {"status": "FAILED:REPLICA_SCOPE_MISMATCH"}
        target = self.mount_root / record.relative_object
        if not target.is_file():
            return {"status": "FAILED:REPLICA_OBJECT_MISSING", "gs_uri": record.gs_uri}
        data = target.read_bytes()
        observed = _sha256_bytes(data)
        if observed != record.sha256 or len(data) != record.bytes:
            return {"status": "FAILED:REPLICA_HASH_MISMATCH", "expected": record.sha256, "observed": observed}
        return {"status": "VERIFIED", "gs_uri": record.gs_uri, "sha256": observed, "bytes": len(data)}
