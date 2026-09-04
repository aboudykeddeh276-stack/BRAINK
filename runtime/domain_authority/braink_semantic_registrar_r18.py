from __future__ import annotations

from pathlib import Path
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import kex_registrar_service as registrar

DOMAIN = "keddeh.com"
CANONICAL_ID = f"LEX://DOMAIN/{DOMAIN}"


def canonical_binding():
    return {
        "canonical_id": CANONICAL_ID,
        "braink_id": "BRAINK::KEX-MACHINE-001::R18",
        "lineage_id": "BRAINK::LINEAGE::KEX-MACHINE-001::GENESIS",
        "lexical_id": CANONICAL_ID,
        "vector_id": "VEC://GLOBAL/DOMAIN/KEDDEH",
        "service_route": "KEX://MACHINE/KEX-MACHINE-001/SERVER/",
        "storage_route": "KEX://MACHINE/KEX-MACHINE-001/STORAGE/",
        "adapter_id": "BRAINK_SEMANTIC_REGISTRAR_R18",
        "state": "ACTIVE",
    }


def main():
    registrar.init_registrar_db()

    legacy_before = registrar.resolve_domain("os.keddeh")
    carrier_before = registrar.resolve_domain(DOMAIN)

    binding = canonical_binding()
    proof = registrar.register_semantic_domain(DOMAIN, binding)
    readback = registrar.resolve_semantic_domain(DOMAIN)

    legacy_after = registrar.resolve_domain("os.keddeh")
    carrier_after = registrar.resolve_domain(DOMAIN)

    checks = {
        "legacy_carrier_preserved": legacy_before == "127.0.0.1" and legacy_after == "127.0.0.1",
        "semantic_binding_present": bool(readback),
        "canonical_id_match": bool(readback) and readback["canonical_id"] == CANONICAL_ID,
        "lexical_id_match": bool(readback) and readback["lexical_id"] == CANONICAL_ID,
        "braink_identity_present": bool(readback) and readback["braink_id"] == binding["braink_id"],
        "lineage_preserved": bool(readback) and readback["lineage_id"] == binding["lineage_id"],
        "vector_route_present": bool(readback) and readback["vector_id"] == binding["vector_id"],
        "service_route_present": bool(readback) and readback["service_route"] == binding["service_route"],
        "proof_readback_match": bool(readback) and readback["proof_sha256"] == proof,
        "semantic_identity_does_not_require_ip": carrier_before is None and carrier_after is None,
    }

    receipt = {
        "schema": "braink.semantic-registrar.r18",
        "domain": DOMAIN,
        "canonical_id": CANONICAL_ID,
        "contract": "SEMANTIC_IDENTITY_AUTHORITY_DISTINCT_FROM_CARRIER_IP",
        "legacy_carrier_route": {
            "domain": "os.keddeh",
            "before": legacy_before,
            "after": legacy_after,
        },
        "domain_carrier_ip": carrier_after,
        "semantic_binding": readback,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    out = HERE / "BRAINK_R18_SEMANTIC_REGISTRAR_RECEIPT.json"
    out.write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
