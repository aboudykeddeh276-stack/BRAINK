#!/usr/bin/env python3
"""BRAINK resident-root projection and carrier-last remote host verification.

Authority chain:
resident object graph -> canonical typed roots -> root digest verification ->
carrier projection.  The carrier endpoint is intentionally excluded from the
canonical snapshot digest and cannot establish BRAINK identity.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping
import hashlib
import json

from modules.kex_core.canonical_state import CanonicalState, digest
from runtime.runtime_route_registry import RuntimeRouteRegistry
from enterprise.domain_replication import DOMAIN_BINDINGS

SCHEMA = "braink.resident-root-projection.r28/v1"
ROOT_TYPES = (
    "DOMAIN_ROOT",
    "DNS_ROOT",
    "REGISTRAR_ROOT",
    "TLS_ROOT",
    "SERVER_ROOT",
    "CLOUD_ROOT",
)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class RootBinding:
    root_type: str
    identity: str
    logical_address: str
    source_binding: str
    adapter_binding: str | None
    adapter_state: str
    authority: str
    payload: Mapping[str, Any]

    def material(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def root_digest(self) -> str:
        return sha256(self.material())


class ResidentRootResolver:
    """Resolve typed roots from resident repository/runtime mechanics.

    This resolver does not discover identity from a public endpoint.  It derives
    identity from resident state and records missing concrete adapters explicitly.
    """

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root)
        self.routes = RuntimeRouteRegistry(self.repo_root)

    def _exists(self, relative: str) -> bool:
        return (self.repo_root / relative).exists()

    def resolve(self, domain: str = "keddeh.com") -> dict[str, RootBinding]:
        app_binding = DOMAIN_BINDINGS.get(domain)
        if not app_binding:
            raise KeyError(f"resident domain binding not found: {domain}")

        public_gateway = self.routes.resolve("public-gateway")
        durable_domain = "enterprise/orchestration/durable_execution_r5.py"
        addressability = "enterprise/addressability_fabric.py"
        self_addressing = "enterprise/self_addressing_runtime.py"
        canonical = "modules/kex_core/canonical_state.py"
        runtime_registry = "runtime/runtime_registry.py"

        roots = {
            "DOMAIN_ROOT": RootBinding(
                "DOMAIN_ROOT", f"domain://{domain}", f"KEX://DOMAIN/{domain.upper()}",
                "enterprise/domain_replication.py:DOMAIN_BINDINGS",
                durable_domain if self._exists(durable_domain) else None,
                "BOUND" if self._exists(durable_domain) else "UNRESOLVED",
                "BRAINK_RESIDENT_DOMAIN_AUTHORITY",
                {"domain": domain, "application_binding": app_binding},
            ),
            "DNS_ROOT": RootBinding(
                "DNS_ROOT", f"dns://{domain}", f"KEX://DNS/{domain.upper()}",
                "enterprise/domain_replication.py:PUBLIC_OBSERVER_CLASSES",
                None, "UNRESOLVED_CONCRETE_ADAPTER",
                "BRAINK_RESIDENT_DNS_STATE_NOT_PUBLIC_DNS_AUTHORITY",
                {"domain": domain, "observer_class": "DNS_OBSERVED"},
            ),
            "REGISTRAR_ROOT": RootBinding(
                "REGISTRAR_ROOT", f"registrar://{domain}", f"KEX://REGISTRAR/{domain.upper()}",
                "deployments/R24_DOMAIN_DURABLE_EXECUTION_RECONCILIATION_R1.json",
                durable_domain if self._exists(durable_domain) else None,
                "BOUND_INTERNAL_DURABLE_AUTHORITY" if self._exists(durable_domain) else "UNRESOLVED",
                "BRAINK_RESIDENT_REGISTRAR_STATE_NOT_REGISTRY_EPP_AUTHORITY",
                {"domain": domain, "external_registry_authority": "UNPROVEN"},
            ),
            "TLS_ROOT": RootBinding(
                "TLS_ROOT", f"tls://{domain}", f"KEX://TLS/{domain.upper()}",
                "enterprise/domain_replication.py:PUBLIC_OBSERVER_CLASSES",
                None, "UNRESOLVED_CONCRETE_ADAPTER",
                "BRAINK_RESIDENT_TLS_STATE_NOT_CA_AUTHORITY",
                {"domain": domain, "observer_class": "TLS_OBSERVED"},
            ),
            "SERVER_ROOT": RootBinding(
                "SERVER_ROOT", "runtime://public-gateway", "KEX://SERVER/PUBLIC-GATEWAY",
                "runtime/runtime_route_registry.py:public-gateway",
                public_gateway["command_route"], "BOUND",
                "BRAINK_RESIDENT_RUNTIME_AUTHORITY",
                {k: public_gateway[k] for k in ("runtime_id", "runtime_class", "argv", "dependencies")},
            ),
            "CLOUD_ROOT": RootBinding(
                "CLOUD_ROOT", "braink://runtime/addressability", "KEX://CLOUD/BRAINK/RESIDENT",
                addressability,
                self_addressing if self._exists(self_addressing) else None,
                "BOUND" if self._exists(addressability) and self._exists(self_addressing) else "UNRESOLVED",
                "BRAINK_RESIDENT_ADDRESSABILITY_AUTHORITY",
                {"addressability_fabric": addressability, "self_addressing_runtime": self_addressing,
                 "canonical_boundary": canonical, "runtime_registry": runtime_registry},
            ),
        }
        return roots

    def canonical_snapshot(self, domain: str = "keddeh.com") -> dict[str, Any]:
        roots = self.resolve(domain)
        material = {
            "schema": SCHEMA,
            "domain": domain,
            "roots": {
                name: {**binding.material(), "root_digest": binding.root_digest}
                for name, binding in sorted(roots.items())
            },
        }
        state = CanonicalState(
            identity=f"braink://resident-root-snapshot/{domain}",
            payload=material,
            lineage=("repo://BRAINK/main", "resident://object-graph"),
            authority="BRAINK_RESIDENT_OBJECT_GRAPH",
            metadata={"carrier_role": "PROJECTION_ONLY"},
        )
        return {"canonical_state": state.envelope(), "snapshot_digest": state.state_digest}


def carrier_projection(snapshot: Mapping[str, Any], *, endpoint: str, carrier: str, host_id: str) -> dict[str, Any]:
    """Attach a mutable network carrier without changing canonical identity."""
    return {
        "schema": "braink.carrier-projection.r28/v1",
        "snapshot_digest": snapshot["snapshot_digest"],
        "resident_identity": snapshot["canonical_state"]["identity"],
        "host_id": host_id,
        "carrier": carrier,
        "endpoint": endpoint,
        "projection_digest": sha256({
            "snapshot_digest": snapshot["snapshot_digest"],
            "host_id": host_id,
            "carrier": carrier,
            "endpoint": endpoint,
        }),
    }


def verify_remote_join(local_snapshot: Mapping[str, Any], remote_projection: Mapping[str, Any], remote_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Trust resident root digests first; accept carrier only after identity proof."""
    local_roots = local_snapshot["canonical_state"]["payload"]["roots"]
    remote_roots = remote_snapshot["canonical_state"]["payload"]["roots"]
    root_checks = {
        name: local_roots[name]["root_digest"] == remote_roots[name]["root_digest"]
        for name in ROOT_TYPES
    }
    snapshot_match = local_snapshot["snapshot_digest"] == remote_snapshot["snapshot_digest"]
    projection_links_snapshot = remote_projection.get("snapshot_digest") == remote_snapshot["snapshot_digest"]
    accepted = snapshot_match and projection_links_snapshot and all(root_checks.values())
    return {
        "status": "ACCEPTED" if accepted else "REJECTED",
        "snapshot_match": snapshot_match,
        "projection_links_snapshot": projection_links_snapshot,
        "root_digest_checks": root_checks,
        "carrier_trusted": accepted,
        "carrier_endpoint": remote_projection.get("endpoint") if accepted else None,
    }
