"""Deterministic identity generation and collision detection."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .canonical import canonical_hash, canonical_serialize, stable_namespace

__all__ = [
    "CollisionError",
    "generate_component_id",
    "generate_skill_id",
    "generate_service_id",
    "detect_collision",
    "IdentityRegistry",
]


class CollisionError(Exception):
    """Raised when a single identity maps to two different input tuples."""


def _require(name: str, value: Any) -> str:
    if value is None or not isinstance(value, str) or value.strip() == "":
        raise ValueError("%s must be a non-empty string" % name)
    return value


def generate_component_id(namespace: str, name: str, version: str) -> str:
    _require("namespace", namespace)
    _require("name", name)
    _require("version", version)
    return canonical_hash(
        {"namespace": namespace, "name": name, "version": version}
    )


def generate_skill_id(namespace: str, skill_name: str) -> str:
    _require("namespace", namespace)
    _require("skill_name", skill_name)
    return canonical_hash({"namespace": namespace, "skill_name": skill_name})


def generate_service_id(namespace: str, service_name: str, endpoint: str) -> str:
    _require("namespace", namespace)
    _require("service_name", service_name)
    _require("endpoint", endpoint)
    return canonical_hash(
        {"namespace": namespace, "service_name": service_name, "endpoint": endpoint}
    )


def detect_collision(id1: str, id2: str) -> bool:
    """True when the two identifiers are identical (i.e. a collision)."""
    if id1 is None or id2 is None:
        raise ValueError("identifiers must not be None")
    return id1 == id2


class IdentityRegistry:
    """In-memory registry that refuses to let one ID mean two things."""

    def __init__(self) -> None:
        self._records: Dict[str, Dict[str, Any]] = {}

    def register(self, identity: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        _require("identity", identity)
        if inputs is None or not isinstance(inputs, dict):
            raise ValueError("inputs must be a dict")
        fingerprint = canonical_serialize(inputs)
        existing = self._records.get(identity)
        if existing is not None:
            if existing["fingerprint"] != fingerprint:
                raise CollisionError(
                    "identity %s already registered with different inputs" % identity
                )
            return existing
        record = {
            "identity": identity,
            "inputs": dict(inputs),
            "fingerprint": fingerprint,
        }
        self._records[identity] = record
        return record

    def register_component(self, namespace: str, name: str, version: str) -> str:
        identity = generate_component_id(namespace, name, version)
        self.register(
            identity,
            {
                "kind": "component",
                "namespace": namespace,
                "name": name,
                "version": version,
                "key": stable_namespace(namespace, name),
            },
        )
        return identity

    def get(self, identity: str) -> Optional[Dict[str, Any]]:
        return self._records.get(identity)

    def contains(self, identity: str) -> bool:
        return identity in self._records

    def all_identities(self) -> list:
        return sorted(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def export(self) -> Dict[str, Any]:
        return {
            "count": len(self._records),
            "identities": {
                k: v["inputs"] for k, v in sorted(self._records.items())
            },
        }
