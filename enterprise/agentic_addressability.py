from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, Iterable, Mapping, Optional


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def root(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


class AgentAddressState(str, Enum):
    HOLE = "HOLE"
    BOUND = "BOUND"
    REVOKED = "REVOKED"


class TaskState(str, Enum):
    DECLARED = "DECLARED"
    EXECUTED = "EXECUTED"
    DEFERRED = "DEFERRED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class AgentIdentity:
    agent_id: str
    team_id: str
    roles: tuple[str, ...]
    capabilities: tuple[str, ...]
    authority_root: str

    @classmethod
    def create(cls, agent_id: str, team_id: str, roles: Iterable[str], capabilities: Iterable[str], authority: Mapping[str, Any]):
        return cls(agent_id, team_id, tuple(sorted(set(roles))), tuple(sorted(set(capabilities))), root(authority))


@dataclass(frozen=True)
class AgentBinding:
    logical_address: str
    state: AgentAddressState
    agent_id: Optional[str]
    capability: Optional[str]
    aperture_id: Optional[str]
    reason: Optional[str]
    generation: int


@dataclass(frozen=True)
class AgentTask:
    task_id: str
    logical_target: str
    required_capability: str
    operation: str
    payload: Mapping[str, Any]
    predecessor_receipt_root: Optional[str] = None

    @property
    def task_root(self) -> str:
        return root(asdict(self))


@dataclass(frozen=True)
class AgentReceipt:
    task_id: str
    task_root: str
    state: TaskState
    agent_id: Optional[str]
    capability: str
    effect: Mapping[str, Any]
    failure_reason: Optional[str]
    produced_at_ns: int
    predecessor_receipt_root: Optional[str]

    @property
    def receipt_root(self) -> str:
        return root(asdict(self))


@dataclass(frozen=True)
class AgentObserverEvent:
    source: str
    subject: str
    kind: str
    payload: Mapping[str, Any]
    produced_at_ns: int = field(default_factory=time.time_ns)

    @property
    def event_root(self) -> str:
        return root(asdict(self))


class AgentRegistry:
    def __init__(self):
        self.identities: Dict[str, AgentIdentity] = {}
        self.bindings: Dict[str, AgentBinding] = {}
        self.handlers: Dict[tuple[str, str], Callable[[AgentTask], Mapping[str, Any]]] = {}
        self.generation = 0

    def register_agent(self, identity: AgentIdentity) -> None:
        self.identities[identity.agent_id] = identity

    def register_handler(self, agent_id: str, capability: str, handler: Callable[[AgentTask], Mapping[str, Any]]) -> None:
        identity = self.identities.get(agent_id)
        if identity is None:
            raise KeyError("unknown agent")
        if capability not in identity.capabilities:
            raise PermissionError("capability not declared by agent")
        self.handlers[(agent_id, capability)] = handler

    def map_hole(self, logical_address: str, capability: str, reason: str) -> AgentBinding:
        self.generation += 1
        binding = AgentBinding(logical_address, AgentAddressState.HOLE, None, capability, None, reason, self.generation)
        self.bindings[logical_address] = binding
        return binding

    def bind(self, logical_address: str, *, agent_id: str, capability: str, aperture_id: str) -> AgentBinding:
        identity = self.identities.get(agent_id)
        if identity is None:
            raise KeyError("unknown agent")
        if capability not in identity.capabilities:
            raise PermissionError("agent lacks capability")
        existing = self.bindings.get(logical_address)
        if existing and existing.state == AgentAddressState.REVOKED:
            raise RuntimeError("REVOKED_AGENT_ROUTE_REQUIRES_REPAIR")
        self.generation += 1
        binding = AgentBinding(logical_address, AgentAddressState.BOUND, agent_id, capability, aperture_id, None, self.generation)
        self.bindings[logical_address] = binding
        return binding

    def revoke(self, logical_address: str, reason: str) -> AgentBinding:
        current = self.bindings.get(logical_address)
        self.generation += 1
        binding = AgentBinding(logical_address, AgentAddressState.REVOKED, None, current.capability if current else None, None, reason, self.generation)
        self.bindings[logical_address] = binding
        return binding

    def resolve(self, logical_address: str, required_capability: str) -> AgentBinding:
        binding = self.bindings.get(logical_address)
        if binding is None:
            return self.map_hole(logical_address, required_capability, "AGENT_OR_CAPABILITY_UNBOUND")
        if binding.capability != required_capability:
            return self.map_hole(logical_address, required_capability, "BOUND_ROUTE_CAPABILITY_MISMATCH")
        return binding

    @property
    def state_root(self) -> str:
        return root({
            "identities": {k: asdict(v) for k, v in sorted(self.identities.items())},
            "bindings": {k: asdict(v) for k, v in sorted(self.bindings.items())},
            "handlers": sorted(f"{a}:{c}" for a, c in self.handlers.keys()),
        })


class BrainKAgenticFabric:
    def __init__(self):
        self.registry = AgentRegistry()
        self.receipts: list[AgentReceipt] = []
        self.observers: list[AgentObserverEvent] = []
        self.continuation_queue: list[dict[str, Any]] = []
        self.carrier_tick = 0
        self.carrier_frame: Dict[str, Any] = {}

    def dispatch(self, task: AgentTask) -> AgentReceipt:
        binding = self.registry.resolve(task.logical_target, task.required_capability)
        if binding.state == AgentAddressState.HOLE:
            receipt = AgentReceipt(task.task_id, task.task_root, TaskState.DEFERRED, None, task.required_capability,
                                   {"route_state": "HOLE", "logical_target": task.logical_target, "reason": binding.reason},
                                   binding.reason, time.time_ns(), task.predecessor_receipt_root)
            self.receipts.append(receipt)
            self.continuation_queue.append({"task_id": task.task_id, "logical_target": task.logical_target,
                                            "required_capability": task.required_capability,
                                            "continuation": "WAIT_FOR_APERTURE_BINDING"})
            self._rewrite({"receipt_root": receipt.receipt_root})
            return receipt
        if binding.state == AgentAddressState.REVOKED:
            receipt = AgentReceipt(task.task_id, task.task_root, TaskState.REJECTED, None, task.required_capability,
                                   {"route_state": "REVOKED"}, binding.reason, time.time_ns(), task.predecessor_receipt_root)
            self.receipts.append(receipt)
            self._rewrite({"receipt_root": receipt.receipt_root})
            return receipt
        assert binding.agent_id is not None
        handler = self.registry.handlers.get((binding.agent_id, task.required_capability))
        if handler is None:
            receipt = AgentReceipt(task.task_id, task.task_root, TaskState.DEFERRED, binding.agent_id,
                                   task.required_capability, {"route_state": "BOUND", "handler_state": "HOLE",
                                   "aperture_id": binding.aperture_id}, "HANDLER_UNBOUND", time.time_ns(),
                                   task.predecessor_receipt_root)
            self.receipts.append(receipt)
            self.continuation_queue.append({"task_id": task.task_id, "agent_id": binding.agent_id,
                                            "required_capability": task.required_capability,
                                            "continuation": "WAIT_FOR_HANDLER_BINDING"})
            self._rewrite({"receipt_root": receipt.receipt_root})
            return receipt
        try:
            effect = dict(handler(task))
            state, failure = TaskState.EXECUTED, None
        except Exception as exc:
            effect, state, failure = {"exception_type": type(exc).__name__}, TaskState.REJECTED, str(exc)
        receipt = AgentReceipt(task.task_id, task.task_root, state, binding.agent_id, task.required_capability,
                               effect, failure, time.time_ns(), task.predecessor_receipt_root)
        self.receipts.append(receipt)
        self._rewrite({"receipt_root": receipt.receipt_root})
        return receipt

    def observe(self, event: AgentObserverEvent) -> str:
        self.observers.append(event)
        self._rewrite({"observer_event_root": event.event_root})
        return event.event_root

    def conflict_review(self, subject: str) -> Mapping[str, Any]:
        relevant = [e for e in self.observers if e.subject == subject]
        contradiction = any(e.kind == "CONTRADICTION" for e in relevant)
        result = {"subject": subject, "observer_count": len(relevant), "contradiction": contradiction,
                  "observer_root": root([e.event_root for e in relevant]),
                  "decision": "REVIEW_REQUIRED" if contradiction else "NO_CONFLICT_OBSERVED"}
        self._rewrite({"conflict_review": result})
        return result

    def _rewrite(self, mutation: Mapping[str, Any]) -> None:
        self.carrier_tick += 1
        self.carrier_frame = {
            "schema": "braink.agentic-carrier/v1",
            "tick": self.carrier_tick,
            "registry_root": self.registry.state_root,
            "receipt_root": root([r.receipt_root for r in self.receipts]),
            "observer_root": root([o.event_root for o in self.observers]),
            "continuation_root": root(self.continuation_queue),
            "last_mutation": dict(mutation),
        }
        self.carrier_frame["carrier_root"] = root(self.carrier_frame)
