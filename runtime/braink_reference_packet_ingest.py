from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
from typing import Any
import json

STABLE_ROLES = {
    "MACHINE", "ENCODED_MEDIUM", "STORAGE_CONTROLLER", "BRAINK_ROOT",
    "VFS_RESOLVER", "OBSERVER", "NETWORK_BRIDGE", "SERVICE_FABRIC",
    "DOMAIN", "DNS", "REGISTRAR", "TLS", "CLOUD", "PROOF"
}

PROMOTION_STATES = {
    "REFERENCE_ONLY",
    "MAPPED",
    "CONTRADICTS_ACTIVE_STATE",
    "EXECUTION_REQUIRED",
    "READBACK_VERIFIED",
    "PROMOTED"
}

@dataclass
class ReferencePacket:
    packet_sha256: str
    source_label: str
    source_version_label: str | None
    source_agent: str | None
    classification: str
    mapped_roles: list[str]
    claims: list[str]
    promotion_state: str
    authority: str


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def infer_roles(packet: Any) -> list[str]:
    text = canonical_bytes(packet).decode("utf-8", errors="replace").upper()
    aliases = {
        "MACHINE": ("MACHINE", "VM", "COMPUTER"),
        "ENCODED_MEDIUM": ("ENCODED_MEDIUM", "MEDIUM", "STORAGE SUBSTRATE"),
        "STORAGE_CONTROLLER": ("STORAGE_CONTROLLER", "CONTROLLER", "ADAPTER"),
        "BRAINK_ROOT": ("BRAINK_ROOT", "BRAINK ID", "BRAINK_ID"),
        "VFS_RESOLVER": ("VFS", "VFS_RESOLVER"),
        "OBSERVER": ("OBSERVER", "FRAME", "REPRESENTATION"),
        "NETWORK_BRIDGE": ("NETWORK_BRIDGE", "LEX://", "VEC://", "ROUTE"),
        "SERVICE_FABRIC": ("SERVICE_FABRIC", "SERVER_ROOT", "SERVICE ROOT"),
        "DOMAIN": ("DOMAIN",),
        "DNS": ("DNS",),
        "REGISTRAR": ("REGISTRAR", "EPP", "REGISTRY"),
        "TLS": ("TLS", "CERTIFICATE", "ACME", "CA"),
        "CLOUD": ("CLOUD", "REPLICA", "REPLICATION"),
        "PROOF": ("PROOF", "RECEIPT", "READBACK", "VERIFIED")
    }
    roles = []
    for role, terms in aliases.items():
        if any(term in text for term in terms):
            roles.append(role)
    return roles


def extract_claims(packet: Any) -> list[str]:
    claims: list[str] = []
    if isinstance(packet, dict):
        for key in ("claims", "status", "result", "determination", "summary", "implemented", "verified", "deployed"):
            if key in packet:
                claims.append(f"{key}={packet[key]}")
    return claims


def ingest(packet: Any, source_label: str, source_agent: str | None = None,
           source_version_label: str | None = None) -> ReferencePacket:
    digest = sha256(canonical_bytes(packet)).hexdigest()
    return ReferencePacket(
        packet_sha256=digest,
        source_label=source_label,
        source_version_label=source_version_label,
        source_agent=source_agent,
        classification="REFERENCE_PACKET",
        mapped_roles=infer_roles(packet),
        claims=extract_claims(packet),
        promotion_state="REFERENCE_ONLY",
        authority="NO_RUNTIME_AUTHORITY_UNTIL_LOCAL_EXECUTION_AND_READBACK"
    )


def promote(reference: ReferencePacket, *, execution_evidence: dict[str, Any] | None,
            readback: dict[str, Any] | None) -> ReferencePacket:
    # Packet language, version names and self-declared status are intentionally ignored.
    if not execution_evidence:
        reference.promotion_state = "EXECUTION_REQUIRED"
        return reference
    if not readback or readback.get("status") not in {"PASS", "VERIFIED", "READBACK_VERIFIED"}:
        reference.promotion_state = "EXECUTION_REQUIRED"
        return reference
    reference.promotion_state = "PROMOTED"
    reference.authority = "PROMOTED_ONLY_FOR_LOCALLY_VERIFIED_PREDICATES"
    return reference


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Ingest another agent's packet as BRAINK reference evidence")
    parser.add_argument("packet")
    parser.add_argument("--source", default="external-agent")
    parser.add_argument("--agent")
    parser.add_argument("--version-label")
    parser.add_argument("--out", default="BRAINK_REFERENCE_PACKET_RECEIPT.json")
    args = parser.parse_args()
    packet = json.loads(Path(args.packet).read_text())
    receipt = ingest(packet, args.source, args.agent, args.version_label)
    Path(args.out).write_text(json.dumps(asdict(receipt), indent=2))
    print(json.dumps(asdict(receipt), indent=2))


if __name__ == "__main__":
    main()
