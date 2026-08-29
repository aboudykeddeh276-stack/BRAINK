#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

EPHEMERAL_PATTERNS = (
    re.compile(r"sandbox:/workspace/scratch/[^\s)]+"),
    re.compile(r"sandbox:/mnt/data/[^\s)]+"),
)
SAVE_CLAIM = re.compile(r"\b(saved|exported|complete|downloadable|uploaded)\b", re.IGNORECASE)


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_bytes(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ArtifactPreservationGuard:
    """Reject completion claims that are backed only by ephemeral paths or metadata records."""

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.registry = read_json(self.root / "config" / "cross_chat_artifact_preservation_registry.json")

    def validate_registry(self) -> List[str]:
        errors: List[str] = []
        for field in ("version", "registryId", "canonicalRule", "states", "requiredDurabilityEvidence", "confirmedIncidents"):
            if not self.registry.get(field):
                errors.append(f"registry:missing:{field}")
        for incident in self.registry.get("confirmedIncidents", []):
            if not incident.get("incidentId") or not incident.get("state"):
                errors.append("incident:missing_identity_or_state")
        return errors

    def scan_text(self, text: str, source: str = "inline") -> Dict[str, Any]:
        ephemeral: List[str] = []
        for pattern in EPHEMERAL_PATTERNS:
            ephemeral.extend(pattern.findall(text))
        claims = [line.strip() for line in text.splitlines() if SAVE_CLAIM.search(line)]
        return {
            "source": source,
            "ephemeral_references": sorted(set(ephemeral)),
            "save_claim_lines": claims,
            "requires_durability_reconciliation": bool(ephemeral),
        }

    def verify_file(self, path: Path, expected_sha256: Optional[str] = None) -> Dict[str, Any]:
        resolved = path.expanduser().resolve()
        if not resolved.exists() or not resolved.is_file():
            return {
                "path": str(resolved),
                "state": "MISSING_BYTES_CONFIRMED",
                "exists": False,
                "durable_bytes_verified": False,
            }
        digest = sha256_bytes(resolved)
        hash_matches = expected_sha256 is None or digest == expected_sha256
        return {
            "path": str(resolved),
            "state": "DURABLE_BYTES_VERIFIED" if hash_matches else "HASH_MISMATCH",
            "exists": True,
            "byte_size": resolved.stat().st_size,
            "sha256": digest,
            "expected_sha256": expected_sha256,
            "hash_matches": hash_matches,
            "durable_bytes_verified": hash_matches,
        }

    def audit_paths(self, paths: Iterable[Path]) -> Dict[str, Any]:
        results = [self.verify_file(path) for path in paths]
        return {
            "results": results,
            "verified": sum(1 for item in results if item["durable_bytes_verified"]),
            "missing_or_invalid": sum(1 for item in results if not item["durable_bytes_verified"]),
            "global_stop": False,
        }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--scan-file", action="append", default=[])
    parser.add_argument("--verify-file", action="append", default=[])
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)

    guard = ArtifactPreservationGuard(Path(args.root))
    errors = guard.validate_registry()
    scans = []
    for item in args.scan_file:
        path = Path(item)
        scans.append(guard.scan_text(path.read_text(encoding="utf-8"), str(path)))
    verification = guard.audit_paths(Path(item) for item in args.verify_file)
    payload = {
        "registry_valid": not errors,
        "errors": errors,
        "text_scans": scans,
        "file_verification": verification,
        "completion_rule": "saved requires durable byte readback; ephemeral links and manifests alone are insufficient",
        "global_stop": False,
    }
    if args.emit_receipt:
        write_json(guard.root / "evidence" / "artifact_preservation_guard_receipt.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
