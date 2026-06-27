#!/usr/bin/env python3
"""Validate BRAINK/KEX repository governance baseline artifacts."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    ".gitignore",
    "docs/governance/repository-governance-standard.md",
    "docs/governance/manifest.json",
    "scripts/validate-governance.py",
]
MANIFEST_PATH = "docs/governance/manifest.json"

REQUIRED_TOKENS = [
    "GOVERNANCE_ROOT",
    "REPOSITORY_WHOLE",
    "REPOSITORY_ENVIRONMENT",
    "REPOSITORY_STATE",
    "REPOSITORY_FUNCTION",
    "ENVIRONMENT_",
    "STATE_",
    "FUNCTION_",
    "WHOLE_",
    "ARTIFACT_",
    "PROOF_GATE_",
    "PENDING_",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_stable_sha256(path: Path) -> str:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for entry in manifest.values():
        if entry.get("path") == MANIFEST_PATH:
            entry["sha256"] = "SELF_HASH_NORMALIZED"
    stable_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return hashlib.sha256(stable_bytes).hexdigest()


def load_manifest(path: Path) -> dict[str, dict[str, str]]:
    return json.loads(path.read_text(encoding="utf-8"))


def expected_manifest(required_files: list[str]) -> dict[str, dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}
    for relative in required_files:
        artifact_suffix = relative.upper().replace(".", "_").replace("/", "_").replace("-", "_").strip("_")
        artifact_name = "ARTIFACT_" + artifact_suffix
        entries[artifact_name] = {
            "path": relative,
            "sha256": "SELF_HASH_NORMALIZED" if relative == MANIFEST_PATH else sha256(ROOT / relative),
            "state": "STATE_MODEL_LOCAL",
        }

    stable_hash = stable_manifest_sha256_from_entries(entries)
    for entry in entries.values():
        if entry["path"] == MANIFEST_PATH:
            entry["sha256"] = stable_hash
    return dict(sorted(entries.items()))


def stable_manifest_sha256_from_entries(entries: dict[str, dict[str, str]]) -> str:
    stable_entries = json.loads(json.dumps(entries))
    for entry in stable_entries.values():
        if entry.get("path") == MANIFEST_PATH:
            entry["sha256"] = "SELF_HASH_NORMALIZED"
    stable_bytes = (json.dumps(dict(sorted(stable_entries.items())), indent=2, sort_keys=True) + "\n").encode("utf-8")
    return hashlib.sha256(stable_bytes).hexdigest()


def write_manifest(path: Path) -> None:
    path.write_text(json.dumps(expected_manifest(REQUIRED_FILES), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    if "--write-manifest" in sys.argv:
        write_manifest(ROOT / MANIFEST_PATH)
        print("GOVERNANCE_MANIFEST_STATUS: UPDATED")
        return 0

    failures: list[str] = []
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            failures.append(f"missing required file: {relative}")

    standard_path = ROOT / "docs/governance/repository-governance-standard.md"
    if standard_path.is_file():
        standard_text = standard_path.read_text(encoding="utf-8")
        for token in REQUIRED_TOKENS:
            if token not in standard_text:
                failures.append(f"missing governance token in standard: {token}")

    manifest_path = ROOT / MANIFEST_PATH
    if manifest_path.is_file():
        manifest = load_manifest(manifest_path)
        expected_paths = set(REQUIRED_FILES)
        manifest_paths = {entry.get("path") for entry in manifest.values()}
        missing_manifest_paths = sorted(expected_paths - manifest_paths)
        extra_manifest_paths = sorted(path for path in manifest_paths - expected_paths if path)
        for missing_path in missing_manifest_paths:
            failures.append(f"required file missing from manifest: {missing_path}")
        for extra_path in extra_manifest_paths:
            failures.append(f"stale or unexpected manifest path: {extra_path}")
        for artifact_name, entry in manifest.items():
            path_value = entry.get("path")
            expected_hash = entry.get("sha256")
            state_value = entry.get("state")
            if not artifact_name.startswith("ARTIFACT_"):
                failures.append(f"manifest key lacks ARTIFACT_ prefix: {artifact_name}")
            if not state_value or not state_value.startswith("STATE_"):
                failures.append(f"manifest state lacks STATE_ prefix: {artifact_name}")
            if not path_value:
                failures.append(f"manifest path missing: {artifact_name}")
                continue
            artifact_path = ROOT / path_value
            if not artifact_path.is_file():
                failures.append(f"manifest artifact missing: {path_value}")
                continue
            actual_hash = manifest_stable_sha256(artifact_path) if path_value == MANIFEST_PATH else sha256(artifact_path)
            if expected_hash != actual_hash:
                failures.append(
                    f"manifest hash mismatch for {path_value}: expected {expected_hash}, actual {actual_hash}"
                )

    if failures:
        print("GOVERNANCE_CHECK_STATUS: FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("GOVERNANCE_CHECK_STATUS: COMPLETED")
    print(f"GOVERNANCE_REQUIRED_FILES: {len(REQUIRED_FILES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
