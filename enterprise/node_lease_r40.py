from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import hashlib
import json
import time

from enterprise.node_vfs_r40 import NodeVFS


LEASE_SCHEMA = "braink.node-lease.r40/v1"
LEASE_INDEX_SCHEMA = "braink.node-lease-index.r40/v1"
LIFECYCLE = ("ALLOCATED", "LIVE", "QUIESCING", "TOMBSTONED", "RECLAIMED")
_ALLOWED_TRANSITIONS = {
    "ALLOCATED": {"LIVE"},
    "LIVE": {"QUIESCING"},
    "QUIESCING": {"TOMBSTONED"},
    "TOMBSTONED": {"RECLAIMED"},
    "RECLAIMED": set(),
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _semantic_body(value: dict[str, Any]) -> dict[str, Any]:
    # Host observation time is deliberately excluded from deterministic lease identity.
    return {k: v for k, v in value.items() if k not in {"semantic_root", "observed_at_ns"}}


def semantic_root(value: dict[str, Any]) -> str:
    return digest(_semantic_body(value))


@dataclass(frozen=True)
class LeaseAuthorityRecord:
    schema: str
    lease_id: str
    owner_node_id: str
    logical_identity: str
    target_node_id: str
    target_vfs_root: str
    authority: str
    capabilities: tuple[str, ...]
    generation: int
    lifecycle_state: str
    acquired_sequence: int
    expires_sequence: int | None
    active_readers: int
    previous_lease_root: str | None
    backing_disposition: str
    observed_at_ns: int
    semantic_root: str

    def to_dict(self) -> dict[str, Any]:
        body = asdict(self)
        body["capabilities"] = list(self.capabilities)
        return body


class NodeLeaseRegistryR40:
    """Durable Ring-1 allocation authority layered on the resident node VFS.

    The lease owns allocation/routing authority only. It does not create nodes,
    mutate BRAINK state directly, replace capability/authority systems, or claim
    secure physical erasure. `RECLAIMED` means the logical allocation may be
    acquired by a later generation; tombstone evidence remains persisted.

    Correctness uses deterministic ledger/event sequence values supplied by the
    caller. `observed_at_ns` is operational telemetry and is excluded from the
    semantic root, so wall-clock time cannot change replay identity.
    """

    def __init__(self, vfs: NodeVFS, owner_node_id: str):
        self.vfs = vfs
        self.owner_node_id = str(owner_node_id)

    @staticmethod
    def _record_path(logical_identity: str) -> str:
        return "leases/" + digest(str(logical_identity)) + ".json"

    @staticmethod
    def _lease_id(owner_node_id: str, logical_identity: str) -> str:
        return "LEASE-" + digest({"owner_node_id": owner_node_id, "logical_identity": str(logical_identity)})[:24]

    def _read_cell(self, logical_path: str) -> tuple[dict[str, Any] | None, str | None]:
        cell = self.vfs.read(self.owner_node_id, logical_path)
        result = cell["result"]
        if result.get("status") == "HOLE":
            return None, None
        value = result.get("value")
        if not isinstance(value, dict):
            raise RuntimeError("LEASE_CELL_NOT_OBJECT")
        return value, result.get("value_hash")

    def _verify_record(self, body: dict[str, Any]) -> None:
        if body.get("schema") != LEASE_SCHEMA:
            raise RuntimeError("LEASE_SCHEMA_MISMATCH")
        if body.get("lifecycle_state") not in LIFECYCLE:
            raise RuntimeError("LEASE_STATE_INVALID")
        if int(body.get("generation", 0)) < 1:
            raise RuntimeError("LEASE_GENERATION_INVALID")
        if int(body.get("active_readers", -1)) < 0:
            raise RuntimeError("LEASE_READER_COUNT_INVALID")
        if body.get("semantic_root") != semantic_root(body):
            raise RuntimeError("LEASE_SEMANTIC_ROOT_MISMATCH")

    def read(self, logical_identity: str) -> dict[str, Any] | None:
        body, _ = self._read_cell(self._record_path(logical_identity))
        if body is None:
            return None
        self._verify_record(body)
        return body

    def _commit(self, logical_identity: str, body: dict[str, Any], expected_hash: str | None) -> dict[str, Any]:
        body = dict(body)
        body["semantic_root"] = semantic_root(body)
        result = self.vfs.cas_write(self.owner_node_id, self._record_path(logical_identity), body, expected_hash)
        if result["result"].get("status") == "CONFLICT":
            return {"status": "BLOCKED:LEASE_CONCURRENT_WRITE", "detail": result["result"]}
        self._verify_record(body)
        return {"status": "COMMITTED", "lease": body, "cell": result}

    def _index_add(self, record: dict[str, Any]) -> None:
        for _ in range(8):
            current, expected_hash = self._read_cell("leases/index.json")
            if current is None:
                current = {"schema": LEASE_INDEX_SCHEMA, "leases": {}}
            if current.get("schema") != LEASE_INDEX_SCHEMA or not isinstance(current.get("leases"), dict):
                raise RuntimeError("LEASE_INDEX_INVALID")
            updated = {"schema": LEASE_INDEX_SCHEMA, "leases": dict(current["leases"])}
            updated["leases"][record["lease_id"]] = {
                "logical_identity": record["logical_identity"],
                "record_path": self._record_path(record["logical_identity"]),
            }
            attempt = self.vfs.cas_write(self.owner_node_id, "leases/index.json", updated, expected_hash)
            if attempt["result"].get("status") == "COMMITTED":
                return
        raise RuntimeError("LEASE_INDEX_CONCURRENT_WRITE_EXHAUSTED")

    def acquire(
        self,
        *,
        logical_identity: str,
        target_node_id: str,
        authority: str,
        capabilities: list[str] | tuple[str, ...],
        current_sequence: int,
        ttl_events: int | None = None,
    ) -> dict[str, Any]:
        logical_identity = str(logical_identity).strip()
        target_node_id = str(target_node_id).strip()
        if not logical_identity:
            return {"status": "BLOCKED:LEASE_LOGICAL_IDENTITY_REQUIRED"}
        if not target_node_id:
            return {"status": "BLOCKED:LEASE_TARGET_NODE_REQUIRED"}
        if not str(authority).startswith("authority://"):
            return {"status": "BLOCKED:LEASE_AUTHORITY_INVALID"}
        capability_set = tuple(sorted(set(str(x).strip() for x in capabilities if str(x).strip())))
        if not capability_set:
            return {"status": "BLOCKED:LEASE_CAPABILITY_MANIFEST_REQUIRED"}
        if ttl_events is not None and int(ttl_events) <= 0:
            return {"status": "BLOCKED:LEASE_TTL_EVENTS_INVALID"}

        record_path = self._record_path(logical_identity)
        current, expected_hash = self._read_cell(record_path)
        previous_root = None
        generation = 1
        if current is not None:
            self._verify_record(current)
            if current["lifecycle_state"] != "RECLAIMED":
                status = "LEASE_ACTIVE" if current["lifecycle_state"] in {"ALLOCATED", "LIVE"} else "LEASE_LOCKED_" + current["lifecycle_state"]
                return {"status": "BLOCKED:" + status, "lease": current}
            generation = int(current["generation"]) + 1
            previous_root = current["semantic_root"]

        allocated = {
            "schema": LEASE_SCHEMA,
            "lease_id": self._lease_id(self.owner_node_id, logical_identity),
            "owner_node_id": self.owner_node_id,
            "logical_identity": logical_identity,
            "target_node_id": target_node_id,
            "target_vfs_root": f"vfs://node/{target_node_id}/",
            "authority": str(authority),
            "capabilities": list(capability_set),
            "generation": generation,
            "lifecycle_state": "ALLOCATED",
            "acquired_sequence": int(current_sequence),
            "expires_sequence": None if ttl_events is None else int(current_sequence) + int(ttl_events),
            "active_readers": 0,
            "previous_lease_root": previous_root,
            "backing_disposition": "PRESERVE_AUDIT_EVIDENCE",
            "observed_at_ns": time.time_ns(),
        }
        committed = self._commit(logical_identity, allocated, expected_hash)
        if committed["status"] != "COMMITTED":
            return committed
        self._index_add(committed["lease"])
        return self.transition(
            logical_identity,
            to_state="LIVE",
            current_sequence=current_sequence,
            expected_generation=generation,
        )

    def transition(
        self,
        logical_identity: str,
        *,
        to_state: str,
        current_sequence: int,
        expected_generation: int | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        current, expected_hash = self._read_cell(self._record_path(logical_identity))
        if current is None:
            return {"status": "BLOCKED:LEASE_NOT_FOUND"}
        self._verify_record(current)
        if expected_generation is not None and int(current["generation"]) != int(expected_generation):
            return {"status": "BLOCKED:LEASE_STALE_GENERATION", "lease": current}
        from_state = current["lifecycle_state"]
        if to_state not in _ALLOWED_TRANSITIONS.get(from_state, set()):
            return {"status": f"BLOCKED:LEASE_INVALID_TRANSITION:{from_state}->{to_state}", "lease": current}
        if from_state == "LIVE" and to_state == "QUIESCING" and not force:
            expiry = current.get("expires_sequence")
            if expiry is None:
                return {"status": "BLOCKED:LEASE_NOT_EXPIRING", "lease": current}
            if int(current_sequence) < int(expiry):
                return {"status": "BLOCKED:LEASE_NOT_EXPIRED", "lease": current}
        if from_state == "QUIESCING" and to_state == "TOMBSTONED" and int(current.get("active_readers", 0)) != 0:
            return {"status": "BLOCKED:LEASE_READERS_ACTIVE", "lease": current}

        updated = dict(current)
        updated["lifecycle_state"] = to_state
        updated["previous_lease_root"] = current["semantic_root"]
        updated["observed_at_ns"] = time.time_ns()
        updated.pop("semantic_root", None)
        committed = self._commit(logical_identity, updated, expected_hash)
        if committed["status"] != "COMMITTED":
            return committed
        return {"status": "LEASE_" + to_state, "lease": committed["lease"]}

    def retire(self, logical_identity: str, *, current_sequence: int, expected_generation: int | None = None) -> dict[str, Any]:
        """Rollback/release allocation authority without pretending the lease expired.

        A forced LIVE->QUIESCING transition is an explicit cancellation action,
        not a fabricated clock event. Tombstone evidence remains persisted.
        """
        current = self.read(logical_identity)
        if current is None:
            return {"status": "BLOCKED:LEASE_NOT_FOUND"}
        generation = int(current["generation"])
        if expected_generation is not None and generation != int(expected_generation):
            return {"status": "BLOCKED:LEASE_STALE_GENERATION", "lease": current}
        state = current["lifecycle_state"]
        if state == "RECLAIMED":
            return {"status": "LEASE_RECLAIMED", "lease": current}
        if state == "LIVE":
            step = self.transition(logical_identity, to_state="QUIESCING", current_sequence=current_sequence, expected_generation=generation, force=True)
            if step.get("status") != "LEASE_QUIESCING":
                return step
            current = step["lease"]; state = "QUIESCING"
        if state == "QUIESCING":
            if int(current.get("active_readers", 0)) != 0:
                return {"status": "BLOCKED:LEASE_READERS_ACTIVE", "lease": current}
            step = self.transition(logical_identity, to_state="TOMBSTONED", current_sequence=current_sequence, expected_generation=generation)
            if step.get("status") != "LEASE_TOMBSTONED":
                return step
            current = step["lease"]; state = "TOMBSTONED"
        if state == "TOMBSTONED":
            return self.transition(logical_identity, to_state="RECLAIMED", current_sequence=current_sequence, expected_generation=generation)
        return {"status": "BLOCKED:LEASE_RETIRE_STATE_INVALID", "lease": current}

    def change_readers(self, logical_identity: str, *, delta: int, expected_generation: int | None = None) -> dict[str, Any]:
        for _ in range(8):
            current, expected_hash = self._read_cell(self._record_path(logical_identity))
            if current is None:
                return {"status": "BLOCKED:LEASE_NOT_FOUND"}
            self._verify_record(current)
            if expected_generation is not None and int(current["generation"]) != int(expected_generation):
                return {"status": "BLOCKED:LEASE_STALE_GENERATION", "lease": current}
            if current["lifecycle_state"] not in {"LIVE", "QUIESCING"}:
                return {"status": "BLOCKED:LEASE_NOT_READER_ELIGIBLE", "lease": current}
            readers = int(current["active_readers"]) + int(delta)
            if readers < 0:
                return {"status": "BLOCKED:LEASE_READER_UNDERFLOW", "lease": current}
            updated = dict(current)
            updated["active_readers"] = readers
            updated["previous_lease_root"] = current["semantic_root"]
            updated["observed_at_ns"] = time.time_ns()
            updated.pop("semantic_root", None)
            committed = self._commit(logical_identity, updated, expected_hash)
            if committed["status"] == "COMMITTED":
                return {"status": "LEASE_READERS_UPDATED", "lease": committed["lease"]}
        return {"status": "BLOCKED:LEASE_CONCURRENT_WRITE_EXHAUSTED"}

    def gc(self, *, current_sequence: int, max_scan: int = 32) -> list[dict[str, Any]]:
        if int(max_scan) <= 0:
            raise ValueError("LEASE_GC_MAX_SCAN_INVALID")
        index, _ = self._read_cell("leases/index.json")
        if index is None:
            return []
        if index.get("schema") != LEASE_INDEX_SCHEMA or not isinstance(index.get("leases"), dict):
            raise RuntimeError("LEASE_INDEX_INVALID")
        events: list[dict[str, Any]] = []
        identities = [entry["logical_identity"] for _, entry in sorted(index["leases"].items())][: int(max_scan)]
        for logical_identity in identities:
            record = self.read(logical_identity)
            if record is None:
                events.append({"logical_identity": logical_identity, "status": "FAILED:LEASE_INDEX_DANGLING"})
                continue
            state = record["lifecycle_state"]
            if state == "LIVE" and record.get("expires_sequence") is not None and int(current_sequence) >= int(record["expires_sequence"]):
                events.append({"logical_identity": logical_identity, **self.transition(logical_identity, to_state="QUIESCING", current_sequence=current_sequence, expected_generation=record["generation"])})
            elif state == "QUIESCING" and int(record.get("active_readers", 0)) == 0:
                events.append({"logical_identity": logical_identity, **self.transition(logical_identity, to_state="TOMBSTONED", current_sequence=current_sequence, expected_generation=record["generation"])})
            elif state == "TOMBSTONED":
                events.append({"logical_identity": logical_identity, **self.transition(logical_identity, to_state="RECLAIMED", current_sequence=current_sequence, expected_generation=record["generation"])})
        return events
