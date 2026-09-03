from __future__ import annotations

"""Canonical resident-root resolver for BRAINK/KEX.

The source of truth is the resident typed object graph. Carrier addresses are projections
attached only after root resolution. This module deliberately does not probe public DNS,
HTTP, registrars or other external carriers to discover system state.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import argparse
import hashlib
import json

from modules.kex_core.canonical_state import CanonicalBoundary, mapping_adapter


@dataclass(frozen=True)
class ResidentRoot:
    root_id: str
    class_id: str
    authority: str
    implementation: str | None
    adapter: str | None
    consumer: str | None
    state: str
    notes: str = ""


ROOTS = (
    ResidentRoot(
        "BRAINK_ROOT", "class://braink/root", "BRAINK",
        "enterprise/recursive_computer_runtime_r26.py",
        "enterprise/self_addressing_runtime.py",
        "BRAINK orchestration/continuation",
        "BOUND",
    ),
    ResidentRoot(
        "DOMAIN_ROOT", "class://domain/identity", "BRAINK+SERVERS-KEDDEHSYSTEMS",
        "enterprise/domain_authority_binding.py",
        "enterprise/domain_authority_binding.py",
        "DNS_ROOT/REGISTRAR_ROOT/TLS_ROOT",
        "BOUND",
    ),
    ResidentRoot(
        "DNS_ROOT", "class://domain/dns-authority", "SERVERS-KEDDEHSYSTEMS",
        "dependencies/SERVERS-KEDDEHSYSTEMS/runtime/domain_authority/kex_dns.py",
        "KexDNSServer UDP/TCP DNS wire interface",
        "network clients",
        "BOUND",
    ),
    ResidentRoot(
        "REGISTRAR_ROOT", "class://domain/registrar-authority", "SERVERS-KEDDEHSYSTEMS",
        "dependencies/SERVERS-KEDDEHSYSTEMS/runtime/domain_authority/kex_registrar_service.py",
        "SQLite registrar functions",
        "DNS_ROOT/DOMAIN_ROOT",
        "BOUND",
    ),
    ResidentRoot(
        "TLS_ROOT", "class://domain/tls-authority", "BRAINK_LOCAL_TLS_AUTHORITY",
        "enterprise/tls_authority_runtime.py",
        "ResidentTLSAuthority issue/readback/renew/SSLContext",
        "SERVER_ROOT/TLS transport/public-CA adapters",
        "BOUND",
        "Resident local CA authority is bound. Public ACME/edge CA authority remains a downstream adapter boundary.",
    ),
    ResidentRoot(
        "SERVER_ROOT", "class://server/runtime", "BRAINK",
        "runtime/runtime_registry.py",
        "RuntimeRegistry/RuntimeRouteRegistry",
        "service processes",
        "BOUND",
    ),
    ResidentRoot(
        "CLOUD_ROOT", "class://cloud/machine-fabric", "BRAINK",
        "deployment/bootstrap_keddeh_fabric.py",
        "runtime fabric bootstrap",
        "SERVER_ROOT/remote machine nodes",
        "BOUND",
    ),
)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def resolve_roots(repository_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repository_root).resolve()
    boundary = CanonicalBoundary()
    boundary.register(mapping_adapter("resident-root"))

    resolved: dict[str, Any] = {}
    for definition in ROOTS:
        material = asdict(definition)
        implementation_exists = bool(definition.implementation and (root / definition.implementation).exists())
        if definition.state == "BOUND" and not implementation_exists:
            effective_state = "BROKEN_BINDING"
        else:
            effective_state = definition.state
        material["state"] = effective_state
        material["implementation_exists"] = implementation_exists

        canonical = boundary.enter(
            "resident-root",
            material,
            identity=f"LEX://BRAINK/{definition.root_id}",
            authority=definition.authority,
            lineage=("BRAINK_ROOT", definition.root_id),
        )
        resolved[definition.root_id] = canonical.envelope()

    graph = {
        "schema": "braink.kex.resident-root-graph.v1",
        "authority_order": [
            "BRAINK resident state",
            "KEX controller interpretation",
            "typed object state",
            "adapter operation",
            "carrier observation",
        ],
        "roots": resolved,
        "edges": [
            ["BRAINK_ROOT", "DOMAIN_ROOT"],
            ["DOMAIN_ROOT", "DNS_ROOT"],
            ["DOMAIN_ROOT", "REGISTRAR_ROOT"],
            ["DOMAIN_ROOT", "TLS_ROOT"],
            ["TLS_ROOT", "SERVER_ROOT"],
            ["BRAINK_ROOT", "SERVER_ROOT"],
            ["SERVER_ROOT", "CLOUD_ROOT"],
        ],
        "boundary_metrics": boundary.metrics(),
    }
    graph["graph_digest"] = sha256(graph)
    return graph


def require_resident_integrity(graph: dict[str, Any]) -> None:
    required_bound = {"BRAINK_ROOT", "DOMAIN_ROOT", "DNS_ROOT", "REGISTRAR_ROOT", "TLS_ROOT", "SERVER_ROOT", "CLOUD_ROOT"}
    failures = []
    for rid in sorted(required_bound):
        payload = graph["roots"][rid]["payload"]
        if payload["state"] != "BOUND" or not payload["implementation_exists"]:
            failures.append({"root": rid, "state": payload["state"], "implementation": payload["implementation"]})
    if failures:
        raise RuntimeError(f"RESIDENT_ROOT_BINDING_FAILURE:{failures}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", type=Path, default=Path("build/resident-root-graph.json"))
    args = parser.parse_args()
    graph = resolve_roots(args.root)
    require_resident_integrity(graph)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", "utf-8")
    print(json.dumps({"status": "RESIDENT_ROOTS_RESOLVED", "graph_digest": graph["graph_digest"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
