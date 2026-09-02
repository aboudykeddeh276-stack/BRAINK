#!/usr/bin/env python3
"""Canonical JSON transport for WBOS HTTP wrappers.

JSON values entering or leaving a WBOS HTTP wrapper are normalized through the
same KEX canonical representation. Receipts record software-observed boundary
facts only. Binary/multipart bodies are separate carrier types and require a
carrier-specific adapter rather than being silently treated as JSON.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from modules.kex_core.canonical_state import (
    CanonicalBoundary,
    WrapperAdapter,
    canonical_json,
    digest,
)

HTTP_LEDGER = BASE / "reports" / "kex-wbos" / "canonical-http-ledger.jsonl"


def _normalize_json_value(value: Any) -> Any:
    return json.loads(canonical_json(value).decode("utf-8"))


def _adapter(name: str) -> WrapperAdapter:
    return WrapperAdapter(
        name=name,
        ingress=_normalize_json_value,
        egress=_normalize_json_value,
    )


def _append(receipt: dict[str, Any]) -> int:
    HTTP_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with HTTP_LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")
    with HTTP_LEDGER.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def canonicalize_http_json(
    value: Any,
    *,
    direction: str,
    route: str,
    authority: str = "",
    identity: str | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Normalize one JSON value and emit a boundary receipt.

    direction must be INGRESS or EGRESS. The returned value is a detached,
    deterministic JSON-compatible object. Non-JSON values fail closed.
    """
    direction = direction.upper()
    if direction not in {"INGRESS", "EGRESS"}:
        raise ValueError("direction must be INGRESS or EGRESS")

    wrapper = f"http-{direction.lower()}"
    boundary = CanonicalBoundary()
    boundary.register(_adapter(wrapper))

    resolved_identity = identity or f"HTTP-{direction}-{digest(value)[:16]}"
    state = boundary.enter(
        wrapper,
        value,
        identity=resolved_identity,
        authority=authority,
        lineage=(f"http://wbos{route}",),
        dependency_hops=1,
        fan_out=1,
    )
    normalized = boundary.exit(wrapper, state, dependency_hops=1, fan_out=1)

    receipt = {
        "schema": "kex.wbos-canonical-http.v1",
        "evidenceLevel": "SOFTWARE_OBSERVED",
        "measurementClass": "STRUCTURAL_PROXY",
        "direction": direction,
        "route": route,
        "identity": state.identity,
        "canonicalDigest": state.state_digest,
        "identityPreserved": all(
            item.identity_preserved is not False for item in boundary.evidence
        ),
        "metrics": boundary.metrics(),
        "crossings": [item.as_dict() for item in boundary.evidence],
        "claimBoundary": (
            "Observed proof covers deterministic JSON normalization and round-trip "
            "preservation at this HTTP wrapper. It does not characterize binary carrier, "
            "network, processor, electrical, thermal, or physical propagation."
        ),
    }
    receipt["ledgerRow"] = _append(receipt)
    return normalized, receipt
