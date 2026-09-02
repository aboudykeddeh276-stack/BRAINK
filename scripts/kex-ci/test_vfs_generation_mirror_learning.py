#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "modules" / "kex_wbos"))

from lease_fencing import LeaseFenceRegistry  # noqa: E402
from mirror_learning import MirrorLearningLane  # noqa: E402
from vfs_generation import VFSGenerationStore  # noqa: E402


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        leases = LeaseFenceRegistry(root / "lease.json")
        store = VFSGenerationStore(root / "vfs", leases)
        mirror = MirrorLearningLane(root / "mirror")
        resource = "resource://vfs/canonical"

        l1 = leases.acquire(resource, "owner-A", 10, now=100.0)
        g1 = store.prepare(
            kex_identity="kex://system/root",
            parent_generation=None,
            objects=[{"identity": "cell://A1", "content": {"value": 1}}],
            observer_state={"observer": "operator", "value": 1},
            now=100.0,
        )
        store.persist_candidate(g1)
        p1 = store.promote(descriptor=g1, lease_resource=resource, owner="owner-A", fence=l1["fence"], now=101.0)
        require(p1["state"] == "PROMOTED", "first generation must promote")
        r1 = store.rehydrate()
        require(r1["state"] == "REHYDRATED", "canonical generation must rehydrate")

        learn1 = mirror.record_transition(
            observer="observer://operator",
            subject="kex://system/root",
            canonical_generation=g1["generationHash"],
            event_class="GENERATION_PROMOTED",
            before=None,
            after={"value": 1, "health": "HEALTHY"},
            evidence=[g1["generationHash"]],
            confidence=1.0,
            now=102.0,
        )
        require(learn1["state"] == "LEARNED", "mirror must learn first projection")

        leases.release(resource, "owner-A", l1["fence"], now=103.0)
        l2 = leases.acquire(resource, "owner-B", 10, now=104.0)
        require(l2["fence"] > l1["fence"], "new owner must have newer fence")

        stale = store.prepare(
            kex_identity="kex://system/root",
            parent_generation=None,
            objects=[{"identity": "cell://A1", "content": {"value": 99}}],
            now=104.0,
        )
        store.persist_candidate(stale)
        rejected_parent = store.promote(
            descriptor=stale,
            lease_resource=resource,
            owner="owner-B",
            fence=l2["fence"],
            now=105.0,
        )
        require(rejected_parent["reason"] == "STALE_PARENT", "generation must reject stale parent")

        g2 = store.prepare(
            kex_identity="kex://system/root",
            parent_generation=g1["generationHash"],
            objects=[{"identity": "cell://A1", "content": {"value": 2}}],
            observer_state={"observer": "operator", "value": 2},
            now=106.0,
        )
        store.persist_candidate(g2)

        old_owner = store.promote(
            descriptor=g2,
            lease_resource=resource,
            owner="owner-A",
            fence=l1["fence"],
            now=107.0,
        )
        require(old_owner["reason"] == "FENCED", "stale owner must never publish generation")

        p2 = store.promote(descriptor=g2, lease_resource=resource, owner="owner-B", fence=l2["fence"], now=107.0)
        require(p2["state"] == "PROMOTED", "current fenced owner must promote")
        r2 = store.rehydrate()
        require(r2["generationHash"] == g2["generationHash"], "rehydration must follow canonical HEAD")

        learned2 = mirror.record_transition(
            observer="observer://operator",
            subject="kex://system/root",
            canonical_generation=g2["generationHash"],
            event_class="REHYDRATION_AND_LEARNING_UPDATE",
            before={"value": 1, "health": "HEALTHY"},
            after={"value": 2, "health": "HEALTHY", "generation": 2},
            evidence=[g2["generationHash"]],
            confidence=1.0,
            now=108.0,
        )
        delta = learned2["projection"]["lastDelta"]
        require("value" in delta["changed"], "Mirror Lane must preserve learned change")
        require(delta["added"].get("generation") == 2, "Mirror Lane must preserve learned addition")

        rehydrated_mirror = mirror.rehydrate_projection(
            observer="observer://operator",
            subject="kex://system/root",
            canonical_generation=g2["generationHash"],
            canonical_state={"value": 2, "health": "HEALTHY", "generation": 2},
        )
        require(rehydrated_mirror["state"] == "REHYDRATED", "current mirror projection must rehydrate")

        transitioned = mirror.rehydrate_projection(
            observer="observer://operator",
            subject="kex://system/root",
            canonical_generation="future-generation",
            canonical_state={"value": 3},
        )
        require(
            transitioned["state"] == "REHYDRATED_WITH_VERSION_TRANSITION",
            "changed canonical generation must be explicit",
        )

    print("VFS_GENERATION_MIRROR_LEARNING_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
