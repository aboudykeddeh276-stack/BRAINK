from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Callable, Dict, Optional
import hashlib, json, time, uuid


def _bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def root(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _bytes(value)).hexdigest()


class AddressState(str, Enum):
    HOLE = "HOLE"
    APERTURE_BOUND = "APERTURE_BOUND"
    BACKING_BOUND = "BACKING_BOUND"


@dataclass(frozen=True)
class Address:
    logical: str
    state: AddressState
    aperture: Optional[str] = None
    backing: Optional[str] = None
    adapter: Optional[str] = None


@dataclass(frozen=True)
class ObserverSignal:
    signal_id: str
    source: str
    subject: str
    kind: str
    payload_hash: str
    observed_at_ns: int


class Ring1AddressSpace:
    """Logical addressability/routing plane. Backing may be unresolved."""
    def __init__(self):
        self.addresses: Dict[str, Address] = {}

    def resolve(self, logical: str) -> Address:
        if logical not in self.addresses:
            self.addresses[logical] = Address(logical, AddressState.HOLE)
        return self.addresses[logical]

    def bind(self, logical: str, *, aperture: str, adapter: str, backing: Optional[str] = None) -> Address:
        state = AddressState.BACKING_BOUND if backing else AddressState.APERTURE_BOUND
        addr = Address(logical, state, aperture, backing, adapter)
        self.addresses[logical] = addr
        return addr

    @property
    def state_root(self) -> str:
        return root({k: asdict(v) for k, v in sorted(self.addresses.items())})


class Ring2BackingArray:
    """Reference backing substrate. Adapters may replace this with VFS/database/network backing."""
    def __init__(self, backing_id: str):
        self.backing_id = backing_id
        self.objects: Dict[str, Any] = {}

    def write(self, key: str, value: Any) -> Dict[str, Any]:
        self.objects[key] = value
        return {"status": "COMMITTED", "backing_id": self.backing_id, "key": key, "value_hash": root(value)}

    def read(self, key: str) -> Dict[str, Any]:
        if key not in self.objects:
            return {"status": "HOLE", "key": key, "backing_id": self.backing_id}
        return {"status": "READ", "key": key, "value": self.objects[key], "value_hash": root(self.objects[key])}


class AdapterRegistry:
    def __init__(self):
        self.adapters: Dict[str, Callable[..., Dict[str, Any]]] = {}

    def register(self, adapter_id: str, fn: Callable[..., Dict[str, Any]]) -> None:
        self.adapters[adapter_id] = fn

    def invoke(self, adapter_id: str, **kwargs) -> Dict[str, Any]:
        fn = self.adapters.get(adapter_id)
        if fn is None:
            return {"status": "UNRESOLVED_ADAPTER", "adapter_id": adapter_id, "request_hash": root(kwargs)}
        return fn(**kwargs)


class ObserverMemory:
    """Observer state is runtime input, not execution permission."""
    def __init__(self):
        self.signals: list[ObserverSignal] = []

    def absorb(self, source: str, subject: str, kind: str, payload: Dict[str, Any]) -> ObserverSignal:
        s = ObserverSignal(f"OBS-{uuid.uuid4().hex[:12]}", source, subject, kind, root(payload), time.time_ns())
        self.signals.append(s)
        return s

    @property
    def state_root(self) -> str:
        return root([asdict(s) for s in self.signals])


class RuntimeCarrier:
    def __init__(self, runtime_id: str):
        self.runtime_id = runtime_id
        self.tick = 0
        self.frame: Dict[str, Any] = {}

    def rewrite(self, *, mapping_root: str, observer_root: str, graph: Dict[str, Any], queue: list[Dict[str, Any]], mutation: Dict[str, Any]) -> Dict[str, Any]:
        self.tick += 1
        self.frame = {
            "runtime_id": self.runtime_id,
            "tick": self.tick,
            "mapping_root": mapping_root,
            "observer_root": observer_root,
            "graph_root": root(graph),
            "queue_root": root(queue),
            "last_mutation": mutation,
        }
        return self.frame


class AddressabilityFabric:
    """map -> aperture -> adapter/backing -> operation -> observer -> carrier rewrite"""
    def __init__(self, runtime_id: str = "braink://runtime/addressability"):
        self.ring1 = Ring1AddressSpace()
        self.ring2: Dict[str, Ring2BackingArray] = {}
        self.adapters = AdapterRegistry()
        self.observers = ObserverMemory()
        self.carrier = RuntimeCarrier(runtime_id)
        self.graph: Dict[str, Any] = {}
        self.queue: list[Dict[str, Any]] = []

    def create_backing(self, backing_id: str) -> Ring2BackingArray:
        b = Ring2BackingArray(backing_id)
        self.ring2[backing_id] = b
        return b

    def register_backing_adapter(self, adapter_id: str, backing_id: str) -> None:
        def adapter(*, logical: str, operation: str, payload: Any = None, **_) -> Dict[str, Any]:
            backing = self.ring2.get(backing_id)
            if backing is None:
                return {"status": "BACKING_UNAVAILABLE", "backing_id": backing_id}
            if operation == "WRITE":
                return backing.write(logical, payload)
            if operation == "READ":
                return backing.read(logical)
            return {"status": "UNSUPPORTED_OPERATION", "operation": operation}
        self.adapters.register(adapter_id, adapter)

    def map(self, logical: str, *, aperture: Optional[str] = None, adapter: Optional[str] = None, backing: Optional[str] = None) -> Address:
        if aperture and adapter:
            return self.ring1.bind(logical, aperture=aperture, adapter=adapter, backing=backing)
        return self.ring1.resolve(logical)

    def apply(self, logical: str, operation: str, payload: Any = None) -> Dict[str, Any]:
        addr = self.ring1.resolve(logical)
        if not addr.adapter:
            event = {"status": "HOLE", "logical": logical, "operation": operation}
            self.queue.append(event)
            self.graph[logical] = {"address_state": addr.state.value, "last_event": event}
            self._rewrite(event)
            return event
        result = self.adapters.invoke(addr.adapter, logical=logical, operation=operation, payload=payload, aperture=addr.aperture, backing=addr.backing)
        self.graph[logical] = {"address_state": addr.state.value, "aperture": addr.aperture, "backing": addr.backing, "adapter": addr.adapter, "last_result": result}
        self._rewrite(result)
        return result

    def observe(self, source: str, subject: str, kind: str, payload: Dict[str, Any]) -> ObserverSignal:
        signal = self.observers.absorb(source, subject, kind, payload)
        self.graph.setdefault(subject, {})["last_observer_signal"] = {"signal_id": signal.signal_id, "kind": signal.kind, "payload_hash": signal.payload_hash}
        self._rewrite({"observer_signal": signal.signal_id})
        return signal

    def _rewrite(self, mutation: Dict[str, Any]) -> None:
        self.carrier.rewrite(mapping_root=self.ring1.state_root, observer_root=self.observers.state_root, graph=self.graph, queue=self.queue, mutation=mutation)
