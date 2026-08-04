#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = ROOT.parent
INCLUDED = [
    "SKILL.md",
    "SOFTWARE_TOPOLOGY_STANDARD.md",
    "KEDDEH_INTERMEDIATE_REPRESENTATION.md",
    "IL_LLM_BILATERAL_TRANSLATION_CONTRACT.md",
    "LANGUAGE_TARGET_MATRIX.json",
    "naming_conventions.json",
    "iteration_lifecycle.json",
    "software_topology.schema.json",
    "keo.py",
    "pyproject.toml",
    "QUICKSTART.md",
    "SECURITY.md",
    "SUPPORT.md",
    "enterprise/portfolio-registry.json",
    "enterprise/naming-lineage-registry.json",
    "enterprise/bilateral-contracts.json",
    "enterprise/enterprise-trajectory.json",
    "enterprise/commercial-wedge.json",
    "enterprise/enterprise_portfolio_runtime.py",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(destination: Path, version: str) -> dict[str, object]:
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / f"KEDDEH_ENGINEERING_REGULATED_WORKFLOW_ALPHA_{version}.zip"
    entries: list[dict[str, object]] = []
    missing = [path for path in INCLUDED if not (PACKAGE_ROOT / path).is_file()]
    if missing:
        raise FileNotFoundError("missing_release_inputs:" + ",".join(missing))

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for relative in sorted(INCLUDED):
            source = PACKAGE_ROOT / relative
            data = source.read_bytes()
            info = zipfile.ZipInfo(f"keddeh-engineering-orchestrator/{relative}")
            info.date_time = (2026, 1, 1, 0, 0, 0)
            mode = 0o755 if os.access(source, os.X_OK) or relative.endswith(".py") else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            bundle.writestr(info, data)
            entries.append({"path": relative, "size": len(data), "sha256": sha256_bytes(data)})
        embedded_manifest = {
            "release_id": f"release://keddeh/engineering-regulated-workflow/{version}",
            "version": version,
            "files": entries,
            "artifact_state": "DURABLE_BYTES",
            "promotion_state": "CONTROLLED_ALPHA",
            "global_stop": False,
        }
        info = zipfile.ZipInfo("keddeh-engineering-orchestrator/RELEASE-MANIFEST.json")
        info.date_time = (2026, 1, 1, 0, 0, 0)
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        bundle.writestr(info, json.dumps(embedded_manifest, indent=2, sort_keys=True).encode("utf-8"))

    with zipfile.ZipFile(archive) as bundle:
        corrupt = bundle.testzip()
        names = set(bundle.namelist())
        expected = {f"keddeh-engineering-orchestrator/{path}" for path in INCLUDED}
        expected.add("keddeh-engineering-orchestrator/RELEASE-MANIFEST.json")
        readback_passed = corrupt is None and names == expected
        if not readback_passed:
            raise RuntimeError("release_readback_failed")

    archive_hash = sha256_bytes(archive.read_bytes())
    receipt = {
        "release_id": f"release://keddeh/engineering-regulated-workflow/{version}",
        "archive": archive.name,
        "archive_path": str(archive),
        "archive_size": archive.stat().st_size,
        "archive_sha256": archive_hash,
        "file_count": len(entries),
        "zip_integrity_passed": True,
        "independent_readback_passed": True,
        "artifact_state": "DURABLE_BYTES",
        "promotion_state": "CONTROLLED_ALPHA",
        "remaining_gates": [
            "cryptographic release signing",
            "owner-approved licence",
            "external clean-environment installation",
            "external user case study"
        ],
        "global_stop": False,
    }
    receipt_path = destination / f"KEDDEH_ENGINEERING_REGULATED_WORKFLOW_ALPHA_{version}.receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    checksum_path = destination / f"{archive.name}.sha256"
    checksum_path.write_text(f"{archive_hash}  {archive.name}\n", encoding="utf-8")
    return {**receipt, "receipt_path": str(receipt_path), "checksum_path": str(checksum_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic KEDDEH controlled-alpha release")
    parser.add_argument("--destination", type=Path, default=ROOT / "dist")
    parser.add_argument("--version", default="0.2.0-alpha.1")
    args = parser.parse_args()
    print(json.dumps(build(args.destination, args.version), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
