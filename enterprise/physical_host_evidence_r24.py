from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping
import hashlib
import json
import re

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VERIFIED_ATTESTATION_CLASSES = {"INDEPENDENT_ATTESTOR", "HARDWARE_ROOTED_ATTESTATION"}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def root(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _require_sha256(value: str, field: str) -> str:
    digest = str(value).lower()
    if not _SHA256_RE.fullmatch(digest):
        raise ValueError(f"INVALID_{field.upper()}_SHA256")
    return digest


@dataclass(frozen=True)
class HostAttestation:
    host_id: str
    machine_fingerprint: str
    package_sha256: str
    execution_receipt_root: str
    peer_state_root: str
    fault_recovery_root: str
    rollback_root: str
    attestation_class: str
    attestor_id: str
    attestation_root: str

    def normalized(self) -> dict[str, str]:
        if not self.host_id.strip():
            raise ValueError("HOST_ID_REQUIRED")
        if not self.attestor_id.strip():
            raise ValueError("ATTESTOR_ID_REQUIRED")
        if self.attestation_class not in {
            "SELF_DECLARED",
            "INDEPENDENT_ATTESTOR",
            "HARDWARE_ROOTED_ATTESTATION",
        }:
            raise ValueError("INVALID_ATTESTATION_CLASS")
        return {
            "host_id": self.host_id.strip(),
            "machine_fingerprint": _require_sha256(self.machine_fingerprint, "machine_fingerprint"),
            "package_sha256": _require_sha256(self.package_sha256, "package"),
            "execution_receipt_root": _require_sha256(self.execution_receipt_root, "execution_receipt_root"),
            "peer_state_root": _require_sha256(self.peer_state_root, "peer_state_root"),
            "fault_recovery_root": _require_sha256(self.fault_recovery_root, "fault_recovery_root"),
            "rollback_root": _require_sha256(self.rollback_root, "rollback_root"),
            "attestation_class": self.attestation_class,
            "attestor_id": self.attestor_id.strip(),
            "attestation_root": _require_sha256(self.attestation_root, "attestation_root"),
        }


class PhysicalHostEvidenceVerifier:
    """Fail-closed verifier for R24 distinct physical-host evidence.

    Physical distinctness is not inferred from process IDs, sockets, container IDs,
    hostnames, or self-declared machine IDs. A host contributes to physical-host
    proof only when its attestation is independently or hardware-rooted and the
    package, execution, quorum, fault-recovery and rollback evidence roots are
    structurally valid.
    """

    def verify(
        self,
        attestations: Iterable[HostAttestation | Mapping[str, Any]],
        *,
        expected_package_sha256: str,
        minimum_hosts: int = 3,
    ) -> dict[str, Any]:
        expected_package = _require_sha256(expected_package_sha256, "expected_package")
        if minimum_hosts < 2:
            raise ValueError("MINIMUM_HOSTS_MUST_BE_AT_LEAST_TWO")

        normalized: list[dict[str, str]] = []
        for value in attestations:
            attestation = value if isinstance(value, HostAttestation) else HostAttestation(**dict(value))
            normalized.append(attestation.normalized())

        host_ids = [item["host_id"] for item in normalized]
        fingerprints = [item["machine_fingerprint"] for item in normalized]
        attestation_roots = [item["attestation_root"] for item in normalized]

        duplicate_host_ids = sorted({v for v in host_ids if host_ids.count(v) > 1})
        duplicate_fingerprints = sorted({v for v in fingerprints if fingerprints.count(v) > 1})
        duplicate_attestation_roots = sorted({v for v in attestation_roots if attestation_roots.count(v) > 1})
        package_mismatches = sorted(
            item["host_id"] for item in normalized if item["package_sha256"] != expected_package
        )
        unverified_hosts = sorted(
            item["host_id"]
            for item in normalized
            if item["attestation_class"] not in _VERIFIED_ATTESTATION_CLASSES
        )

        verified_host_count = sum(
            1 for item in normalized if item["attestation_class"] in _VERIFIED_ATTESTATION_CLASSES
        )
        unique_attestors = sorted({
            item["attestor_id"]
            for item in normalized
            if item["attestation_class"] == "INDEPENDENT_ATTESTOR"
        })
        hardware_rooted_count = sum(
            1 for item in normalized if item["attestation_class"] == "HARDWARE_ROOTED_ATTESTATION"
        )

        criteria = {
            "minimum_host_count": len(normalized) >= minimum_hosts,
            "unique_host_ids": not duplicate_host_ids,
            "unique_machine_fingerprints": not duplicate_fingerprints,
            "unique_attestation_roots": not duplicate_attestation_roots,
            "expected_package_on_all_hosts": not package_mismatches,
            "all_hosts_independently_or_hardware_attested": not unverified_hosts,
            "verified_host_count": verified_host_count >= minimum_hosts,
            "attestation_independence_present": bool(unique_attestors) or hardware_rooted_count >= minimum_hosts,
        }

        physical_status = "VERIFIED" if all(criteria.values()) else "UNVERIFIED"
        body = {
            "schema": "braink.r24.physical-host-evidence-verification/v1",
            "physical_host_status": physical_status,
            "minimum_hosts": minimum_hosts,
            "observed_host_count": len(normalized),
            "verified_host_count": verified_host_count,
            "expected_package_sha256": expected_package,
            "criteria": criteria,
            "failures": {
                "duplicate_host_ids": duplicate_host_ids,
                "duplicate_machine_fingerprints": duplicate_fingerprints,
                "duplicate_attestation_roots": duplicate_attestation_roots,
                "package_mismatches": package_mismatches,
                "unverified_hosts": unverified_hosts,
            },
            "attestation_classes": sorted({item["attestation_class"] for item in normalized}),
            "attestors": sorted({item["attestor_id"] for item in normalized}),
            "evidence_roots": sorted(attestation_roots),
        }
        body["verification_root"] = root(body)
        return body
