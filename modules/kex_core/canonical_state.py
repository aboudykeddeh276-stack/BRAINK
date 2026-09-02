#!/usr/bin/env python3
"""KEX canonical-state boundary runtime.

This module implements the proven software-level invariant:
heterogeneous wrapper state is normalized into one deterministic canonical
representation before it is allowed to cross a wrapper boundary.

It makes no hardware-performance claim. It records software propagation and
identity evidence that can later be correlated with lower execution layers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Callable, Mapping

SCHEMA = "kex.canonical-state.v1"
EVIDENCE_LEVEL = "SOFTWARE_OBSERVED"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> bytes:
    """Return stable UTF-8 JSON bytes for supported canonical state values."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class BoundaryEvidence:
    wrapper: str
    direction: str
    input_digest: str
    canonical_digest: str
    output_digest: str | None
    identity_preserved: bool | None
    dependency_hops: int
    propagated_units: int
    fan_out: int
    timestamp: str = field(default_factory=_now)

    @property
    def propagation_cost(self) -> int:
        return self.dependency_hops * self.propagated_units * max(self.fan_out, 1)

    def as_dict(self) -> dict[str, Any]:
        return {
            "wrapper": self.wrapper,
            "direction": self.direction,
            "inputDigest": self.input_digest,
            "canonicalDigest": self.canonical_digest,
            "outputDigest": self.output_digest,
            "identityPreserved": self.identity_preserved,
            "dependencyHops": self.dependency_hops,
            "propagatedUnits": self.propagated_units,
            "fanOut": self.fan_out,
            "propagationCost": self.propagation_cost,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class CanonicalState:
    identity: str
    payload: Any
    lineage: tuple[str, ...]
    authority: str
    revision: int = 1
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def material(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "identity": self.identity,
            "revision": self.revision,
            "authority": self.authority,
            "lineage": list(self.lineage),
            "payload": self.payload,
            "metadata": dict(self.metadata),
        }

    @property
    def state_digest(self) -> str:
        return digest(self.material())

    def envelope(self) -> dict[str, Any]:
        material = self.material()
        return {
            **material,
            "stateDigest": digest(material),
            "evidenceLevel": EVIDENCE_LEVEL,
        }


Ingress = Callable[[Any], Any]
Egress = Callable[[Any], Any]


@dataclass
class WrapperAdapter:
    name: str
    ingress: Ingress
    egress: Egress


class CanonicalBoundary:
    """Adapter registry and canonical boundary gate.

    Every crossing is wrapper -> canonical -> wrapper. Direct wrapper-to-wrapper
    conversion is intentionally absent from the API.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, WrapperAdapter] = {}
        self.evidence: list[BoundaryEvidence] = []

    def register(self, adapter: WrapperAdapter) -> None:
        if not adapter.name:
            raise ValueError("adapter name is required")
        if adapter.name in self._adapters:
            raise ValueError(f"adapter already registered: {adapter.name}")
        self._adapters[adapter.name] = adapter

    def _adapter(self, name: str) -> WrapperAdapter:
        try:
            return self._adapters[name]
        except KeyError as exc:
            raise KeyError(f"wrapper adapter not registered: {name}") from exc

    def enter(
        self,
        wrapper: str,
        raw_state: Any,
        *,
        identity: str,
        authority: str,
        lineage: tuple[str, ...] = (),
        dependency_hops: int = 1,
        fan_out: int = 1,
    ) -> CanonicalState:
        adapter = self._adapter(wrapper)
        normalized = adapter.ingress(raw_state)
        state = CanonicalState(
            identity=identity,
            payload=normalized,
            lineage=(*lineage, f"wrapper://{wrapper}"),
            authority=authority,
        )
        propagated_units = len(canonical_json(normalized))
        self.evidence.append(
            BoundaryEvidence(
                wrapper=wrapper,
                direction="INGRESS",
                input_digest=digest(raw_state),
                canonical_digest=state.state_digest,
                output_digest=None,
                identity_preserved=None,
                dependency_hops=max(dependency_hops, 1),
                propagated_units=propagated_units,
                fan_out=max(fan_out, 1),
            )
        )
        return state

    def exit(
        self,
        wrapper: str,
        state: CanonicalState,
        *,
        dependency_hops: int = 1,
        fan_out: int = 1,
    ) -> Any:
        adapter = self._adapter(wrapper)
        outward = adapter.egress(state.payload)
        roundtrip_payload = adapter.ingress(outward)
        identity_preserved = digest(roundtrip_payload) == digest(state.payload)
        evidence = BoundaryEvidence(
            wrapper=wrapper,
            direction="EGRESS",
            input_digest=state.state_digest,
            canonical_digest=state.state_digest,
            output_digest=digest(outward),
            identity_preserved=identity_preserved,
            dependency_hops=max(dependency_hops, 1),
            propagated_units=len(canonical_json(outward)),
            fan_out=max(fan_out, 1),
        )
        self.evidence.append(evidence)
        if not identity_preserved:
            raise ValueError(f"canonical identity loss crossing wrapper: {wrapper}")
        return outward

    def traverse(
        self,
        source_wrapper: str,
        target_wrapper: str,
        raw_state: Any,
        *,
        identity: str,
        authority: str,
        dependency_hops: int = 1,
        fan_out: int = 1,
    ) -> tuple[CanonicalState, Any]:
        state = self.enter(
            source_wrapper,
            raw_state,
            identity=identity,
            authority=authority,
            dependency_hops=dependency_hops,
            fan_out=fan_out,
        )
        outward = self.exit(
            target_wrapper,
            state,
            dependency_hops=dependency_hops,
            fan_out=fan_out,
        )
        return state, outward

    def metrics(self) -> dict[str, Any]:
        if not self.evidence:
            return {
                "crossings": 0,
                "totalPropagationCost": 0,
                "peakSignalDensity": 0,
                "meanPropagationCost": 0.0,
            }
        costs = [e.propagation_cost for e in self.evidence]
        densities = [e.propagated_units * e.fan_out for e in self.evidence]
        return {
            "crossings": len(self.evidence),
            "totalPropagationCost": sum(costs),
            "peakSignalDensity": max(densities),
            "meanPropagationCost": sum(costs) / len(costs),
        }


def json_adapter(name: str = "json") -> WrapperAdapter:
    def ingress(raw: Any) -> Any:
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        if isinstance(raw, str):
            return json.loads(raw)
        return json.loads(canonical_json(raw).decode("utf-8"))

    def egress(payload: Any) -> str:
        return canonical_json(payload).decode("utf-8")

    return WrapperAdapter(name=name, ingress=ingress, egress=egress)


def mapping_adapter(name: str) -> WrapperAdapter:
    def ingress(raw: Any) -> Any:
        if not isinstance(raw, Mapping):
            raise TypeError(f"{name} ingress requires a mapping")
        return json.loads(canonical_json(dict(raw)).decode("utf-8"))

    def egress(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise TypeError(f"{name} egress requires canonical mapping payload")
        return json.loads(canonical_json(dict(payload)).decode("utf-8"))

    return WrapperAdapter(name=name, ingress=ingress, egress=egress)
