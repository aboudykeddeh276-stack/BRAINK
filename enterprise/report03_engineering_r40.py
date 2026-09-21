from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Callable, Iterable
import hashlib
import json
import os
import threading


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TransitionProposal:
    source_node_id: str
    target_node_id: str
    source_state_root: str
    target_expected_entry_root: str
    logical_sequence: int
    operation: str
    payload_root: str
    authority: str
    hop_path: tuple[str, ...]
    attestation: str

    def semantic_body(self) -> dict[str, Any]:
        body = asdict(self)
        body.pop("attestation", None)
        body["hop_path"] = list(self.hop_path)
        return body

    @property
    def transition_id(self) -> str:
        return sha256_json(self.semantic_body())


class ToTSafetyKernel:
    SCHEMA = "braink.tot-safety-kernel.report03/v1"

    def __init__(self, state_path: str | Path, *, ledger: Any, max_hops: int = 16):
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger = ledger
        self.max_hops = int(max_hops)
        if self.max_hops < 1:
            raise ValueError("TOT_MAX_HOPS_INVALID")
        self._lock = threading.RLock()
        self._state = {"schema": self.SCHEMA, "last_sequence": {}, "accepted": {}, "head": None}
        self._state["head"] = self._compute_head(self._state)
        if self.path.exists():
            self._load()

    def _semantic_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema": state["schema"],
            "last_sequence": state["last_sequence"],
            "accepted": state["accepted"],
        }

    def _compute_head(self, state: dict[str, Any]) -> str:
        return sha256_json(self._semantic_state(state))

    def _load(self) -> None:
        body = json.loads(self.path.read_text(encoding="utf-8"))
        if body.get("schema") != self.SCHEMA:
            raise RuntimeError("TOT_STATE_SCHEMA_MISMATCH")
        if body.get("head") != self._compute_head(body):
            raise RuntimeError("TOT_STATE_HASH_MISMATCH")
        self._state = body

    def _persist(self, candidate: dict[str, Any]) -> None:
        body = json.loads(canonical_json(candidate))
        body["head"] = self._compute_head(body)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        raw = (json.dumps(body, sort_keys=True, indent=2) + "\n").encode("utf-8")
        with tmp.open("wb") as fh:
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)
        fd = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        self._state = body

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(canonical_json(self._state))

    def authorize(
        self,
        proposal: TransitionProposal,
        *,
        source_entry: dict[str, Any] | None,
        target_entry: dict[str, Any] | None,
        authority_verifier: Callable[[TransitionProposal], bool],
    ) -> dict[str, Any]:
        with self._lock:
            stages: list[str] = []
            if source_entry is None:
                return {"status": "BLOCKED:SOURCE_NODE_UNKNOWN", "stages": stages}
            if target_entry is None:
                return {"status": "BLOCKED:TARGET_NODE_UNKNOWN", "stages": stages}
            stages.append("DIRECTORY_RESOLVED")

            if proposal.source_node_id == proposal.target_node_id:
                return {"status": "BLOCKED:TOT_SELF_TRANSITION", "stages": stages}
            if source_entry.get("node_id") != proposal.source_node_id or target_entry.get("node_id") != proposal.target_node_id:
                return {"status": "FAILED:TOT_DIRECTORY_IDENTITY_MISMATCH", "stages": stages}
            if source_entry.get("state_root") != proposal.source_state_root:
                return {"status": "BLOCKED:TOT_SOURCE_STATE_STALE", "stages": stages}
            if target_entry.get("entry_root") != proposal.target_expected_entry_root:
                return {"status": "BLOCKED:TOT_TARGET_ENTRY_STALE", "stages": stages}
            stages.append("STATE_ROOTS_VERIFIED")

            if source_entry.get("authority") != proposal.authority:
                return {"status": "BLOCKED:TOT_AUTHORITY_MISMATCH", "stages": stages}
            if "tot.propose" not in set(source_entry.get("capabilities", [])):
                return {"status": "BLOCKED:TOT_SOURCE_CAPABILITY", "stages": stages}
            if proposal.operation not in set(target_entry.get("capabilities", [])):
                return {"status": "BLOCKED:TOT_TARGET_CAPABILITY", "stages": stages}
            stages.append("CAPABILITIES_VERIFIED")

            path = tuple(proposal.hop_path)
            if not path or path[0] != proposal.source_node_id:
                return {"status": "BLOCKED:TOT_PATH_SOURCE_MISMATCH", "stages": stages}
            if len(path) > self.max_hops:
                return {"status": "BLOCKED:TOT_HOP_LIMIT", "stages": stages}
            if len(set(path)) != len(path):
                return {"status": "BLOCKED:TOT_CYCLE_DETECTED", "stages": stages}
            if proposal.target_node_id in path:
                return {"status": "BLOCKED:TOT_TARGET_ALREADY_VISITED", "stages": stages}
            stages.append("PATH_VERIFIED")

            last = int(self._state["last_sequence"].get(proposal.source_node_id, 0))
            if proposal.logical_sequence <= last:
                return {
                    "status": "BLOCKED:TOT_REPLAY_OR_STALE_SEQUENCE",
                    "stages": stages,
                    "last_sequence": last,
                }
            if proposal.transition_id in self._state["accepted"]:
                return {"status": "BLOCKED:TOT_REPLAY_TRANSITION", "stages": stages}
            if not bool(authority_verifier(proposal)):
                return {"status": "FAILED:TOT_ATTESTATION_INVALID", "stages": stages}
            stages.append("AUTHENTICATED")

            next_state = json.loads(canonical_json(self._state))
            next_state["last_sequence"][proposal.source_node_id] = proposal.logical_sequence
            next_state["accepted"][proposal.transition_id] = {
                "source_node_id": proposal.source_node_id,
                "target_node_id": proposal.target_node_id,
                "logical_sequence": proposal.logical_sequence,
                "operation": proposal.operation,
                "payload_root": proposal.payload_root,
            }
            self._persist(next_state)
            receipt = self.ledger.append(
                stream_id="tot.safety",
                packet_type="tot_transition_authorized",
                actor=proposal.source_node_id,
                brain_role="safety_kernel",
                status="VALIDATED",
                content={
                    "transition_id": proposal.transition_id,
                    "source_node_id": proposal.source_node_id,
                    "target_node_id": proposal.target_node_id,
                    "logical_sequence": proposal.logical_sequence,
                    "operation": proposal.operation,
                    "payload_root": proposal.payload_root,
                    "kernel_head": self._state["head"],
                },
                capability_ids=["tot.propose", proposal.operation],
                constraint_ids=["NO_REPLAY", "NO_CYCLE", "BOUNDED_HOPS", "STATE_ROOT_MATCH"],
            )
            stages += ["SAFETY_STATE_COMMITTED", "EVIDENCE_BOUND"]
            return {
                "status": "AUTHORIZED",
                "transition_id": proposal.transition_id,
                "packet_id": receipt.packet_id,
                "stages": stages,
                "kernel_head": self._state["head"],
            }


@dataclass(frozen=True)
class CoordinateEntry:
    node_id: str
    coordinate: tuple[int, ...]
    generation: int
    sequence: int
    logical_identity: str
    state_root: str
    template_root: str
    network_endpoints: tuple[str, ...]
    capabilities: tuple[str, ...]
    authority: str
    health: str
    parent_entry_root: str | None = None
    tombstoned: bool = False

    def body(self) -> dict[str, Any]:
        body = asdict(self)
        body["coordinate"] = list(self.coordinate)
        body["network_endpoints"] = list(self.network_endpoints)
        body["capabilities"] = list(self.capabilities)
        return body

    @property
    def entry_root(self) -> str:
        return sha256_json(self.body())

    def record(self) -> dict[str, Any]:
        body = self.body()
        body["entry_root"] = self.entry_root
        return body

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "CoordinateEntry":
        body = dict(record)
        claimed = body.pop("entry_root", None)
        obj = cls(
            node_id=str(body["node_id"]),
            coordinate=tuple(int(x) for x in body["coordinate"]),
            generation=int(body["generation"]),
            sequence=int(body["sequence"]),
            logical_identity=str(body["logical_identity"]),
            state_root=str(body["state_root"]),
            template_root=str(body["template_root"]),
            network_endpoints=tuple(str(x) for x in body["network_endpoints"]),
            capabilities=tuple(sorted(set(str(x) for x in body["capabilities"]))),
            authority=str(body["authority"]),
            health=str(body["health"]),
            parent_entry_root=body.get("parent_entry_root"),
            tombstoned=bool(body.get("tombstoned", False)),
        )
        if obj.entry_root != claimed:
            raise RuntimeError("DIRECTORY_ENTRY_HASH_MISMATCH")
        return obj


class DistributedCoordinateDirectory:
    SCHEMA = "braink.distributed-coordinate-directory.report03/v1"

    def __init__(
        self,
        state_path: str | Path,
        *,
        ledger: Any,
        persist_hook: Callable[[dict[str, Any]], None] | None = None,
    ):
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger = ledger
        self.persist_hook = persist_hook
        self._lock = threading.RLock()
        self._state = {
            "schema": self.SCHEMA,
            "directory_id": sha256_json(str(self.path.resolve())),
            "version": 0,
            "entries": {},
            "history": {},
            "coordinate_owner": {},
            "head_root": None,
        }
        self._state["head_root"] = self._head(self._state)
        if self.path.exists():
            self._load()

    @staticmethod
    def _coord_key(coord: Iterable[int]) -> str:
        values = tuple(int(x) for x in coord)
        if not values or any(x == 0 for x in values):
            raise ValueError("DIRECTORY_COORDINATE_ZERO_OR_EMPTY")
        return ":".join(str(x) for x in values)

    @staticmethod
    def _head(state: dict[str, Any]) -> str:
        return sha256_json({
            "schema": state["schema"],
            "directory_id": state["directory_id"],
            "version": state["version"],
            "entries": state["entries"],
            "coordinate_owner": state["coordinate_owner"],
        })

    def _validate_state(self, state: dict[str, Any]) -> None:
        if state.get("schema") != self.SCHEMA:
            raise RuntimeError("DIRECTORY_SCHEMA_MISMATCH")
        if state.get("head_root") != self._head(state):
            raise RuntimeError("DIRECTORY_HEAD_MISMATCH")
        owners: dict[str, str] = {}
        for node_id, record in state.get("entries", {}).items():
            entry = CoordinateEntry.from_record(record)
            if entry.node_id != node_id:
                raise RuntimeError("DIRECTORY_NODE_KEY_MISMATCH")
            key = self._coord_key(entry.coordinate)
            if not entry.tombstoned:
                other = owners.get(key)
                if other is not None and other != node_id:
                    raise RuntimeError("DIRECTORY_COORDINATE_COLLISION")
                owners[key] = node_id
            if entry.entry_root not in state.get("history", {}).get(node_id, {}):
                raise RuntimeError("DIRECTORY_CURRENT_ENTRY_MISSING_HISTORY")
        if owners != state.get("coordinate_owner", {}):
            raise RuntimeError("DIRECTORY_OWNER_INDEX_MISMATCH")
        for node_id, history in state.get("history", {}).items():
            for entry_root, record in history.items():
                entry = CoordinateEntry.from_record(record)
                if entry.node_id != node_id or entry.entry_root != entry_root:
                    raise RuntimeError("DIRECTORY_HISTORY_CORRUPT")

    def _load(self) -> None:
        body = json.loads(self.path.read_text(encoding="utf-8"))
        self._validate_state(body)
        self._state = body

    def _persist(self, candidate: dict[str, Any]) -> None:
        body = json.loads(canonical_json(candidate))
        body["head_root"] = self._head(body)
        self._validate_state(body)
        if self.persist_hook is not None:
            self.persist_hook(body)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        raw = (json.dumps(body, sort_keys=True, indent=2) + "\n").encode("utf-8")
        with tmp.open("wb") as fh:
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)
        fd = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        self._state = body

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(canonical_json(self._state))

    def resolve(self, node_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._state["entries"].get(str(node_id))
            return None if record is None else json.loads(canonical_json(record))

    def resolve_coordinate(self, coordinate: Iterable[int]) -> dict[str, Any] | None:
        with self._lock:
            node_id = self._state["coordinate_owner"].get(self._coord_key(coordinate))
            return None if node_id is None else self.resolve(node_id)

    def _commit_entry(
        self,
        entry: CoordinateEntry,
        *,
        packet_type: str,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        candidate = json.loads(canonical_json(self._state))
        key = self._coord_key(entry.coordinate)
        owner = candidate["coordinate_owner"].get(key)
        if not entry.tombstoned and owner is not None and owner != entry.node_id:
            return {"status": "BLOCKED:COORDINATE_OCCUPIED", "owner": owner, "coordinate": key}

        old_record = candidate["entries"].get(entry.node_id)
        if old_record is not None:
            old = CoordinateEntry.from_record(old_record)
            old_key = self._coord_key(old.coordinate)
            if old.coordinate != entry.coordinate:
                return {"status": "BLOCKED:COORDINATE_IMMUTABLE", "entry": old_record}
            if entry.parent_entry_root != old.entry_root:
                return {
                    "status": "BLOCKED:DIRECTORY_CAS_CONFLICT",
                    "expected": old.entry_root,
                    "parent": entry.parent_entry_root,
                }
            if entry.sequence != old.sequence + 1:
                return {"status": "BLOCKED:DIRECTORY_SEQUENCE", "expected": old.sequence + 1}
            if entry.generation < old.generation:
                return {"status": "BLOCKED:DIRECTORY_GENERATION_STALE"}
            candidate["coordinate_owner"].pop(old_key, None)
        else:
            if entry.sequence != 1 or entry.parent_entry_root is not None:
                return {"status": "BLOCKED:DIRECTORY_GENESIS_SEQUENCE"}

        candidate["entries"][entry.node_id] = entry.record()
        candidate["history"].setdefault(entry.node_id, {})[entry.entry_root] = entry.record()
        if not entry.tombstoned:
            candidate["coordinate_owner"][key] = entry.node_id
        candidate["version"] += 1

        before = json.loads(canonical_json(self._state))
        try:
            self._persist(candidate)
        except Exception:
            self._state = before
            raise

        packet = self.ledger.append(
            stream_id="coordinate.directory",
            packet_type=packet_type,
            actor=entry.node_id,
            brain_role="directory",
            status="VALIDATED",
            content={
                "entry": entry.record(),
                "directory_version": self._state["version"],
                "directory_head": self._state["head_root"],
                "evidence": evidence or {},
            },
        )
        return {
            "status": "COMMITTED",
            "entry": entry.record(),
            "directory_version": self._state["version"],
            "directory_head": self._state["head_root"],
            "packet_id": packet.packet_id,
        }

    def register(self, entry: CoordinateEntry, *, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            if entry.node_id in self._state["entries"]:
                return {"status": "BLOCKED:NODE_ALREADY_REGISTERED", "entry": self.resolve(entry.node_id)}
            return self._commit_entry(entry, packet_type="coordinate_registered", evidence=evidence)

    def update(
        self,
        node_id: str,
        *,
        expected_entry_root: str,
        state_root: str | None = None,
        template_root: str | None = None,
        network_endpoints: Iterable[str] | None = None,
        capabilities: Iterable[str] | None = None,
        health: str | None = None,
        generation: int | None = None,
        tombstoned: bool | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            current_record = self.resolve(node_id)
            if current_record is None:
                return {"status": "BLOCKED:NODE_UNKNOWN"}
            old = CoordinateEntry.from_record(current_record)
            if old.entry_root != expected_entry_root:
                return {
                    "status": "BLOCKED:DIRECTORY_CAS_CONFLICT",
                    "expected": old.entry_root,
                    "provided": expected_entry_root,
                }
            new = replace(
                old,
                sequence=old.sequence + 1,
                parent_entry_root=old.entry_root,
                state_root=old.state_root if state_root is None else str(state_root),
                template_root=old.template_root if template_root is None else str(template_root),
                network_endpoints=old.network_endpoints if network_endpoints is None else tuple(sorted(set(map(str, network_endpoints)))),
                capabilities=old.capabilities if capabilities is None else tuple(sorted(set(map(str, capabilities)))),
                health=old.health if health is None else str(health),
                generation=old.generation if generation is None else int(generation),
                tombstoned=old.tombstoned if tombstoned is None else bool(tombstoned),
            )
            return self._commit_entry(new, packet_type="coordinate_updated", evidence=evidence)

    def merge_snapshot(self, remote: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._validate_state(remote)
            applied: list[str] = []
            conflicts: list[dict[str, Any]] = []
            ignored: list[dict[str, Any]] = []

            for node_id, remote_record in sorted(remote["entries"].items()):
                remote_current = CoordinateEntry.from_record(remote_record)
                local_record = self._state["entries"].get(node_id)

                if local_record is None:
                    history = remote["history"].get(node_id, {})
                    chain = []
                    cursor = remote_current
                    while True:
                        chain.append(cursor)
                        if cursor.parent_entry_root is None:
                            break
                        parent_record = history.get(cursor.parent_entry_root)
                        if parent_record is None:
                            conflicts.append({"node_id": node_id, "reason": "REMOTE_HISTORY_GAP"})
                            chain = []
                            break
                        cursor = CoordinateEntry.from_record(parent_record)
                    for item in reversed(chain):
                        if self._state["entries"].get(node_id) is None:
                            result = self.register(item, evidence={"merge": "remote"})
                        else:
                            result = self.update(
                                node_id,
                                expected_entry_root=item.parent_entry_root,
                                state_root=item.state_root,
                                template_root=item.template_root,
                                network_endpoints=item.network_endpoints,
                                capabilities=item.capabilities,
                                health=item.health,
                                generation=item.generation,
                                tombstoned=item.tombstoned,
                                evidence={"merge": "remote"},
                            )
                        if result.get("status") != "COMMITTED":
                            conflicts.append({"node_id": node_id, "reason": result.get("status")})
                            break
                        applied.append(item.entry_root)
                    continue

                local = CoordinateEntry.from_record(local_record)
                if local.entry_root == remote_current.entry_root:
                    ignored.append({"node_id": node_id, "reason": "IDENTICAL"})
                    continue
                if remote_current.sequence == local.sequence:
                    conflicts.append({
                        "node_id": node_id,
                        "reason": "CONCURRENT_FORK_SAME_SEQUENCE",
                        "local_root": local.entry_root,
                        "remote_root": remote_current.entry_root,
                    })
                    continue
                if remote_current.sequence < local.sequence:
                    ignored.append({"node_id": node_id, "reason": "STALE_OLDER"})
                    continue

                history = remote["history"].get(node_id, {})
                chain = []
                cursor = remote_current
                found = False
                while cursor.parent_entry_root is not None:
                    if cursor.parent_entry_root == local.entry_root:
                        chain.append(cursor)
                        found = True
                        break
                    chain.append(cursor)
                    parent_record = history.get(cursor.parent_entry_root)
                    if parent_record is None:
                        break
                    cursor = CoordinateEntry.from_record(parent_record)

                if not found:
                    conflicts.append({
                        "node_id": node_id,
                        "reason": "FORK_OR_MISSING_ANCESTRY",
                        "local_root": local.entry_root,
                        "remote_root": remote_current.entry_root,
                    })
                    continue

                for item in reversed(chain):
                    result = self.update(
                        node_id,
                        expected_entry_root=item.parent_entry_root,
                        state_root=item.state_root,
                        template_root=item.template_root,
                        network_endpoints=item.network_endpoints,
                        capabilities=item.capabilities,
                        health=item.health,
                        generation=item.generation,
                        tombstoned=item.tombstoned,
                        evidence={"merge": "remote"},
                    )
                    if result.get("status") != "COMMITTED":
                        conflicts.append({"node_id": node_id, "reason": result.get("status")})
                        break
                    applied.append(item.entry_root)

            return {
                "status": "MERGED" if not conflicts else "CONFLICT",
                "applied": applied,
                "conflicts": conflicts,
                "ignored": ignored,
                "directory_head": self._state["head_root"],
            }


@dataclass(frozen=True)
class DesiredNodeState:
    node_id: str
    coordinate: tuple[int, ...]
    logical_identity: str
    template_root: str
    authority: str
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class ObservedNodeState:
    node_id: str
    coordinate: tuple[int, ...]
    logical_identity: str
    state_root: str
    template_root: str
    network_endpoints: tuple[str, ...]
    capabilities: tuple[str, ...]
    authority: str
    health: str
    local_verified: bool

    def mutable_projection(self) -> dict[str, Any]:
        return {
            "state_root": self.state_root,
            "network_endpoints": list(self.network_endpoints),
            "capabilities": list(self.capabilities),
            "health": self.health,
        }


class Layer2Reconciler:
    def __init__(self, directory: DistributedCoordinateDirectory, kernel: ToTSafetyKernel, *, ledger: Any):
        self.directory = directory
        self.kernel = kernel
        self.ledger = ledger

    def _receipt(self, packet_type: str, status: str, content: dict[str, Any]) -> dict[str, Any]:
        packet = self.ledger.append(
            stream_id="layer2.reconcile",
            packet_type=packet_type,
            actor=content.get("node_id", "layer2"),
            brain_role="reconciler",
            status="VALIDATED" if status in {"REGISTERED", "RECONCILED", "FIXED_POINT"} else "BLOCKED",
            content={"status": status, **content},
        )
        return {"packet_id": packet.packet_id, "semantic_hash": packet.semantic_hash}

    def reconcile(
        self,
        desired: DesiredNodeState,
        observed: ObservedNodeState | None,
        *,
        proposer_entry: dict[str, Any] | None = None,
        proposal: TransitionProposal | None = None,
        authority_verifier: Callable[[TransitionProposal], bool] | None = None,
        bootstrap_verifier: Callable[[ObservedNodeState], bool] | None = None,
    ) -> dict[str, Any]:
        stages = ["DESIRED_LOADED"]
        if observed is None:
            receipt = self._receipt("reconcile_blocked", "BLOCKED:OBSERVED_NODE_MISSING", {"node_id": desired.node_id})
            return {"status": "BLOCKED:OBSERVED_NODE_MISSING", "stages": stages, "receipt": receipt}
        stages.append("OBSERVED_READBACK")

        if not observed.local_verified:
            receipt = self._receipt("reconcile_blocked", "BLOCKED:LOCAL_VERIFICATION_REQUIRED", {"node_id": desired.node_id})
            return {"status": "BLOCKED:LOCAL_VERIFICATION_REQUIRED", "stages": stages, "receipt": receipt}

        immutable_errors = []
        if observed.node_id != desired.node_id:
            immutable_errors.append("NODE_ID")
        if observed.coordinate != desired.coordinate:
            immutable_errors.append("COORDINATE")
        if observed.logical_identity != desired.logical_identity:
            immutable_errors.append("LOGICAL_IDENTITY")
        if observed.template_root != desired.template_root:
            immutable_errors.append("TEMPLATE_ROOT")
        if observed.authority != desired.authority:
            immutable_errors.append("AUTHORITY")
        if immutable_errors:
            receipt = self._receipt("reconcile_failed", "FAILED:IDENTITY_DRIFT", {
                "node_id": desired.node_id,
                "fields": immutable_errors,
            })
            return {
                "status": "FAILED:IDENTITY_DRIFT",
                "stages": stages,
                "fields": immutable_errors,
                "receipt": receipt,
            }
        stages.append("IDENTITY_VERIFIED")

        current = self.directory.resolve(desired.node_id)
        if current is None:
            if bootstrap_verifier is None or not bool(bootstrap_verifier(observed)):
                receipt = self._receipt("reconcile_blocked", "BLOCKED:BOOTSTRAP_AUTHORITY", {"node_id": desired.node_id})
                return {"status": "BLOCKED:BOOTSTRAP_AUTHORITY", "stages": stages, "receipt": receipt}
            entry = CoordinateEntry(
                node_id=desired.node_id,
                coordinate=desired.coordinate,
                generation=1,
                sequence=1,
                logical_identity=desired.logical_identity,
                state_root=observed.state_root,
                template_root=desired.template_root,
                network_endpoints=tuple(sorted(set(observed.network_endpoints))),
                capabilities=tuple(sorted(set(observed.capabilities))),
                authority=desired.authority,
                health=observed.health,
            )
            result = self.directory.register(entry, evidence={"layer2": "bootstrap", "local_verified": True})
            if result.get("status") != "COMMITTED":
                return {"status": result.get("status"), "stages": stages, "directory": result}
            stages += ["DIRECTORY_REGISTERED", "READBACK_VERIFIED"]
            receipt = self._receipt("reconcile_registered", "REGISTERED", {
                "node_id": desired.node_id,
                "entry_root": result["entry"]["entry_root"],
            })
            return {"status": "REGISTERED", "stages": stages, "directory": result, "receipt": receipt}

        stages.append("DIRECTORY_RESOLVED")
        current_mutable = {
            "state_root": current["state_root"],
            "network_endpoints": current["network_endpoints"],
            "capabilities": current["capabilities"],
            "health": current["health"],
        }
        observed_mutable = observed.mutable_projection()
        observed_mutable["network_endpoints"] = sorted(set(observed_mutable["network_endpoints"]))
        observed_mutable["capabilities"] = sorted(set(observed_mutable["capabilities"]))

        if current_mutable == observed_mutable:
            receipt = self._receipt("reconcile_fixed_point", "FIXED_POINT", {
                "node_id": desired.node_id,
                "entry_root": current["entry_root"],
            })
            return {
                "status": "FIXED_POINT",
                "stages": stages + ["QUIESCED"],
                "receipt": receipt,
                "entry": current,
            }

        if proposal is None or proposer_entry is None or authority_verifier is None:
            receipt = self._receipt("reconcile_blocked", "BLOCKED:TOT_PROOF_REQUIRED", {
                "node_id": desired.node_id,
                "drift": {"directory": current_mutable, "observed": observed_mutable},
            })
            return {"status": "BLOCKED:TOT_PROOF_REQUIRED", "stages": stages, "receipt": receipt}

        expected_payload = sha256_json(observed_mutable)
        if (
            proposal.target_node_id != desired.node_id
            or proposal.payload_root != expected_payload
            or proposal.target_expected_entry_root != current["entry_root"]
        ):
            receipt = self._receipt("reconcile_failed", "FAILED:TOT_PROPOSAL_BINDING", {"node_id": desired.node_id})
            return {"status": "FAILED:TOT_PROPOSAL_BINDING", "stages": stages, "receipt": receipt}

        safety = self.kernel.authorize(
            proposal,
            source_entry=proposer_entry,
            target_entry=current,
            authority_verifier=authority_verifier,
        )
        if safety.get("status") != "AUTHORIZED":
            receipt = self._receipt("reconcile_blocked", safety.get("status", "BLOCKED:TOT"), {
                "node_id": desired.node_id,
                "safety": safety,
            })
            return {
                "status": safety.get("status", "BLOCKED:TOT"),
                "stages": stages,
                "safety": safety,
                "receipt": receipt,
            }

        stages.append("TOT_AUTHORIZED")
        result = self.directory.update(
            desired.node_id,
            expected_entry_root=current["entry_root"],
            state_root=observed.state_root,
            network_endpoints=observed.network_endpoints,
            capabilities=observed.capabilities,
            health=observed.health,
            evidence={"layer2": "tot_reconcile", "transition_id": safety["transition_id"]},
        )
        if result.get("status") != "COMMITTED":
            receipt = self._receipt("reconcile_failed", "FAILED:DIRECTORY_COMMIT", {
                "node_id": desired.node_id,
                "directory": result,
            })
            return {"status": "FAILED:DIRECTORY_COMMIT", "stages": stages, "directory": result, "receipt": receipt}

        readback = self.directory.resolve(desired.node_id)
        if (
            readback is None
            or readback["state_root"] != observed.state_root
            or sorted(readback["network_endpoints"]) != sorted(set(observed.network_endpoints))
        ):
            receipt = self._receipt("reconcile_failed", "FAILED:READBACK_MISMATCH", {
                "node_id": desired.node_id,
                "readback": readback,
            })
            return {"status": "FAILED:READBACK_MISMATCH", "stages": stages, "receipt": receipt}

        stages += ["DIRECTORY_COMMITTED", "READBACK_VERIFIED"]
        receipt = self._receipt("reconcile_completed", "RECONCILED", {
            "node_id": desired.node_id,
            "transition_id": safety["transition_id"],
            "entry_root": readback["entry_root"],
        })
        return {
            "status": "RECONCILED",
            "stages": stages,
            "safety": safety,
            "directory": result,
            "readback": readback,
            "receipt": receipt,
        }
