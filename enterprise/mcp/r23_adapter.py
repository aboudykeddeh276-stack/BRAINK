from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from enterprise.foundry_closure_r23 import (
    CustomerFileLifecycle,
    DurableStore,
    HRSupervisionRuntime,
    PublicationRuntime,
    ResearchPromotionGate,
)


ALLOWED_ACTIONS = {
    "hr.lease.acquire",
    "hr.lease.replace_rehydrate",
    "customer.lifecycle.create",
    "customer.lifecycle.transition",
    "customer.lifecycle.event",
    "research.promotion.evaluate",
    "publishing.stage",
    "publishing.project_internal",
    "frontage.release_internal",
    "domain.public_activation.request",
}


def _receipt_dict(receipt: Any) -> dict[str, Any]:
    return {**asdict(receipt), "receipt_root": receipt.receipt_root}


class R23ClosureToolAdapter:
    """Thin callable boundary over the resident R23 foundary-closure mechanics."""

    def __init__(self, state_path: str | Path):
        self.store = DurableStore(state_path)
        self.hr = HRSupervisionRuntime(self.store)
        self.customers = CustomerFileLifecycle(self.store)
        self.research = ResearchPromotionGate(self.store)
        self.publishing = PublicationRuntime(self.store)

    def state(self) -> dict[str, Any]:
        state = self.store.state
        return {
            "status": "PASS",
            "address": "runtime://braink/r23-closure",
            "generation": state.get("generation", 0),
            "state_root": state.get("state_root"),
            "counts": {
                "leases": len(state.get("leases", {})),
                "customer_files": len(state.get("customer_files", {})),
                "research": len(state.get("research", {})),
                "publications": len(state.get("publications", {})),
                "domain_intents": len(state.get("domain_intents", {})),
                "frontage_releases": len(state.get("frontage_releases", {})),
                "receipts": len(state.get("receipts", [])),
            },
        }

    def operate(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action not in ALLOWED_ACTIONS:
            raise PermissionError(f"ACTION_NOT_EXPOSED:{action}")
        before = self.store.state.get("state_root")
        dispatch = {
            "hr.lease.acquire": lambda: self.hr.acquire(payload["lease_id"], payload["supervisor_id"], payload["subject_id"], int(payload["ttl_ns"]), payload.get("now_ns")),
            "hr.lease.replace_rehydrate": lambda: self.hr.expire_and_replace(payload["subject_id"], payload["lease_id"], payload["supervisor_id"], int(payload["ttl_ns"]), int(payload["now_ns"])),
            "customer.lifecycle.create": lambda: self.customers.create(payload["file_id"], payload["customer_id"], payload.get("consent", {})),
            "customer.lifecycle.transition": lambda: self.customers.transition(payload["file_id"], payload["target"], payload.get("reason", "")),
            "customer.lifecycle.event": lambda: self.customers.append_event(payload["file_id"], payload["kind"], payload.get("payload", {})),
            "research.promotion.evaluate": lambda: self.research.evaluate(payload["research_id"], payload.get("claims", []), payload.get("sources", []), payload.get("replays", []), payload.get("independent_verifier")),
            "publishing.stage": lambda: self.publishing.stage(payload["release_id"], payload.get("artifacts", []), payload["frontage_id"], payload.get("approval", {})),
            "publishing.project_internal": lambda: self.publishing.publish_internal(payload["release_id"], payload["projection_ref"]),
            "frontage.release_internal": lambda: self.publishing.bind_frontage_release(payload["release_id"], payload["frontage"], payload["landing_page"], payload.get("route_path", "/")),
            "domain.public_activation.request": lambda: self.publishing.request_public_activation(payload["release_id"], payload["domain"], payload.get("dns_changes", []), payload.get("tls_required", True), None),
        }
        receipt = _receipt_dict(dispatch[action]())
        after = self.store.state.get("state_root")
        return {
            "status": receipt["status"],
            "action": action,
            "subject": receipt["subject"],
            "state_before_root": before,
            "state_after_root": after,
            "receipt_root": receipt["receipt_root"],
            "receipt": receipt,
            "descendants": self._descendants_for(action, payload, receipt),
            "readback": self.state(),
            "blockers": self._blockers(receipt),
        }

    def receipt(self, receipt_root: str) -> dict[str, Any]:
        for item in reversed(self.store.state.get("receipts", [])):
            if item.get("receipt_root") == receipt_root:
                return {"status": "PASS", "address": f"receipt://{receipt_root}", "receipt": item}
        raise KeyError("RECEIPT_NOT_FOUND")

    def list_descendants(self) -> dict[str, Any]:
        state = self.store.state
        addresses: list[str] = []
        addresses.extend(f"lease://{key}" for key in sorted(state.get("leases", {})))
        addresses.extend(f"customer-file://{key}" for key in sorted(state.get("customer_files", {})))
        addresses.extend(f"research://{key}" for key in sorted(state.get("research", {})))
        addresses.extend(f"publication://{key}" for key in sorted(state.get("publications", {})))
        addresses.extend(f"frontage-release://{key}" for key in sorted(state.get("frontage_releases", {})))
        addresses.extend(f"domain-intent://{key}" for key in sorted(state.get("domain_intents", {})))
        return {"status": "PASS", "parent": "runtime://braink/r23-closure", "descendants": addresses}

    @staticmethod
    def _blockers(receipt: dict[str, Any]) -> list[str]:
        if receipt.get("status") == "DEFERRED_EXTERNAL_ACTUATOR":
            return [str(receipt.get("effect", {}).get("missing", "EXTERNAL_ACTUATOR_REQUIRED"))]
        return []

    @staticmethod
    def _descendants_for(action: str, payload: dict[str, Any], receipt: dict[str, Any]) -> list[str]:
        result = [f"receipt://{receipt['receipt_root']}"]
        mapping = {
            "hr.lease.acquire": ("lease", "subject_id"),
            "hr.lease.replace_rehydrate": ("lease", "subject_id"),
            "customer.lifecycle.create": ("customer-file", "file_id"),
            "customer.lifecycle.transition": ("customer-file", "file_id"),
            "customer.lifecycle.event": ("customer-file", "file_id"),
            "research.promotion.evaluate": ("research", "research_id"),
            "publishing.stage": ("publication", "release_id"),
            "publishing.project_internal": ("publication", "release_id"),
            "frontage.release_internal": ("frontage-release", "release_id"),
            "domain.public_activation.request": ("domain-intent", "domain"),
        }
        kind, key = mapping[action]
        result.insert(0, f"{kind}://{payload[key]}")
        return result
