#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "modules" / "kex_wbos"))

from lease_fencing import LeaseFenceRegistry  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = LeaseFenceRegistry(Path(tmp) / "lease-fences.json")
        first = registry.acquire("resource://vfs/test", "owner-A", 10, now=100.0)
        require(first["state"] == "ACQUIRED", "first owner must acquire")
        require(first["fence"] == 1, "first fence must be 1")

        held = registry.acquire("resource://vfs/test", "owner-B", 10, now=105.0)
        require(held["state"] == "HELD", "live lease must not be stolen")
        require(held["owner"] == "owner-A", "current owner must be reported")

        renewed = registry.heartbeat("resource://vfs/test", "owner-A", 1, now=106.0)
        require(renewed["state"] == "RENEWED", "current owner must renew")
        require(renewed["expiresAt"] == 116.0, "heartbeat must extend lease")

        takeover = registry.acquire("resource://vfs/test", "owner-B", 10, now=117.0)
        require(takeover["state"] == "ACQUIRED", "expired lease must permit takeover")
        require(takeover["fence"] == 2, "takeover must increment fence")
        require(takeover["priorOwner"] == "owner-A", "takeover lineage must record prior owner")

        stale_publish = registry.validate_fence("resource://vfs/test", "owner-A", 1, now=118.0)
        require(stale_publish["state"] == "FENCED", "resumed predecessor must be fenced")

        valid_publish = registry.validate_fence("resource://vfs/test", "owner-B", 2, now=118.0)
        require(valid_publish["state"] == "VALID", "new owner fence must validate")

        pending = registry.mark_effect("resource://vfs/test", "owner-B", 2, "EFFECT_PENDING", now=118.0)
        require(pending["state"] == "RECORDED", "current owner may record effect state")

        released = registry.release("resource://vfs/test", "owner-B", 2, now=119.0)
        require(released["state"] == "RELEASED", "current owner may release")

        third = registry.acquire("resource://vfs/test", "owner-C", 10, now=120.0)
        require(third["fence"] == 3, "fence must remain monotonic after release")
        require(third["effectState"] == "EFFECT_NOT_STARTED", "non-ambiguous effect state must reset on new generation")

        ambiguous = registry.mark_effect("resource://vfs/test", "owner-C", 3, "EFFECT_AMBIGUOUS", now=121.0)
        require(ambiguous["state"] == "RECORDED", "ambiguous effect must be representable")
        registry.release("resource://vfs/test", "owner-C", 3, now=122.0)
        fourth = registry.acquire("resource://vfs/test", "owner-D", 10, now=123.0)
        require(fourth["fence"] == 4, "second takeover must remain monotonic")
        require(fourth["effectState"] == "EFFECT_AMBIGUOUS", "ambiguous effect must survive ownership takeover for reconciliation")

        stale_effect = registry.mark_effect("resource://vfs/test", "owner-C", 3, "COMPLETED", now=124.0)
        require(stale_effect["state"] == "FENCED", "old owner must not publish completion after fencing")

        state = json.loads((Path(tmp) / "lease-fences.json").read_text())
        require(state["resources"]["resource://vfs/test"]["fence"] == 4, "durable state must preserve latest fence")

    print("LEASE_FENCING_PASS")


if __name__ == "__main__":
    main()
