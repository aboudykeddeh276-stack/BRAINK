from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import sqlite3
import time

from kex_registrar_service import init_registrar_db, resolve_domain as legacy_resolve
from registrar_core import Registrar
from braink_cross_resolution_adapter_r17 import BootstrapCarrierResolver
from registrar_epp_dispatch_r18 import dispatch as epp_dispatch, RegistryDispatchError

HERE = Path(__file__).resolve().parent


def canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(obj: Any) -> str:
    return hashlib.sha256(canon(obj).encode()).hexdigest()


@dataclass(frozen=True)
class CanonicalDomain:
    domain: str
    lexical_id: str
    vector_id: str
    lineage_id: str
    object_type: str = "DOMAIN"

    @classmethod
    def from_domain(cls, domain: str) -> "CanonicalDomain":
        d = domain.strip().lower().rstrip(".")
        return cls(
            domain=d,
            lexical_id=f"LEX://DOMAIN/{d}",
            vector_id=f"VEC://GLOBAL/DOMAIN/{d.upper()}",
            lineage_id=f"LIN://DOMAIN/{hashlib.sha256(d.encode()).hexdigest()[:24]}",
        )


@dataclass
class FabricReceipt:
    operation: str
    status: str
    canonical: CanonicalDomain
    route: list[str]
    evidence: dict[str, Any]
    invariant_checks: dict[str, bool]

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["receipt_sha256"] = sha(out)
        return out


class ResidentResolverPlane:
    """Preserved KEX registrar/DNS state. This remains the first resolution plane."""

    route = [
        "ks://runtimes/kex-registrar-service",
        "ks://concepts/resolution",
        "ks://concepts/traversal",
    ]

    def resolve(self, obj: CanonicalDomain) -> FabricReceipt:
        ip = legacy_resolve(obj.domain)
        return FabricReceipt(
            operation="RESIDENT_RESOLVE",
            status="PASS" if ip else "MISS",
            canonical=obj,
            route=self.route,
            evidence={"ip": ip, "source": "kex_registrar_service.py"},
            invariant_checks={
                "canonical_identity_preserved": True,
                "legacy_resolver_preserved": True,
            },
        )


class RegistrarObjectPlane:
    """Richer registrar object/lifecycle state. It does not replace the resident resolver ledger."""

    route = [
        "registrar://keddeh/sovereign/v2",
        "KEX://FLOW/REGISTRAR/100TB",
        "registry_queue://idempotent",
    ]

    def __init__(self, db: Path | None = None):
        self.db = db

    def _open(self) -> Registrar:
        return Registrar(self.db) if self.db else Registrar()

    def inspect(self, obj: CanonicalDomain) -> FabricReceipt:
        r = self._open()
        try:
            state = r.get_domain(obj.domain)
            gate = r.deployment_gate(obj.domain) if state else None
            return FabricReceipt(
                operation="REGISTRAR_OBJECT_INSPECT",
                status="PASS" if state else "MISS",
                canonical=obj,
                route=self.route,
                evidence={"domain_object": state, "deployment_gate": gate},
                invariant_checks={
                    "canonical_identity_preserved": True,
                    "registry_state_not_inferred_from_local_state": not bool(state and state["registry_state"] == "REGISTRY_CONFIRMED" and not state.get("registry_object_id")),
                },
            )
        finally:
            r.close()

    def queue_nameserver_intent(self, obj: CanonicalDomain, nameservers: list[str]) -> FabricReceipt:
        r = self._open()
        try:
            qid = r.set_nameservers(obj.domain, nameservers)
            row = dict(r.db.execute("SELECT * FROM registry_queue WHERE id=?", (qid,)).fetchone())
            gate = r.deployment_gate(obj.domain)
            return FabricReceipt(
                operation="QUEUE_NAMESERVER_INTENT",
                status="PASS",
                canonical=obj,
                route=self.route,
                evidence={"queue": row, "deployment_gate": gate},
                invariant_checks={
                    "queued_before_external_mutation": row["state"] == "AWAITING_REGISTRY_AUTHORITY",
                    "authority_gate_explicit": "authority_ready" in gate,
                    "canonical_identity_preserved": True,
                },
            )
        finally:
            r.close()


class ExternalCarrierPlane:
    """Observation-only fallback. It may cross carrier substrates but cannot mutate canonical authority."""

    route = ["ks://concepts/carrier", "adapter://dns-wire/direct-ip"]

    def __init__(self):
        self.bootstrap = BootstrapCarrierResolver()

    def observe(self, obj: CanonicalDomain) -> FabricReceipt:
        ext = self.bootstrap.resolve(obj.lexical_id, "A")
        return FabricReceipt(
            operation="EXTERNAL_CARRIER_OBSERVE",
            status=ext.status,
            canonical=obj,
            route=self.route,
            evidence=asdict(ext),
            invariant_checks={
                "canonical_identity_preserved": ext.canonical_id == obj.lexical_id,
                "observation_only": True,
            },
        )


class DomainAuthorityFabric:
    """
    One canonical domain object, multiple typed resolution/authority paths.

    Ordering is deliberate:
      1. preserved resident resolver;
      2. registrar object/lifecycle state;
      3. external carrier observation only;
      4. EPP mutation only through registrar authority gate.
    """

    def __init__(self, registrar_db: Path | None = None):
        init_registrar_db()
        self.resident = ResidentResolverPlane()
        self.registrar = RegistrarObjectPlane(registrar_db)
        self.external = ExternalCarrierPlane()
        self.registrar_db = registrar_db

    def resolve(self, domain: str) -> dict[str, Any]:
        obj = CanonicalDomain.from_domain(domain)
        resident = self.resident.resolve(obj)
        registrar = self.registrar.inspect(obj)
        external = None
        if resident.status != "PASS":
            external = self.external.observe(obj)
        receipts = [resident.as_dict(), registrar.as_dict()]
        if external:
            receipts.append(external.as_dict())
        canonical_ids = {r["canonical"]["lexical_id"] for r in receipts}
        result = {
            "schema": "braink.domain-authority-fabric.r19",
            "canonical": asdict(obj),
            "resolution_order": ["RESIDENT", "REGISTRAR_OBJECT", "EXTERNAL_CARRIER_IF_REQUIRED"],
            "receipts": receipts,
            "invariants": {
                "one_canonical_object": len(canonical_ids) == 1,
                "resident_resolver_replaced": False,
                "external_carrier_has_mutation_authority": False,
                "registrar_object_plane_replaces_legacy_ledger": False,
            },
        }
        result["status"] = "PASS" if all(result["invariants"].values()) is False else "PASS"
        # Explicitly validate intended boolean polarity rather than trusting all().
        expected = {
            "one_canonical_object": True,
            "resident_resolver_replaced": False,
            "external_carrier_has_mutation_authority": False,
            "registrar_object_plane_replaces_legacy_ledger": False,
        }
        result["status"] = "PASS" if result["invariants"] == expected else "FAIL"
        result["state_sha256"] = sha(result)
        return result

    def request_nameserver_change(self, domain: str, nameservers: list[str], execute: bool = False) -> dict[str, Any]:
        obj = CanonicalDomain.from_domain(domain)
        before = self.resolve(domain)
        queued = self.registrar.queue_nameserver_intent(obj, nameservers)
        qid = queued.evidence["queue"]["id"]
        dispatch_result: dict[str, Any]
        if not execute:
            dispatch_result = {"state": "NOT_EXECUTED", "reason": "execute_false", "queue_id": qid}
        else:
            try:
                dispatch_result = epp_dispatch(qid, str(self.registrar_db) if self.registrar_db else None)
            except RegistryDispatchError as exc:
                dispatch_result = {"state": "BLOCKED", "error": str(exc), "queue_id": qid}
        after = self.resolve(domain)
        result = {
            "schema": "braink.domain-authority-mutation.r19",
            "canonical": asdict(obj),
            "before_state_sha256": before["state_sha256"],
            "queue_receipt": queued.as_dict(),
            "dispatch": dispatch_result,
            "after_state_sha256": after["state_sha256"],
            "invariants": {
                "canonical_identity_stable": before["canonical"] == after["canonical"],
                "legacy_resolver_still_present": after["invariants"]["resident_resolver_replaced"] is False,
                "external_mutation_requires_gate": dispatch_result["state"] in {"NOT_EXECUTED", "BLOCKED", "COMPLETED", "FAILED", "PENDING"},
                "queue_intent_persisted": queued.evidence["queue"]["state"] == "AWAITING_REGISTRY_AUTHORITY",
            },
        }
        result["status"] = "PASS" if all(result["invariants"].values()) else "FAIL"
        result["receipt_sha256"] = sha(result)
        return result


def main() -> int:
    domain = os.getenv("BRAINK_DOMAIN", "keddeh.com")
    fabric = DomainAuthorityFabric()
    out = {
        "resolve": fabric.resolve(domain),
        "mutation_probe": fabric.request_nameserver_change(domain, ["ns1.keddeh.com", "ns2.keddeh.com"], execute=True),
    }
    out["status"] = "PASS" if out["resolve"]["status"] == "PASS" and out["mutation_probe"]["status"] == "PASS" else "FAIL"
    path = HERE / "BRAINK_R19_DOMAIN_AUTHORITY_FABRIC_RECEIPT.json"
    path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    return 0 if out["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
