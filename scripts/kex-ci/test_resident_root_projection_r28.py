#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from runtime.resident_root_projection_r28 import (  # noqa: E402
    ROOT_TYPES,
    ResidentRootResolver,
    carrier_projection,
    verify_remote_join,
)


def main() -> int:
    resolver = ResidentRootResolver(ROOT)
    local = resolver.canonical_snapshot("keddeh.com")
    remote = resolver.canonical_snapshot("keddeh.com")

    p1 = carrier_projection(
        remote,
        endpoint="https://carrier-a.invalid/braink",
        carrier="HTTPS_TUNNEL",
        host_id="remote-host-r28",
    )
    p2 = carrier_projection(
        remote,
        endpoint="https://carrier-b.invalid/braink",
        carrier="HTTPS_TUNNEL",
        host_id="remote-host-r28",
    )

    roots = local["canonical_state"]["payload"]["roots"]
    assert set(roots) == set(ROOT_TYPES)
    assert roots["DOMAIN_ROOT"]["adapter_state"] == "BOUND"
    assert roots["SERVER_ROOT"]["adapter_state"] == "BOUND"
    assert roots["CLOUD_ROOT"]["adapter_state"] == "BOUND"
    assert roots["TLS_ROOT"]["adapter_state"] == "UNRESOLVED_CONCRETE_ADAPTER"
    assert roots["DNS_ROOT"]["adapter_state"] == "UNRESOLVED_CONCRETE_ADAPTER"

    # Carrier mutation must not mutate resident identity/snapshot authority.
    assert p1["snapshot_digest"] == p2["snapshot_digest"] == local["snapshot_digest"]
    assert p1["projection_digest"] != p2["projection_digest"]

    accepted = verify_remote_join(local, p1, remote)
    assert accepted["status"] == "ACCEPTED"
    assert accepted["carrier_trusted"] is True
    assert all(accepted["remote_root_integrity"].values())

    # A remote cannot alter resident material while reusing the old declared digest.
    tampered_material = deepcopy(remote)
    tampered_material["canonical_state"]["payload"]["roots"]["DOMAIN_ROOT"]["payload"]["application_binding"] = "app://attacker"
    rejected_material = verify_remote_join(local, p1, tampered_material)
    assert rejected_material["status"] == "REJECTED"
    assert rejected_material["carrier_trusted"] is False
    assert rejected_material["remote_root_integrity"]["DOMAIN_ROOT"] is False
    assert rejected_material["remote_snapshot_valid"] is False

    # A forged root digest also fails independently.
    tampered_digest = deepcopy(remote)
    tampered_digest["canonical_state"]["payload"]["roots"]["DOMAIN_ROOT"]["root_digest"] = "0" * 64
    rejected_digest = verify_remote_join(local, p1, tampered_digest)
    assert rejected_digest["status"] == "REJECTED"
    assert rejected_digest["root_digest_checks"]["DOMAIN_ROOT"] is False

    bad_projection = deepcopy(p1)
    bad_projection["snapshot_digest"] = "f" * 64
    rejected_projection = verify_remote_join(local, bad_projection, remote)
    assert rejected_projection["status"] == "REJECTED"
    assert rejected_projection["projection_links_snapshot"] is False

    wrong_identity = deepcopy(p1)
    wrong_identity["resident_identity"] = "braink://forged"
    rejected_identity = verify_remote_join(local, wrong_identity, remote)
    assert rejected_identity["status"] == "REJECTED"
    assert rejected_identity["projection_links_identity"] is False

    receipt = {
        "schema": "braink.resident-root-remote-carrier.r28.receipt/v1",
        "status": "PASS",
        "snapshot_digest": local["snapshot_digest"],
        "root_digests": {name: roots[name]["root_digest"] for name in ROOT_TYPES},
        "adapter_states": {name: roots[name]["adapter_state"] for name in ROOT_TYPES},
        "checks": {
            "six_resident_roots_resolved": True,
            "carrier_change_preserves_snapshot_digest": True,
            "carrier_change_changes_projection_only": True,
            "valid_join_accepted_after_recomputed_root_verification": True,
            "tampered_root_material_rejected": True,
            "forged_root_digest_rejected": True,
            "projection_snapshot_mismatch_rejected": True,
            "projection_identity_mismatch_rejected": True,
            "tls_concrete_adapter_unresolved_not_invented": True,
            "dns_concrete_adapter_unresolved_not_invented": True,
        },
        "authority_chain": [
            "RESIDENT_OBJECT_GRAPH",
            "CANONICAL_TYPED_ROOTS",
            "RECOMPUTED_ROOT_DIGEST_VERIFICATION",
            "RECOMPUTED_CANONICAL_SNAPSHOT_VERIFICATION",
            "REMOTE_HOST_PROJECTION",
            "CARRIER_ENDPOINT_LAST",
        ],
    }
    out = ROOT / "reports" / "BRAINK_R28_RESIDENT_ROOT_REMOTE_CARRIER_RECEIPT.json"
    out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
