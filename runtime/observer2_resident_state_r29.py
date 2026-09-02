from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable, Mapping, Optional
import json

from observer2_federation_r29 import FederatedFrame


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def _root(value: Any) -> str:
    return sha256(_canon(value)).hexdigest()


class ResidentSnapshotProbe:
    """Read-only adapter over a resident object's non-mutating snapshot/state method.

    The adapter deliberately accepts only an explicit read method. It never discovers or
    invokes route/apply/write/commit/checkpoint/restore/continuation_tick methods.
    """

    substrate = "braink-resident-state"

    def __init__(self, resident: Any, *, environment_id: str, probe_id: str,
                 read_method: str = "snapshot", projection: Optional[Callable[[Any], Mapping[str, Any]]] = None) -> None:
        self.resident = resident
        self.environment_id = environment_id
        self.probe_id = probe_id
        self.read_method = read_method
        self.projection = projection
        reader = getattr(resident, read_method, None)
        if not callable(reader):
            raise TypeError(f"resident has no callable read method {read_method!r}")
        self._reader = reader

    def sample(self, observer_id: str) -> Mapping[str, Any]:
        raw = self._reader()
        if self.projection is not None:
            raw = self.projection(raw)
        payload = json.loads(json.dumps(raw, sort_keys=True, default=str))
        return {
            "observer_id": observer_id,
            "resident_type": type(self.resident).__name__,
            "read_method": self.read_method,
            "state_root": _root(payload),
            "state": payload,
        }


class SelfAddressingRuntimeProbe(ResidentSnapshotProbe):
    """Read-only Observer² view of the existing SelfAddressingRuntime.snapshot()."""

    substrate = "braink-self-addressing-runtime"

    def __init__(self, runtime: Any, *, environment_id: str = "env://braink/self-addressing-runtime",
                 probe_id: str = "probe://braink/self-addressing-runtime") -> None:
        super().__init__(runtime, environment_id=environment_id, probe_id=probe_id, read_method="snapshot")


class RecursiveComputerProbe(ResidentSnapshotProbe):
    """Read-only adapter for a RecursiveComputer snapshot/state export method."""

    substrate = "braink-recursive-computer"

    def __init__(self, runtime: Any, *, environment_id: str = "env://braink/recursive-computer",
                 probe_id: str = "probe://braink/recursive-computer", read_method: str = "snapshot") -> None:
        super().__init__(runtime, environment_id=environment_id, probe_id=probe_id, read_method=read_method)


class KexCoordinatePlaneProbe(ResidentSnapshotProbe):
    """Read-only adapter for the existing KEX coordinate-plane state export."""

    substrate = "kex-coordinate-plane"

    def __init__(self, runtime: Any, *, environment_id: str = "env://kex/coordinate-plane",
                 probe_id: str = "probe://kex/coordinate-plane", read_method: str = "snapshot") -> None:
        super().__init__(runtime, environment_id=environment_id, probe_id=probe_id, read_method=read_method)


@dataclass(frozen=True)
class EnvironmentDelta:
    environment_id: str
    probe_id: str
    substrate: str
    before_status: Optional[str]
    after_status: Optional[str]
    before_payload_sha256: Optional[str]
    after_payload_sha256: Optional[str]
    changed: bool


def _receipt_index(frame: FederatedFrame) -> dict[tuple[str, str], Any]:
    return {(r.environment_id, r.probe_id): r for r in frame.receipts}


def compare_federated_frames(before: FederatedFrame, after: FederatedFrame, *, mode: str = "PRE_POST_ENVIRONMENT") -> Mapping[str, Any]:
    if before.observer_id != after.observer_id:
        raise ValueError("observer identity changed across comparison")
    left = _receipt_index(before)
    right = _receipt_index(after)
    keys = sorted(set(left) | set(right))
    deltas = []
    for key in keys:
        a = left.get(key)
        b = right.get(key)
        delta = EnvironmentDelta(
            environment_id=key[0],
            probe_id=key[1],
            substrate=(b.substrate if b else a.substrate),
            before_status=(a.status if a else None),
            after_status=(b.status if b else None),
            before_payload_sha256=(a.payload_sha256 if a else None),
            after_payload_sha256=(b.payload_sha256 if b else None),
            changed=(a is None or b is None or a.status != b.status or a.payload_sha256 != b.payload_sha256),
        )
        deltas.append(delta.__dict__)
    relation = {
        "schema": "kex.observer2.federated-pre-post-relation.r29",
        "mode": mode,
        "observer_id": before.observer_id,
        "left_environment_root": before.environment_root_sha256,
        "right_environment_root": after.environment_root_sha256,
        "changed": any(x["changed"] for x in deltas),
        "environment_deltas": deltas,
    }
    return {**relation, "comparison_root": _root(relation)}


def derive_continuation(before: FederatedFrame, after: FederatedFrame,
                        comparison: Mapping[str, Any], *, target_satisfied: bool,
                        prior: Optional[Mapping[str, Any]] = None) -> Mapping[str, Any]:
    next_route = "FOLLOW_SUCCESSOR_STATE" if target_satisfied else "RECONCILE"
    return {
        **dict(prior or {}),
        "schema": "kex.observer2.federated-continuation.r29",
        "observer_id": after.observer_id,
        "pre_environment_root": before.environment_root_sha256,
        "post_environment_root": after.environment_root_sha256,
        "comparison_root": comparison["comparison_root"],
        "environment_changed": bool(comparison["changed"]),
        "target_satisfied": bool(target_satisfied),
        "next_route": next_route,
    }
