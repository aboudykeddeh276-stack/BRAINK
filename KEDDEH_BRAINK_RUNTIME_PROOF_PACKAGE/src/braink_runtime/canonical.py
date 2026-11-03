"""Canonical serialization primitives.

Every hash produced anywhere in the BRAINK runtime flows through this module so
that identical logical objects always produce identical bytes, and therefore
identical digests, across processes, machines and restarts.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

__all__ = [
    "canonical_serialize",
    "canonical_bytes",
    "canonical_hash",
    "stable_namespace",
]


def canonical_serialize(obj: Dict[str, Any]) -> str:
    """Serialize a mapping to a deterministic JSON string.

    Rules: keys sorted, no insignificant whitespace, non-ASCII preserved as
    escaped sequences so the output is pure ASCII and byte-stable.
    """
    if obj is None:
        raise ValueError("canonical_serialize requires a non-None object")
    if not isinstance(obj, dict):
        raise ValueError("canonical_serialize requires a dict")
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def canonical_bytes(obj: Dict[str, Any]) -> bytes:
    """UTF-8 encoded form of :func:`canonical_serialize`."""
    return canonical_serialize(obj).encode("utf-8")


def canonical_hash(obj: Dict[str, Any]) -> str:
    """SHA-256 hex digest of the canonical serialization of ``obj``."""
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def stable_namespace(namespace: str, name: str) -> str:
    """Join a namespace and a name into a stable, human-readable key."""
    if namespace is None or name is None:
        raise ValueError("namespace and name must not be None")
    return "{0}:{1}".format(namespace, name)
