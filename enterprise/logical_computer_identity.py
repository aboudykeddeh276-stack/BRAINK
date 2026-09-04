from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import shutil
import time


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class LogicalComputerIdentity:
    logical_id: str
    constructor_id: str
    lineage: tuple[str, ...]
    authority_id: str
    created_ns: int


@dataclass(frozen=True)
class MachineProjection:
    projection_id: str
    host_fingerprint: str
    platform: str
    carrier: str


class LogicalComputerController:
    """Host-independent logical identity over a machine-specific projection.

    Logical identity is derived only from stable logical material. Machine/host/carrier
    data is persisted separately as a replaceable projection. This layer deliberately
    does not redefine R26 state; it binds an existing recursive computer state root to
    a host-independent identity and records migrations as evidence.
    """

    SCHEMA = "braink.logical-computer.identity.v1"
    CONSTRUCTOR_ID = "constructor://braink/logical-computer/r1"

    def __init__(self, state_root: str | Path):
        self.state_root = Path(state_root)
        self.identity_path = self.state_root / "logical-computer.json"
        self.projection_path = self.state_root / "machine-projection.json"
        self.receipts_path = self.state_root / "logical-computer-receipts.jsonl"

    @classmethod
    def create(
        cls,
        state_root: str | Path,
        *,
        lineage: tuple[str, ...],
        authority_id: str,
        projection: MachineProjection,
    ) -> "LogicalComputerController":
        self = cls(state_root)
        self.state_root.mkdir(parents=True, exist_ok=True)
        if self.identity_path.exists():
            raise RuntimeError("LOGICAL_IDENTITY_ALREADY_EXISTS")
        stable = {
            "constructor_id": cls.CONSTRUCTOR_ID,
            "lineage": list(lineage),
            "authority_id": authority_id,
        }
        logical_id = "BRAINK-LOGICAL-" + _sha256(stable)[:24]
        identity = LogicalComputerIdentity(
            logical_id=logical_id,
            constructor_id=cls.CONSTRUCTOR_ID,
            lineage=tuple(lineage),
            authority_id=authority_id,
            created_ns=time.time_ns(),
        )
        self._durable_json(self.identity_path, {"schema": cls.SCHEMA, "identity": asdict(identity)})
        self._durable_json(self.projection_path, asdict(projection))
        self._append_receipt("LOGICAL_COMPUTER_CREATED", projection=projection, proof={"logical_material_hash": _sha256(stable)})
        return self

    def read_identity(self) -> LogicalComputerIdentity:
        payload = json.loads(self.identity_path.read_text("utf-8"))
        if payload.get("schema") != self.SCHEMA:
            raise RuntimeError("LOGICAL_IDENTITY_SCHEMA_MISMATCH")
        i = payload["identity"]
        identity = LogicalComputerIdentity(
            logical_id=i["logical_id"], constructor_id=i["constructor_id"],
            lineage=tuple(i["lineage"]), authority_id=i["authority_id"], created_ns=int(i["created_ns"])
        )
        stable = {"constructor_id": identity.constructor_id, "lineage": list(identity.lineage), "authority_id": identity.authority_id}
        expected = "BRAINK-LOGICAL-" + _sha256(stable)[:24]
        if identity.logical_id != expected:
            raise RuntimeError("LOGICAL_IDENTITY_INTEGRITY_MISMATCH")
        return identity

    def read_projection(self) -> MachineProjection:
        p = json.loads(self.projection_path.read_text("utf-8"))
        return MachineProjection(**p)

    def bind_projection(self, projection: MachineProjection) -> dict[str, Any]:
        before = self.read_projection() if self.projection_path.exists() else None
        identity = self.read_identity()
        self._durable_json(self.projection_path, asdict(projection))
        after_identity = self.read_identity()
        if after_identity.logical_id != identity.logical_id:
            raise RuntimeError("LOGICAL_IDENTITY_CHANGED_DURING_PROJECTION_BIND")
        return self._append_receipt(
            "MACHINE_PROJECTION_REBOUND",
            projection=projection,
            proof={
                "logical_id_unchanged": True,
                "previous_projection_id": before.projection_id if before else None,
                "new_projection_id": projection.projection_id,
            },
        )

    def migrate_to(self, destination_root: str | Path, *, new_projection: MachineProjection) -> "LogicalComputerController":
        destination_root = Path(destination_root)
        if destination_root.exists() and any(destination_root.iterdir()):
            raise RuntimeError("MIGRATION_DESTINATION_NOT_EMPTY")
        source_identity = self.read_identity()
        source_projection = self.read_projection()
        shutil.copytree(self.state_root, destination_root, dirs_exist_ok=True)
        migrated = LogicalComputerController(destination_root)
        copied_identity = migrated.read_identity()
        if copied_identity.logical_id != source_identity.logical_id:
            raise RuntimeError("MIGRATION_LOGICAL_IDENTITY_MISMATCH")
        migrated.bind_projection(new_projection)
        final_identity = migrated.read_identity()
        if final_identity.logical_id != source_identity.logical_id:
            raise RuntimeError("POST_MIGRATION_LOGICAL_IDENTITY_MISMATCH")
        migrated._append_receipt(
            "LOGICAL_COMPUTER_MIGRATED",
            projection=new_projection,
            proof={
                "logical_id_unchanged": True,
                "source_projection_id": source_projection.projection_id,
                "destination_projection_id": new_projection.projection_id,
                "source_state_digest": self.state_digest(),
                "destination_state_digest": migrated.state_digest(),
            },
        )
        if self.state_digest() != migrated.state_digest():
            raise RuntimeError("MIGRATION_STATE_DIGEST_MISMATCH")
        return migrated

    def state_digest(self) -> str:
        excluded = {self.projection_path.name, self.receipts_path.name}
        entries = []
        for p in sorted(self.state_root.rglob("*")):
            if not p.is_file() or p.name in excluded:
                continue
            rel = p.relative_to(self.state_root).as_posix()
            entries.append({"path": rel, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
        return _sha256(entries)

    def _append_receipt(self, operation: str, *, projection: MachineProjection, proof: dict[str, Any]) -> dict[str, Any]:
        receipt = {
            "schema": "braink.logical-computer.receipt.v1",
            "operation": operation,
            "logical_id": self.read_identity().logical_id,
            "projection": asdict(projection),
            "proof": proof,
            "recorded_ns": time.time_ns(),
        }
        self.receipts_path.parent.mkdir(parents=True, exist_ok=True)
        with self.receipts_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")
            fh.flush(); os.fsync(fh.fileno())
        return receipt

    @staticmethod
    def _durable_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", "utf-8")
        fd = os.open(tmp, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
        os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
