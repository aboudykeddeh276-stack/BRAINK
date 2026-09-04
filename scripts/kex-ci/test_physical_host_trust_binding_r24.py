from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from enterprise.physical_host_evidence_r24 import HostAttestation, PhysicalHostEvidenceVerifier
from enterprise.physical_host_trust_binding_r24 import (
    AttestationBinding,
    ExternalTrustBinder,
    TrustAnchor,
    binding_payload,
)

PACKAGE = "7f48db1cfc94c3eaf11140d472a3e6e160ef4fa55ae5c9c275c1995ed8d980e2"


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def attestation(host: str, attestor: str) -> HostAttestation:
    return HostAttestation(
        host_id=host,
        machine_fingerprint=digest(f"machine:{host}"),
        package_sha256=PACKAGE,
        execution_receipt_root=digest(f"exec:{host}"),
        peer_state_root=digest(f"peer:{host}"),
        fault_recovery_root=digest(f"fault:{host}"),
        rollback_root=digest(f"rollback:{host}"),
        attestation_class="INDEPENDENT_ATTESTOR",
        attestor_id=attestor,
        attestation_root=digest(f"attestation:{host}:{attestor}"),
    )


def signed_binding(
    host: HostAttestation,
    *,
    anchor_id: str,
    key_hex: str,
    structural_root: str,
) -> AttestationBinding:
    signature = hmac.new(
        bytes.fromhex(key_hex),
        binding_payload(host.normalized(), structural_root),
        hashlib.sha256,
    ).hexdigest()
    return AttestationBinding(host.host_id, anchor_id, signature)


def main() -> None:
    hosts = [
        attestation("host-a", "declared-attestor-a"),
        attestation("host-b", "declared-attestor-b"),
        attestation("host-c", "declared-attestor-c"),
    ]
    structural = PhysicalHostEvidenceVerifier().verify(
        hosts,
        expected_package_sha256=PACKAGE,
    )
    assert structural["structural_evidence_status"] == "STRUCTURALLY_QUALIFIED"
    assert structural["physical_host_status"] == "UNVERIFIED"

    keys = {
        "anchor-a": digest("external-anchor-key-a"),
        "anchor-b": digest("external-anchor-key-b"),
        "anchor-c": digest("external-anchor-key-c"),
    }
    anchors = [
        TrustAnchor("anchor-a", "INDEPENDENT_ATTESTATION_SERVICE", keys["anchor-a"]),
        TrustAnchor("anchor-b", "INDEPENDENT_ATTESTATION_SERVICE", keys["anchor-b"]),
        TrustAnchor("anchor-c", "HARDWARE_ROOT_PROXY", keys["anchor-c"]),
    ]
    bindings = [
        signed_binding(hosts[0], anchor_id="anchor-a", key_hex=keys["anchor-a"], structural_root=structural["verification_root"]),
        signed_binding(hosts[1], anchor_id="anchor-b", key_hex=keys["anchor-b"], structural_root=structural["verification_root"]),
        signed_binding(hosts[2], anchor_id="anchor-c", key_hex=keys["anchor-c"], structural_root=structural["verification_root"]),
    ]

    binder = ExternalTrustBinder()
    bound = binder.bind(structural, hosts, anchors, bindings)
    assert bound["trust_binding_status"] == "TRUST_BOUND"
    assert bound["physical_host_status"] == "UNVERIFIED"
    assert bound["verification_boundary"] == "DISTINCT_PHYSICAL_EXECUTION_AND_INDEPENDENT_VERIFICATION_REQUIRED"
    assert bound["valid_binding_count"] == 3
    assert bound["criteria"]["structural_result_reproduced"] is True
    assert bound["criteria"]["all_binding_signatures_valid"] is True
    assert bound["criteria"]["external_anchor_diversity"] is True
    assert bound["synthetic_fixture_is_physical_execution_evidence"] is False

    tampered = list(bindings)
    tampered[1] = AttestationBinding("host-b", "anchor-b", digest("forged-signature"))
    tampered_result = binder.bind(structural, hosts, anchors, tampered)
    assert tampered_result["trust_binding_status"] == "UNBOUND"
    assert tampered_result["physical_host_status"] == "UNVERIFIED"
    assert tampered_result["failures"]["invalid_signatures"] == ["host-b"]

    one_anchor = [TrustAnchor("anchor-a", "EXTERNAL_SHARED_KEY", keys["anchor-a"])]
    one_anchor_bindings = [
        signed_binding(host, anchor_id="anchor-a", key_hex=keys["anchor-a"], structural_root=structural["verification_root"])
        for host in hosts
    ]
    one_anchor_result = binder.bind(structural, hosts, one_anchor, one_anchor_bindings)
    assert one_anchor_result["trust_binding_status"] == "UNBOUND"
    assert one_anchor_result["criteria"]["external_anchor_diversity"] is False

    print(
        json.dumps(
            {
                "marker": "R24_PHYSICAL_HOST_TRUST_BINDING_PASS",
                "contract_fixture_trust_status": bound["trust_binding_status"],
                "contract_fixture_physical_status": bound["physical_host_status"],
                "tampered_signature_status": tampered_result["trust_binding_status"],
                "single_anchor_status": one_anchor_result["trust_binding_status"],
                "synthetic_fixture_is_execution_evidence": False,
                "trust_binding_root": bound["trust_binding_root"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    print("R24_PHYSICAL_HOST_TRUST_BINDING_PASS")


if __name__ == "__main__":
    main()
