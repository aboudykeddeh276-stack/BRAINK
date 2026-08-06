"""Evidence generation: manifests, test results and validation receipts."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from .canonical import canonical_hash

__all__ = [
    "generate_package_manifest",
    "generate_test_results",
    "generate_validation_receipt",
    "sha256_file",
    "EXCLUDED_DIRS",
]

EXCLUDED_DIRS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", "node_modules"}
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".sqlite-wal", ".sqlite-shm")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: str, chunk_size: int = 65536) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def generate_package_manifest(package_root: str) -> Dict[str, Any]:
    """Hash every file under ``package_root`` and return a manifest dict."""
    if not package_root or not os.path.isdir(package_root):
        raise ValueError("package_root must be an existing directory")
    root = os.path.abspath(package_root)
    files: Dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for filename in sorted(filenames):
            if filename.endswith(EXCLUDED_SUFFIXES):
                continue
            absolute = os.path.join(dirpath, filename)
            if not os.path.isfile(absolute):
                continue
            relative = os.path.relpath(absolute, root).replace(os.sep, "/")
            files[relative] = sha256_file(absolute)
    manifest = {
        "manifest_type": "PACKAGE_MANIFEST",
        "package_root": os.path.basename(root),
        "hash_algorithm": "sha256",
        "files": files,
        "file_count": len(files),
        "generated_at": _utc_now(),
    }
    manifest["manifest_hash"] = canonical_hash({"files": files})
    return manifest


def generate_test_results(
    passed: int,
    failed: int,
    errors: int,
    test_names: List[str],
    raw_summary: str = "",
) -> Dict[str, Any]:
    total = int(passed) + int(failed) + int(errors)
    status = "PASSED" if int(failed) == 0 and int(errors) == 0 and total > 0 else "FAILED"
    return {
        "receipt_type": "TEST_RESULTS",
        "status": status,
        "timestamp": _utc_now(),
        "tests_run": total,
        "passed": int(passed),
        "failed": int(failed),
        "errors": int(errors),
        "test_names": list(test_names),
        "raw_summary": raw_summary,
    }


def generate_validation_receipt(
    component_id: str, status: str, evidence: Dict[str, Any]
) -> Dict[str, Any]:
    if not component_id:
        raise ValueError("component_id must be provided")
    if not status:
        raise ValueError("status must be provided")
    if evidence is None:
        evidence = {}
    receipt = {
        "receipt_type": "VALIDATION_RECEIPT",
        "component_id": component_id,
        "status": status,
        "evidence": evidence,
        "generated_at": _utc_now(),
    }
    receipt["receipt_hash"] = canonical_hash(
        {"component_id": component_id, "status": status, "evidence": evidence}
    )
    return receipt
