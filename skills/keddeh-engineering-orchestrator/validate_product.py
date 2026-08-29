#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


def load_json(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def validate_product() -> list[str]:
    errors: list[str] = []
    manifest = load_json("product_manifest.json")

    if manifest.get("product_id") != "product://keddeh/engineering-orchestrator":
        errors.append("product:invalid_product_id")
    if manifest.get("short_name") != "KEO":
        errors.append("product:invalid_short_name")
    if manifest.get("privacy_default") != "LOCAL_ONLY_NO_SOURCE_UPLOAD":
        errors.append("product:privacy_default_not_local_only")
    if manifest.get("global_stop") is not False:
        errors.append("product:global_stop_must_be_false")
    if manifest.get("cli", {}).get("third_party_runtime_dependencies") != []:
        errors.append("product:runtime_dependencies_not_empty")
    if set(manifest.get("starter_profiles", [])) != {"server", "bios-firmware", "hardware-abstraction"}:
        errors.append("product:starter_profiles_incomplete")
    if "Lovable" not in manifest.get("excluded_tools", []):
        errors.append("product:lovable_not_excluded")

    required_files = {
        "keo.py",
        "pyproject.toml",
        "QUICKSTART.md",
        "MARKET_PRODUCT_CASE_STUDY.md",
        "product_manifest.json",
        "test_product_cli.py",
        "SECURITY.md",
        "SUPPORT.md",
        "RELEASE_READINESS.md",
    }
    for filename in sorted(required_files):
        if not (ROOT / filename).exists():
            errors.append(f"product:missing_file:{filename}")

    if errors:
        return errors

    version = subprocess.run(
        [sys.executable, str(ROOT / "keo.py"), "version"],
        check=False,
        capture_output=True,
        text=True,
    )
    if version.returncode != 0 or version.stdout.strip() != manifest.get("version"):
        errors.append("product:cli_version_manifest_mismatch")

    profiles = subprocess.run(
        [sys.executable, str(ROOT / "keo.py"), "profiles"],
        check=False,
        capture_output=True,
        text=True,
    )
    if profiles.returncode != 0 or set(profiles.stdout.split()) != set(manifest.get("starter_profiles", [])):
        errors.append("product:cli_profiles_manifest_mismatch")

    with tempfile.TemporaryDirectory() as temp:
        project = Path(temp) / "market-readiness-server"
        init_result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "keo.py"),
                "init",
                str(project),
                "--name",
                "Market Readiness Server",
                "--profile",
                "server",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if init_result.returncode != 0:
            errors.append("product:quickstart_init_failed")
            return errors

        validate_result = subprocess.run(
            [sys.executable, str(ROOT / "keo.py"), "validate", str(project)],
            check=False,
            capture_output=True,
            text=True,
        )
        if validate_result.returncode != 0:
            errors.append("product:quickstart_validate_failed")

        inspect_result = subprocess.run(
            [sys.executable, str(ROOT / "keo.py"), "inspect", str(project)],
            check=False,
            capture_output=True,
            text=True,
        )
        if inspect_result.returncode != 0:
            errors.append("product:quickstart_inspect_failed")

    return errors


def main() -> int:
    errors = validate_product()
    result = {
        "product_id": "product://keddeh/engineering-orchestrator",
        "version": load_json("product_manifest.json").get("version"),
        "valid": not errors,
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
