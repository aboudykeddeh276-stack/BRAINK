#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / ".kex" / "runner-control-plane.json"
REPORT_DIR = ROOT / "reports" / "kex-ci"
MODES = {"health", "cascade", "substrate", "openapi", "proof", "object-runtime", "stress", "deploy"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def finding(kind: str, code: str, detail: str, path: str | None = None) -> dict:
    return {"kind": kind, "code": code, "detail": detail, "path": path}


def discover_files() -> list[str]:
    out = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if ".git" in rel.parts:
            continue
        out.append(rel.as_posix())
    return sorted(out)


def inspect_runtime_surfaces(paths: list[str]) -> dict:
    return {
        "workbook": [p for p in paths if p.lower().endswith((".xlsx", ".xlsm"))],
        "hyperk0": [p for p in paths if "hyperk0" in p.lower()],
        "indexeddb": [p for p in paths if "indexeddb" in p.lower()],
        "kex_uri": [p for p in paths if "kex" in p.lower() and ("uri" in p.lower() or "route" in p.lower())],
        "openapi": [p for p in paths if "openapi" in p.lower()],
        "proof": [p for p in paths if "proof" in p.lower() or "ledger" in p.lower()],
        "docker": [p for p in paths if p.lower().endswith("dockerfile") or "docker" in p.lower()],
        "deployment": [p for p in paths if p.startswith("deploy/") or "deploy" in p.lower()],
        "object_runtime": [p for p in paths if "object" in p.lower() and ("runtime" in p.lower() or "registry" in p.lower())],
    }


def check_base(manifest: dict, paths: list[str]) -> list[dict]:
    findings = []
    for wf in manifest["required_workflows"]:
        if wf not in paths:
            findings.append(finding("DEFECT", "MISSING_REQUIRED_WORKFLOW", wf, wf))
    for required in ("README.md", "LICENSE", ".gitignore"):
        if required not in paths:
            findings.append(finding("DEFECT", "MISSING_GOVERNANCE_BASELINE", required, required))
    if len(set(manifest["cascade_order"])) != len(manifest["cascade_order"]):
        findings.append(finding("DEFECT", "CASCADE_ORDER_DUPLICATE", "cascade order contains duplicates"))
    if len(set(manifest["warm_boot_order"])) != len(manifest["warm_boot_order"]):
        findings.append(finding("DEFECT", "WARM_BOOT_ORDER_DUPLICATE", "warm boot order contains duplicates"))
    return findings


def check_mode(mode: str, surfaces: dict) -> list[dict]:
    findings = []
    required = {
        "cascade": ["hyperk0", "indexeddb", "kex_uri"],
        "substrate": ["workbook"],
        "openapi": ["openapi"],
        "proof": ["proof"],
        "object-runtime": ["object_runtime"],
        "deploy": ["deployment"],
    }
    for surface in required.get(mode, []):
        if not surfaces[surface]:
            findings.append(finding(
                "UNRESOLVED",
                "RUNTIME_SURFACE_NOT_RESIDENT",
                f"{surface} implementation surface was not discovered; the workflow exists but execution cannot be promoted to runtime success"
            ))
    if mode == "stress" and not any(surfaces[k] for k in ("hyperk0", "workbook", "object_runtime")):
        findings.append(finding("UNRESOLVED", "NO_STRESS_TARGET", "no executable workbook/HyperK0/object-runtime surface was discovered"))
    return findings


def build_receipt(mode: str) -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    paths = discover_files()
    surfaces = inspect_runtime_surfaces(paths)
    findings = check_base(manifest, paths) + check_mode(mode, surfaces)
    defects = [x for x in findings if x["kind"] == "DEFECT"]
    unresolved = [x for x in findings if x["kind"] == "UNRESOLVED"]
    state = "PASS" if not defects and not unresolved else ("FAIL" if defects else "UNRESOLVED_RUNTIME_SURFACE")
    return {
        "schema": "kex.ci.receipt.v1",
        "mode": mode,
        "state": state,
        "timestamp": time.time(),
        "git_sha": os.getenv("GITHUB_SHA"),
        "git_ref": os.getenv("GITHUB_REF"),
        "runner_name": os.getenv("RUNNER_NAME"),
        "runner_os": os.getenv("RUNNER_OS"),
        "cascade_order": manifest["cascade_order"],
        "warm_boot_order": manifest["warm_boot_order"],
        "acceptance_rule": manifest["acceptance_rule"],
        "discovered_surface_counts": {k: len(v) for k, v in surfaces.items()},
        "discovered_surfaces": surfaces,
        "findings": findings,
        "proof": {"manifest_sha256": sha256(MANIFEST), "file_count": len(paths)},
        "claim_boundary": "PASS means the declared repository checks for this mode completed. It does not imply absent runtime surfaces executed. UNRESOLVED_RUNTIME_SURFACE means the workflow/control contract is resident but a required implementation surface was not discovered."
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=sorted(MODES), required=True)
    ap.add_argument("--strict-unresolved", action="store_true")
    args = ap.parse_args()
    receipt = build_receipt(args.mode)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / f"{args.mode}.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    if receipt["state"] == "FAIL":
        return 1
    if args.strict_unresolved and receipt["state"] == "UNRESOLVED_RUNTIME_SURFACE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
