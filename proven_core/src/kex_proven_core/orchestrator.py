from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from .core import EvidenceState, ProofLedger, Registry, digest


@dataclass(frozen=True)
class Capability:
    identity: str
    subject: str
    operation: str
    authority: str


@dataclass(frozen=True)
class Route:
    identity: str
    source: str
    target: str
    relation: str
    required_capability: str


@dataclass(frozen=True)
class AdapterResult:
    adapter: str
    executed: bool
    payload: Mapping[str, object]


class DurableRuntimeRegistry:
    def __init__(self, logical_registry: Registry) -> None:
        self.logical_registry = logical_registry
        self._capabilities: dict[str, Capability] = {}
        self._routes: dict[str, Route] = {}
        self._adapters: dict[str, Callable[[Mapping[str, object]], AdapterResult]] = {}

    def capability(self, capability: Capability) -> None:
        self.logical_registry.get(capability.subject)
        prior = self._capabilities.get(capability.identity)
        if prior and prior != capability:
            raise ValueError("capability identity is immutable")
        self._capabilities[capability.identity] = capability

    def route(self, route: Route) -> None:
        self.logical_registry.get(route.source)
        self.logical_registry.get(route.target)
        if route.required_capability not in self._capabilities:
            raise ValueError("route capability is not registered")
        prior = self._routes.get(route.identity)
        if prior and prior != route:
            raise ValueError("route identity is immutable")
        self._routes[route.identity] = route

    def adapter(self, identity: str, handler: Callable[[Mapping[str, object]], AdapterResult]) -> None:
        if identity in self._adapters:
            raise ValueError("adapter identity already bound")
        self._adapters[identity] = handler

    def resolve(self, route_id: str) -> tuple[Route, Capability]:
        route = self._routes[route_id]
        return route, self._capabilities[route.required_capability]

    def invoke_adapter(self, adapter_id: str, payload: Mapping[str, object]) -> AdapterResult:
        return self._adapters[adapter_id](payload)


class Supervisor:
    """One deterministic reconciliation pass; no hidden loop or authority amplification."""

    def __init__(self, registry: DurableRuntimeRegistry, ledger: ProofLedger) -> None:
        self.registry = registry
        self.ledger = ledger

    def reconcile(self, *, route_id: str, actor: str, operation: str,
                  adapter_id: str, payload: Mapping[str, object]) -> AdapterResult:
        route, capability = self.registry.resolve(route_id)
        if capability.authority != actor:
            raise PermissionError("actor lacks explicit capability authority")
        if capability.operation != operation:
            raise PermissionError("capability does not authorize operation")
        if capability.subject != route.target:
            raise PermissionError("capability subject does not match route target")

        result = self.registry.invoke_adapter(adapter_id, payload)
        state = EvidenceState.EXECUTED_LOCAL if result.executed else EvidenceState.NOT_OBSERVED
        self.ledger.append(
            subject=route.target,
            event="SUPERVISOR_RECONCILE",
            state=state,
            payload={
                "route": route.identity,
                "relation": route.relation,
                "adapter": result.adapter,
                "executed": result.executed,
                "result_hash": digest(result.payload),
            },
        )
        return result
