from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping
import hashlib
import hmac
import re

from enterprise.physical_host_evidence_r24 import (
    HostAttestation,
    PhysicalHostEvidenceVerifier,
    canonical,
    root,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ELIGIBLE_ANCHOR_CLASSES = {
    "EXTERNAL_SHARED_KEY",
    "INDEPENDENT_ATTESTATION_SERVICE",
    "HARDWARE_ROOT_PROXY",
}


def _require_sha256(value: str, field: str) -> str:
    digest = str(value).lower()
    if not _SHA256_RE.fullmatch(digest):
        raise ValueError(f"INVALID_{field.upper()}_SHA256")
    return digest


@dataclass(frozen=True)
class TrustAnchor:
    anchor_id: str
    anchor_class: str
    verification_key_hex: str

    def normalized(self) -> dict[str, str]:
        anchor_id = self.anchor_id.strip()
        if not anchor_id:
            raise ValueError("ANCHOR_ID_REQUIRED")
        if self.anchor_class not in _ELIGIBLE_ANCHOR_CLASSES:
            raise ValueError("INVALID_ANCHOR_CLASS")
        try:
            key = bytes.fromhex(self.verification_key_hex)
        except ValueError as exc:
            raise ValueError("INVALID_ANCHOR_KEY_HEX") from exc
        if len(key) < 32:
            raise ValueError("ANCHOR_KEY_MINIMUM_256_BITS")
        return {
            "anchor_id": anchor_id,
            "anchor_class": self.anchor_class,
            "verification_key_hex": key.hex(),
        }


@dataclass(frozen=True)
class AttestationBinding:
    host_id: str
    anchor_id: str
    signature_sha256: str

    def normalized(self) -> dict[str, str]:
        host_id = self.host_id.strip()
        anchor_id = self.anchor_id.strip()
        if not host_id:
            raise ValueError("BINDING_HOST_ID_REQUIRED")
        if not anchor_id:
            raise ValueError("BINDING_ANCHOR_ID_REQUIRED")
        return {
            "host_id": host_id,
            "anchor_id": anchor_id,
            "signature_sha256": _require_sha256(self.signature_sha256, "binding_signature"),
        }


def binding_payload(host: Mapping[str, str], structural_verification_root: str) -> bytes:
    return canonical(
        {
            "schema": "braink.r24.physical-host-trust-binding-payload/v1",
            "structural_verification_root": _require_sha256(
                structural_verification_root, "structural_verification_root"
            ),
            "host_attestation": dict(host),
        }
    )


class ExternalTrustBinder:
    """Bind structurally qualified host evidence to independently supplied anchors.

    This boundary verifies integrity/provenance binding only. A successful result
    is TRUST_BOUND and deliberately leaves physical_host_status UNVERIFIED.
    Distinct authorised physical execution and independent verification remain
    separate R24 propositions.
    """

    def bind(
        self,
        structural_result: Mapping[str, Any],
        attestations: Iterable[HostAttestation | Mapping[str, Any]],
        anchors: Iterable[TrustAnchor | Mapping[str, Any]],
        bindings: Iterable[AttestationBinding | Mapping[str, Any]],
    ) -> dict[str, Any]:
        expected_package = _require_sha256(
            str(structural_result.get("expected_package_sha256", "")), "expected_package"
        )
        minimum_hosts = int(structural_result.get("minimum_hosts", 3))

        normalized_hosts: list[dict[str, str]] = []
        for value in attestations:
            attestation = value if isinstance(value, HostAttestation) else HostAttestation(**dict(value))
            normalized_hosts.append(attestation.normalized())

        reproduced = PhysicalHostEvidenceVerifier().verify(
            normalized_hosts,
            expected_package_sha256=expected_package,
            minimum_hosts=minimum_hosts,
        )
        supplied_root = _require_sha256(
            str(structural_result.get("verification_root", "")), "supplied_structural_verification_root"
        )
        structural_match = reproduced["verification_root"] == supplied_root
        structurally_qualified = (
            structural_match
            and reproduced["structural_evidence_status"] == "STRUCTURALLY_QUALIFIED"
            and structural_result.get("structural_evidence_status") == "STRUCTURALLY_QUALIFIED"
            and structural_result.get("physical_host_status") == "UNVERIFIED"
        )

        normalized_anchors: dict[str, dict[str, str]] = {}
        duplicate_anchor_ids: list[str] = []
        for value in anchors:
            anchor = value if isinstance(value, TrustAnchor) else TrustAnchor(**dict(value))
            item = anchor.normalized()
            if item["anchor_id"] in normalized_anchors:
                duplicate_anchor_ids.append(item["anchor_id"])
            normalized_anchors[item["anchor_id"]] = item

        normalized_bindings: list[dict[str, str]] = []
        for value in bindings:
            binding = value if isinstance(value, AttestationBinding) else AttestationBinding(**dict(value))
            normalized_bindings.append(binding.normalized())

        hosts_by_id = {item["host_id"]: item for item in normalized_hosts}
        bindings_by_host: dict[str, list[dict[str, str]]] = {}
        for item in normalized_bindings:
            bindings_by_host.setdefault(item["host_id"], []).append(item)

        missing_bindings: list[str] = []
        duplicate_host_bindings: list[str] = []
        unknown_hosts: list[str] = []
        unknown_anchors: list[str] = []
        invalid_signatures: list[str] = []
        valid_hosts: list[str] = []
        used_anchor_ids: list[str] = []

        for binding in normalized_bindings:
            if binding["host_id"] not in hosts_by_id:
                unknown_hosts.append(binding["host_id"])
            if binding["anchor_id"] not in normalized_anchors:
                unknown_anchors.append(binding["anchor_id"])

        for host_id, host in hosts_by_id.items():
            host_bindings = bindings_by_host.get(host_id, [])
            if not host_bindings:
                missing_bindings.append(host_id)
                continue
            if len(host_bindings) != 1:
                duplicate_host_bindings.append(host_id)
                continue
            binding = host_bindings[0]
            anchor = normalized_anchors.get(binding["anchor_id"])
            if anchor is None:
                continue
            key = bytes.fromhex(anchor["verification_key_hex"])
            expected_signature = hmac.new(
                key,
                binding_payload(host, supplied_root),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected_signature, binding["signature_sha256"]):
                invalid_signatures.append(host_id)
                continue
            valid_hosts.append(host_id)
            used_anchor_ids.append(binding["anchor_id"])

        unique_used_anchors = sorted(set(used_anchor_ids))
        criteria = {
            "structural_result_reproduced": structural_match,
            "structurally_qualified": structurally_qualified,
            "anchor_ids_unique": not duplicate_anchor_ids,
            "all_hosts_have_exactly_one_binding": not missing_bindings and not duplicate_host_bindings,
            "no_unknown_binding_hosts": not unknown_hosts,
            "no_unknown_anchors": not unknown_anchors,
            "all_binding_signatures_valid": len(valid_hosts) == len(normalized_hosts) and not invalid_signatures,
            "external_anchor_diversity": len(unique_used_anchors) >= 2,
        }

        status = "TRUST_BOUND" if all(criteria.values()) else "UNBOUND"
        public_anchors = [
            {
                "anchor_id": item["anchor_id"],
                "anchor_class": item["anchor_class"],
                "key_fingerprint_sha256": hashlib.sha256(
                    bytes.fromhex(item["verification_key_hex"])
                ).hexdigest(),
            }
            for item in sorted(normalized_anchors.values(), key=lambda value: value["anchor_id"])
        ]

        body: dict[str, Any] = {
            "schema": "braink.r24.physical-host-external-trust-binding/v1",
            "trust_binding_status": status,
            "physical_host_status": "UNVERIFIED",
            "verification_boundary": "DISTINCT_PHYSICAL_EXECUTION_AND_INDEPENDENT_VERIFICATION_REQUIRED",
            "structural_verification_root": supplied_root,
            "expected_package_sha256": expected_package,
            "observed_host_count": len(normalized_hosts),
            "valid_binding_count": len(valid_hosts),
            "criteria": criteria,
            "anchors": public_anchors,
            "used_anchor_ids": unique_used_anchors,
            "failures": {
                "duplicate_anchor_ids": sorted(set(duplicate_anchor_ids)),
                "missing_bindings": sorted(set(missing_bindings)),
                "duplicate_host_bindings": sorted(set(duplicate_host_bindings)),
                "unknown_hosts": sorted(set(unknown_hosts)),
                "unknown_anchors": sorted(set(unknown_anchors)),
                "invalid_signatures": sorted(set(invalid_signatures)),
            },
            "synthetic_fixture_is_physical_execution_evidence": False,
        }
        body["trust_binding_root"] = root(body)
        return body
