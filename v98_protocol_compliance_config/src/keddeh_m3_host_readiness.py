#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command_version(command: List[str]) -> str:
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)
        return (result.stdout or result.stderr).strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return "UNAVAILABLE"


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def collect_host_facts(root: Path) -> Dict[str, Any]:
    memory_bytes = 0
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        memory_bytes = int(page_size * pages)
    except (AttributeError, OSError, ValueError):
        pass
    disk = shutil.disk_usage(root)
    return {
        "hostname": platform.node(),
        "os_name": platform.system(),
        "os_version": platform.mac_ver()[0] or platform.release(),
        "architecture": platform.machine().lower(),
        "cpu_brand": platform.processor() or "UNRESOLVED",
        "logical_cpu_count": os.cpu_count() or 1,
        "physical_memory_bytes": memory_bytes,
        "free_disk_bytes": disk.free,
        "python_version": platform.python_version(),
        "node_version": command_version(["node", "--version"]),
        "git_version": command_version(["git", "--version"]),
        "runner_labels": sorted(filter(None, os.environ.get("RUNNER_LABELS", "").split(","))),
        "repository_head_sha": os.environ.get("GITHUB_SHA", command_version(["git", "rev-parse", "HEAD"])),
        "observed_at": time.time(),
    }


def validate_receipt(contract: Dict[str, Any], receipt: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    facts = receipt.get("host_facts", {})
    checks = receipt.get("checks", {})
    for field in contract["requiredHostFacts"]:
        if field not in facts or facts[field] in (None, ""):
            errors.append(f"missing_host_fact:{field}")
    for check in contract["requiredExecutableChecks"]:
        if checks.get(check) is not True:
            errors.append(f"check_not_passed:{check}")
    required_labels = set(contract["runnerLabels"])
    present_labels = set(facts.get("runner_labels", []))
    if not required_labels.issubset(present_labels):
        errors.append("runner_labels_incomplete")
    minimums = contract["minimums"]
    if facts.get("architecture", "").lower() not in {minimums["architecture"], "arm64", "aarch64"}:
        errors.append("architecture_mismatch")
    if int(facts.get("free_disk_bytes", 0)) < int(minimums["free_disk_bytes"]):
        errors.append("insufficient_free_disk")
    if int(facts.get("logical_cpu_count", 0)) < int(minimums["logical_cpu_count"]):
        errors.append("insufficient_logical_cpu_count")
    expected_hash = receipt.get("receipt_hash")
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    if expected_hash != canonical_hash(body):
        errors.append("receipt_hash_mismatch")
    return errors


def build_receipt(root: Path, check_results: Dict[str, bool]) -> Dict[str, Any]:
    contract = read_json(root / "config" / "m3_host_readiness_contract.json")
    body = {
        "version": contract["version"],
        "contract_id": contract["contractId"],
        "host_facts": collect_host_facts(root),
        "checks": check_results,
        "promotion_state": "TARGET_HOST_PASS" if all(check_results.values()) else "BOUNDED_STOP",
        "global_stop": False,
    }
    body["receipt_hash"] = canonical_hash(body)
    return body


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--receipt")
    parser.add_argument("--emit-template", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    contract = read_json(root / "config" / "m3_host_readiness_contract.json")
    if args.receipt:
        receipt = read_json(Path(args.receipt))
        errors = validate_receipt(contract, receipt)
        result = {"valid": not errors, "errors": errors, "promotion_state": "TARGET_HOST_PASS" if not errors else "HOST_RECEIPT_REJECTED", "global_stop": False}
    else:
        checks = {name: False for name in contract["requiredExecutableChecks"]}
        result = build_receipt(root, checks)
        if args.emit_template:
            write_json(root / "runtime_volume" / "workplans" / "m3_host_readiness" / "host_receipt_template.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("valid") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
