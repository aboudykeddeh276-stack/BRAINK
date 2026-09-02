from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from virtual_address_fabric import (
    AddressState,
    ExecutionReceipt,
    ObserverClass,
    ObserverEvent,
    VirtualAddressFabric,
    sha,
)
from vfs_generation import VFSGenerationStore


class VFSAddressRejection(RuntimeError):
    pass


@dataclass
class VFSGenerationHeadAdapter:
    """Ring-2 adapter exposing one fenced VFS generation HEAD as backing state.

    Logical address identity remains in Ring-1. The VFS generation descriptor and
    HEAD are backing/proof carriers, not the logical identity itself.
    """

    adapter_id: str
    stores: Mapping[str, VFSGenerationStore]

    def resolve(self, backing_ref: str) -> Any:
        store = self.stores[backing_ref]
        return store.rehydrate()

    def commit(self, backing_ref: str, operation: str, payload: Any) -> Mapping[str, Any]:
        store = self.stores[backing_ref]
        if operation == "READ_HEAD":
            head = store.read_head(allow_missing=True)
            return {
                "state": "HEAD_ABSENT" if head is None else "HEAD_READ",
                "backingRef": backing_ref,
                "head": head,
                "effectRoot": sha(head),
            }
        if operation != "PROMOTE_GENERATION":
            raise ValueError(f"unsupported VFS address operation: {operation}")
        if not isinstance(payload, dict):
            raise TypeError("PROMOTE_GENERATION requires mapping payload")

        current = store.read_head(allow_missing=True)
        descriptor = store.prepare(
            kex_identity=str(payload["kex_identity"]),
            parent_generation=current.get("generationHash") if current else None,
            objects=list(payload.get("objects") or []),
            semantic_bindings=list(payload.get("semantic_bindings") or []),
            proof_refs=list(payload.get("proof_refs") or []),
            observer_state=dict(payload.get("observer_state") or {}),
            now=payload.get("now"),
        )
        candidate = store.persist_candidate(descriptor)
        result = store.promote(
            descriptor=descriptor,
            lease_resource=str(payload["lease_resource"]),
            owner=str(payload["owner"]),
            fence=int(payload["fence"]),
            now=payload.get("now"),
        )
        if result.get("state") != "PROMOTED":
            raise VFSAddressRejection(f"VFS_PROMOTION_REJECTED:{result.get('reason')}")
        return {
            "state": "PROMOTED",
            "backingRef": backing_ref,
            "generationHash": result["generationHash"],
            "headHash": result["headHash"],
            "candidate": str(candidate),
            "fence": result["fence"],
            "owner": result["owner"],
            "effectRoot": sha(result),
        }


def bind_vfs_head(
    fabric: VirtualAddressFabric,
    *,
    logical_address: str,
    backing_ref: str,
    store: VFSGenerationStore,
    aperture_id: str | None = None,
    adapter_id: str = "adapter://kex/vfs-generation-head",
) -> VFSGenerationHeadAdapter:
    adapter = VFSGenerationHeadAdapter(adapter_id=adapter_id, stores={backing_ref: store})
    fabric.register_adapter(adapter)
    fabric.bind_aperture(
        logical_address,
        aperture_id=aperture_id or f"aperture://{backing_ref}/HEAD",
        adapter_id=adapter_id,
        backing_ref=backing_ref,
        writable=True,
    )
    return adapter


def execute_vfs_address_operation(
    fabric: VirtualAddressFabric,
    logical_address: str,
    operation: str,
    payload: Any,
) -> ExecutionReceipt:
    """Execute a VFS-bound address operation while preserving rule rejection as a receipt."""
    route = fabric.resolve(logical_address)
    if route.state in {AddressState.HOLE, AddressState.REJECTED}:
        return fabric.apply(logical_address, operation, payload)
    try:
        return fabric.apply(logical_address, operation, payload)
    except VFSAddressRejection as exc:
        event = ObserverEvent(
            ObserverClass.CONTRADICTION,
            "adapter://kex/vfs-generation-head",
            {
                "logical_address": logical_address,
                "operation": operation,
                "reason": str(exc),
                "route_root": route.route_root,
            },
        )
        fabric.observer.integrate(event)
        return ExecutionReceipt(
            logical_address=logical_address,
            generation=route.generation,
            operation=operation,
            status="REJECTED_EFFECT",
            adapter_id=route.aperture.adapter_id if route.aperture else None,
            backing_ref=route.aperture.backing_ref if route.aperture else None,
            effect_root=None,
            failure_reason=str(exc),
            observer_root=fabric.observer.root,
            produced_at_ns=event.observed_at_ns,
        )
