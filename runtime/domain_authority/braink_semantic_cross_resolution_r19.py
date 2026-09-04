from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
import json
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import kex_registrar_service as registrar
import braink_cross_resolution_adapter_r17 as r17

DOMAIN = "keddeh.com"
CANONICAL_ID = f"LEX://DOMAIN/{DOMAIN}"


class SemanticResidentResolver:
    """BRAINK canonical identity first; carrier/IP compatibility second."""

    route = "ks://concepts/resolution->ks://concepts/semantic-authority->ks://concepts/traversal"

    def resolve(self, canonical_id: str) -> r17.ResolutionReceipt:
        domain = canonical_id.removeprefix("LEX://DOMAIN/")
        semantic = registrar.resolve_semantic_domain(domain)
        if semantic:
            return r17.ResolutionReceipt(
                operation="SEMANTIC_RESIDENT_RESOLVE",
                canonical_id=canonical_id,
                route=self.route,
                status="PASS",
                evidence_class="KEX_SEMANTIC_REGISTRAR_LEDGER_READBACK",
                lineage=[
                    semantic["lineage_id"],
                    "ks://concepts/semantic-authority",
                    "ks://concepts/resolution",
                    "ks://concepts/traversal",
                ],
                detail={
                    "domain": domain,
                    "binding": semantic,
                    "carrier_ip_required": False,
                },
            )

        ip = registrar.resolve_domain(domain)
        return r17.ResolutionReceipt(
            operation="LEGACY_CARRIER_RESOLVE",
            canonical_id=canonical_id,
            route="ks://concepts/resolution->adapter://legacy-ip",
            status="PASS" if ip else "MISS",
            evidence_class="KEX_REGISTRAR_LEDGER_READBACK",
            lineage=["ks://runtimes/kex-registrar-service", "adapter://legacy-ip"],
            detail={"domain": domain, "ip": ip, "carrier_ip_required": True},
        )


class SemanticCrossResolutionRouter(r17.CrossResolutionRouter):
    def __init__(self):
        super().__init__()
        self.resident = SemanticResidentResolver()


def binding() -> dict[str, Any]:
    return {
        "canonical_id": CANONICAL_ID,
        "braink_id": "BRAINK::KEX-MACHINE-001::R19",
        "lineage_id": "BRAINK::LINEAGE::KEX-MACHINE-001::GENESIS",
        "lexical_id": CANONICAL_ID,
        "vector_id": "VEC://GLOBAL/DOMAIN/KEDDEH",
        "service_route": "KEX://MACHINE/KEX-MACHINE-001/SERVER/",
        "storage_route": "KEX://MACHINE/KEX-MACHINE-001/STORAGE/",
        "adapter_id": "BRAINK_SEMANTIC_CROSS_RESOLUTION_R19",
        "state": "ACTIVE",
    }


def main() -> int:
    registrar.init_registrar_db()
    proof = registrar.register_semantic_domain(DOMAIN, binding())
    routed = SemanticCrossResolutionRouter().resolve_domain(DOMAIN)

    resident = routed["resident_primary"]
    checks = {
        "resident_primary_pass": resident["status"] == "PASS",
        "resident_semantic_evidence": resident["evidence_class"] == "KEX_SEMANTIC_REGISTRAR_LEDGER_READBACK",
        "canonical_identity_preserved": routed["canonical_identity_preserved"] is True,
        "resident_not_replaced": routed["resident_resolver_replaced"] is False,
        "no_carrier_ip_required": resident["detail"].get("carrier_ip_required") is False,
        "proof_readback_match": resident["detail"]["binding"]["proof_sha256"] == proof,
        "external_carrier_subordinate": routed["carrier_escape"]["operation"] == "BOOTSTRAP_CARRIER_RESOLVE",
    }

    receipt = {
        "schema": "braink.semantic-cross-resolution.r19",
        "domain": DOMAIN,
        "contract": "SEMANTIC_RESIDENT_PRIMARY_WITH_SUBORDINATE_CARRIER_ESCAPE",
        "domain_resolution": routed,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    out = HERE / "BRAINK_R19_SEMANTIC_CROSS_RESOLUTION_RECEIPT.json"
    out.write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
