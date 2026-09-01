#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "modules" / "kex_wbos"))

from lease_fencing import LeaseFenceRegistry  # noqa: E402
from vfs_generation import VFSGenerationStore  # noqa: E402
from virtual_address_fabric import AddressState, VirtualAddressFabric  # noqa: E402
from vfs_address_bridge import bind_vfs_head, execute_vfs_address_operation  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    logical = "kex://vfs/app-casepath/HEAD"
    resource = "resource://vfs/app-casepath/HEAD"

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        leases = LeaseFenceRegistry(root / "lease-fences.json")
        store = VFSGenerationStore(root / "vfs", leases)
        fabric = VirtualAddressFabric()

        unresolved = fabric.resolve(logical)
        require(unresolved.state == AddressState.HOLE, "unresolved VFS HEAD must become a typed HOLE")
        deferred = fabric.apply(logical, "PROMOTE_GENERATION", {"ignored": True})
        require(deferred.status == "DEFERRED_HOLE", "operation against unbound HEAD must defer with receipt")

        first = leases.acquire(resource, "owner-A", 10, now=100.0)
        require(first["state"] == "ACQUIRED" and first["fence"] == 1, "owner-A must acquire fence 1")
        bind_vfs_head(fabric, logical_address=logical, backing_ref="app://casepath", store=store)

        promoted = execute_vfs_address_operation(
            fabric,
            logical,
            "PROMOTE_GENERATION",
            {
                "kex_identity": "app://casepath",
                "objects": [{"identity": "page://casepath/your-data", "content": {"marker": "RING1-VFS-R1"}}],
                "semantic_bindings": [{"logical": logical, "target": "page://casepath/your-data"}],
                "proof_refs": ["BRAINK_VIRTUAL_ADDRESS_FABRIC_R1"],
                "observer_state": {"publicReadback": "OBSERVER_PENDING"},
                "lease_resource": resource,
                "owner": "owner-A",
                "fence": 1,
                "now": 101.0,
            },
        )
        require(promoted.status == "COMMITTED", "valid fenced VFS generation must commit through aperture")
        head = store.read_head()
        require(head["kexIdentity"] == "app://casepath", "HEAD must preserve logical KEX identity")
        require(head["fence"] == 1, "HEAD must preserve the resource-side fence")
        rehydrated = store.rehydrate()
        require(rehydrated["state"] == "REHYDRATED", "promoted generation must rehydrate")

        takeover = leases.acquire(resource, "owner-B", 10, now=112.0)
        require(takeover["state"] == "ACQUIRED" and takeover["fence"] == 2, "successor must acquire fence 2")
        stale = execute_vfs_address_operation(
            fabric,
            logical,
            "PROMOTE_GENERATION",
            {
                "kex_identity": "app://casepath",
                "objects": [{"identity": "page://casepath/your-data", "content": {"marker": "STALE"}}],
                "lease_resource": resource,
                "owner": "owner-A",
                "fence": 1,
                "now": 113.0,
            },
        )
        require(stale.status == "REJECTED_EFFECT", "stale owner must produce a rejection receipt, not a false commit")
        require("FENCED" in str(stale.failure_reason), "rejection receipt must identify the fence failure")
        after = store.read_head()
        require(after["generationHash"] == head["generationHash"], "stale owner must not replace canonical HEAD")

    print("VFS_ADDRESS_BRIDGE_PASS")


if __name__ == "__main__":
    main()
