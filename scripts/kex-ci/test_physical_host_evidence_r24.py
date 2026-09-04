from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from enterprise.physical_host_evidence_r24 import HostAttestation, PhysicalHostEvidenceVerifier

PACKAGE = "7f48db1cfc94c3eaf11140d472a3e6e160ef4fa55ae5c9c275c1995ed8d980e2"


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def attestation(
    host: str,
    *,
    cls: str,
    attestor: str,
    package: str = PACKAGE,
    fingerprint: str | None = None,
) -> HostAttestation:
    return HostAttestation(
        host_id=host,
        machine_fingerprint=fingerprint or digest(f"machine:{host}"),
        package_sha256=package,
        execution_receipt_root=digest(f"exec:{host}"),
        peer_state_root=digest(f"peer:{host}"),
        fault_recovery_root=digest(f"fault:{host}"),
        rollback_root=digest(f"rollback:{host}"),
        attestation_class=cls,
        attestor_id=attestor,
        attestation_root=digest(f"attestation:{host}:{attestor}:{cls}"),
    )


def main() -> None:
    verifier = PhysicalHostEvidenceVerifier()

    # Three local/self-declared identities must never be upgraded into physical proof.
    self_declared = [
        attestation("alpha", cls="SELF_DECLARED", attestor="alpha"),
        attestation("beta", cls="SELF_DECLARED", attestor="beta"),
        attestation("gamma", cls="SELF_DECLARED", attestor="gamma"),
    ]
    local_result = verifier.verify(self_declared, expected_package_sha256=PACKAGE)
    assert local_result["physical_host_status"] == "UNVERIFIED"
    assert local_result["criteria"]["minimum_host_count"] is True
    assert local_result["criteria"]["all_hosts_independently_or_hardware_attested"] is False

    duplicate_fingerprint = [
        attestation("alpha", cls="INDEPENDENT_ATTESTOR", attestor="verifier-a"),
        attestation(
            "beta",
            cls="INDEPENDENT_ATTESTOR",
            attestor="verifier-b",
            fingerprint=digest("machine:alpha"),
        ),
        attestation("gamma", cls="INDEPENDENT_ATTESTOR", attestor="verifier-c"),
    ]
    duplicate_result = verifier.verify(duplicate_fingerprint, expected_package_sha256=PACKAGE)
    assert duplicate_result["physical_host_status"] == "UNVERIFIED"
    assert duplicate_result["criteria"]["unique_machine_fingerprints"] is False

    wrong_package = [
        attestation("alpha", cls="INDEPENDENT_ATTESTOR", attestor="verifier-a"),
        attestation(
            "beta",
            cls="INDEPENDENT_ATTESTOR",
            attestor="verifier-b",
            package=digest("wrong-package"),
        ),
        attestation("gamma", cls="INDEPENDENT_ATTESTOR", attestor="verifier-c"),
    ]
    package_result = verifier.verify(wrong_package, expected_package_sha256=PACKAGE)
    assert package_result["physical_host_status"] == "UNVERIFIED"
    assert package_result["criteria"]["expected_package_on_all_hosts"] is False
    assert package_result["failures"]["package_mismatches"] == ["beta"]

    # This is a verifier-contract fixture, not a claim that these hosts were executed.
    verified_fixture = [
        attestation("host-a", cls="INDEPENDENT_ATTESTOR", attestor="verifier-a"),
        attestation("host-b", cls="INDEPENDENT_ATTESTOR", attestor="verifier-b"),
        attestation("host-c", cls="HARDWARE_ROOTED_ATTESTATION", attestor="tpm-ek:host-c"),
    ]
    verified_result = verifier.verify(verified_fixture, expected_package_sha256=PACKAGE)
    assert verified_result["physical_host_status"] == "VERIFIED"
    assert all(verified_result["criteria"].values())
    assert len(verified_result["verification_root"]) == 64

    print(
        json.dumps(
            {
                "marker": "R24_PHYSICAL_HOST_EVIDENCE_VERIFIER_PASS",
                "self_declared_status": local_result["physical_host_status"],
                "duplicate_fingerprint_status": duplicate_result["physical_host_status"],
                "wrong_package_status": package_result["physical_host_status"],
                "contract_fixture_status": verified_result["physical_host_status"],
                "contract_fixture_is_execution_evidence": False,
                "verification_root": verified_result["verification_root"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    print("R24_PHYSICAL_HOST_EVIDENCE_VERIFIER_PASS")


if __name__ == "__main__":
    main()
