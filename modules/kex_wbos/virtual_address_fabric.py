from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, MutableMapping, Optional, Protocol, Tuple


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


class AddressState(str, Enum):
    BOUND = "BOUND"
    HOLE = "HOLE"
    REJECTED = "REJECTED"


class ObserverClass(str, Enum):
    INTERNAL_RECEIPT = "INTERNAL_RECEIPT"
    PUBLIC_READBACK = "PUBLIC_READBACK"
    RELEASE_MARKER = "RELEASE_MARKER"
    HASH = "HASH"
    CONTRADICTION = "CONTRADICTION"
    ROUTE_SIGNAL = "ROUTE_SIGNAL"


@dataclass(frozen=True)
class ObserverEvent:
    observer_class: ObserverClass
    source: str
    payload: Mapping[str, Any]
    observed_at_ns: int = field(default_factory=time.time_ns)

    @property
    def event_root(self) -> str:
        return sha({
            "observer_class": self.observer_class.value,
            "source": self.source,
            "payload": self.payload,
            "observed_at_ns": self.observed_at_ns,
        })


@dataclass
class ObserverMemory:
    events: list[ObserverEvent] = field(default_factory=list)

    def integrate(self, event: ObserverEvent) -> str:
        self.events.append(event)
        return self.root

    @property
    def root(self) -> str:
        return sha([e.event_root for e in self.events])

    def latest(self, observer_class: ObserverClass) -> Optional[ObserverEvent]:
        for event in reversed(self.events):
            if event.observer_class == observer_class:
                return event
        return None


class BackingAdapter(Protocol):
    adapter_id: str

    def resolve(self, backing_ref: str) -> Any: ...
    def commit(self, backing_ref: str, operation: str, payload: Any) -> Mapping[str, Any]: ...


@dataclass
class DictBackingAdapter:
    adapter_id: str
    store: MutableMapping[str, Any]

    def resolve(self, backing_ref: str) -> Any:
        if backing_ref not in self.store:
            raise KeyError(backing_ref)
        return self.store[backing_ref]

    def commit(self, backing_ref: str, operation: str, payload: Any) -> Mapping[str, Any]:
        if operation == "SET":
            self.store[backing_ref] = payload
        elif operation == "MERGE":
            current = self.store.get(backing_ref, {})
            if not isinstance(current, dict) or not isinstance(payload, dict):
                raise TypeError("MERGE requires mapping backing and payload")
            merged = dict(current)
            merged.update(payload)
            self.store[backing_ref] = merged
        else:
            raise ValueError(f"unsupported operation: {operation}")
        return {
            "adapter_id": self.adapter_id,
            "backing_ref": backing_ref,
            "operation": operation,
            "state_root": sha(self.store[backing_ref]),
        }


@dataclass(frozen=True)
class Aperture:
    aperture_id: str
    adapter_id: str
    backing_ref: str
    writable: bool = True

    @property
    def root(self) -> str:
        return sha({
            "aperture_id": self.aperture_id,
            "adapter_id": self.adapter_id,
            "backing_ref": self.backing_ref,
            "writable": self.writable,
        })


@dataclass(frozen=True)
class AddressBinding:
    logical_address: str
    state: AddressState
    aperture_id: Optional[str]
    reason: Optional[str]
    generation: int

    @property
    def root(self) -> str:
        return sha({
            "logical_address": self.logical_address,
            "state": self.state.value,
            "aperture_id": self.aperture_id,
            "reason": self.reason,
            "generation": self.generation,
        })


@dataclass(frozen=True)
class RouteResolution:
    logical_address: str
    state: AddressState
    generation: int
    aperture: Optional[Aperture]
    reason: Optional[str]
    route_root: str


@dataclass(frozen=True)
class ExecutionReceipt:
    logical_address: str
    generation: int
    operation: str
    status: str
    adapter_id: Optional[str]
    backing_ref: Optional[str]
    effect_root: Optional[str]
    failure_reason: Optional[str]
    observer_root: str
    produced_at_ns: int

    @property
    def receipt_root(self) -> str:
        return sha(self.__dict__)


class VirtualAddressFabric:
    """
    Ring-1 addressability fabric.

    A HOLE is a valid addressable runtime state.
    It does not imply a backing store exists.
    It can later be rebound to an aperture without changing logical identity.
    """

    def __init__(self):
        self.bindings: Dict[str, AddressBinding] = {}
        self.apertures: Dict[str, Aperture] = {}
        self.adapters: Dict[str, BackingAdapter] = {}
        self.observer = ObserverMemory()
        self._generation = 0

    def register_adapter(self, adapter: BackingAdapter) -> None:
        self.adapters[adapter.adapter_id] = adapter

    def map_hole(self, logical_address: str, reason: str) -> AddressBinding:
        self._generation += 1
        binding = AddressBinding(
            logical_address=logical_address,
            state=AddressState.HOLE,
            aperture_id=None,
            reason=reason,
            generation=self._generation,
        )
        self.bindings[logical_address] = binding
        return binding

    def bind_aperture(
        self,
        logical_address: str,
        *,
        aperture_id: str,
        adapter_id: str,
        backing_ref: str,
        writable: bool = True,
    ) -> AddressBinding:
        if adapter_id not in self.adapters:
            raise KeyError(f"adapter not registered: {adapter_id}")

        previous = self.bindings.get(logical_address)
        if previous and previous.state == AddressState.REJECTED:
            raise RuntimeError("REJECTED_ADDRESS_CANNOT_REBIND_WITHOUT_REPAIR")

        aperture = Aperture(
            aperture_id=aperture_id,
            adapter_id=adapter_id,
            backing_ref=backing_ref,
            writable=writable,
        )
        self.apertures[aperture_id] = aperture

        self._generation += 1
        binding = AddressBinding(
            logical_address=logical_address,
            state=AddressState.BOUND,
            aperture_id=aperture_id,
            reason=None,
            generation=self._generation,
        )
        self.bindings[logical_address] = binding
        return binding

    def reject(self, logical_address: str, reason: str) -> AddressBinding:
        self._generation += 1
        binding = AddressBinding(
            logical_address=logical_address,
            state=AddressState.REJECTED,
            aperture_id=None,
            reason=reason,
            generation=self._generation,
        )
        self.bindings[logical_address] = binding
        return binding

    def resolve(self, logical_address: str) -> RouteResolution:
        binding = self.bindings.get(logical_address)
        if binding is None:
            binding = self.map_hole(logical_address, "UNMAPPED_LOGICAL_ADDRESS")

        aperture = None
        if binding.aperture_id:
            aperture = self.apertures[binding.aperture_id]

        route_root = sha({
            "logical_address": logical_address,
            "binding_root": binding.root,
            "aperture_root": aperture.root if aperture else None,
        })
        return RouteResolution(
            logical_address=logical_address,
            state=binding.state,
            generation=binding.generation,
            aperture=aperture,
            reason=binding.reason,
            route_root=route_root,
        )

    def apply(self, logical_address: str, operation: str, payload: Any) -> ExecutionReceipt:
        produced_at = time.time_ns()
        route = self.resolve(logical_address)

        if route.state == AddressState.HOLE:
            event = ObserverEvent(
                ObserverClass.ROUTE_SIGNAL,
                "braink://virtual-address-fabric",
                {
                    "logical_address": logical_address,
                    "state": "HOLE",
                    "operation": operation,
                    "route_root": route.route_root,
                },
            )
            self.observer.integrate(event)
            return ExecutionReceipt(
                logical_address=logical_address,
                generation=route.generation,
                operation=operation,
                status="DEFERRED_HOLE",
                adapter_id=None,
                backing_ref=None,
                effect_root=None,
                failure_reason=route.reason,
                observer_root=self.observer.root,
                produced_at_ns=produced_at,
            )

        if route.state == AddressState.REJECTED:
            event = ObserverEvent(
                ObserverClass.CONTRADICTION,
                "braink://virtual-address-fabric",
                {
                    "logical_address": logical_address,
                    "state": "REJECTED",
                    "operation": operation,
                    "reason": route.reason,
                },
            )
            self.observer.integrate(event)
            return ExecutionReceipt(
                logical_address=logical_address,
                generation=route.generation,
                operation=operation,
                status="REJECTED",
                adapter_id=None,
                backing_ref=None,
                effect_root=None,
                failure_reason=route.reason,
                observer_root=self.observer.root,
                produced_at_ns=produced_at,
            )

        assert route.aperture is not None
        if not route.aperture.writable:
            raise PermissionError("APERTURE_READ_ONLY")

        adapter = self.adapters[route.aperture.adapter_id]
        effect = adapter.commit(route.aperture.backing_ref, operation, payload)
        effect_root = sha(effect)

        event = ObserverEvent(
            ObserverClass.INTERNAL_RECEIPT,
            f"adapter://{route.aperture.adapter_id}",
            {
                "logical_address": logical_address,
                "operation": operation,
                "effect": effect,
                "route_root": route.route_root,
            },
        )
        self.observer.integrate(event)

        return ExecutionReceipt(
            logical_address=logical_address,
            generation=route.generation,
            operation=operation,
            status="COMMITTED",
            adapter_id=route.aperture.adapter_id,
            backing_ref=route.aperture.backing_ref,
            effect_root=effect_root,
            failure_reason=None,
            observer_root=self.observer.root,
            produced_at_ns=produced_at,
        )

    @property
    def topology_root(self) -> str:
        return sha({
            "bindings": {k: v.root for k, v in sorted(self.bindings.items())},
            "apertures": {k: v.root for k, v in sorted(self.apertures.items())},
            "observer_root": self.observer.root,
        })

    def snapshot(self) -> Mapping[str, Any]:
        return {
            "schema": "braink.virtual-address-fabric/v1",
            "generation": self._generation,
            "topology_root": self.topology_root,
            "observer_root": self.observer.root,
            "bindings": {
                addr: {
                    "state": binding.state.value,
                    "aperture_id": binding.aperture_id,
                    "reason": binding.reason,
                    "generation": binding.generation,
                }
                for addr, binding in sorted(self.bindings.items())
            },
            "apertures": {
                aid: {
                    "adapter_id": ap.adapter_id,
                    "backing_ref": ap.backing_ref,
                    "writable": ap.writable,
                    "root": ap.root,
                }
                for aid, ap in sorted(self.apertures.items())
            },
        }


class RuntimeCarrier:
    """
    Small carrier frame. The carrier does not contain all backing memory;
    it contains addresses, routes, observer roots and continuation state.
    """

    def __init__(self, carrier_id: str):
        self.carrier_id = carrier_id
        self.revision = 0
        self.last_root: Optional[str] = None
        self.frame: Dict[str, Any] = {}

    def rewrite(
        self,
        fabric: VirtualAddressFabric,
        *,
        continuation: Mapping[str, Any],
        observer_inputs: Tuple[ObserverEvent, ...] = (),
    ) -> Mapping[str, Any]:
        for event in observer_inputs:
            fabric.observer.integrate(event)

        self.revision += 1
        self.frame = {
            "schema": "braink.runtime-carrier/v1",
            "carrier_id": self.carrier_id,
            "revision": self.revision,
            "fabric_topology_root": fabric.topology_root,
            "observer_root": fabric.observer.root,
            "continuation": dict(continuation),
        }
        self.last_root = sha(self.frame)
        return {**self.frame, "carrier_root": self.last_root}
