#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "governance" / "control_skeleton" / "generate_governance.py"
DEFAULT_REGISTRY = ROOT / "governance" / "GOVERNANCE_TARGET_REGISTRY.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    ap.add_argument("--output-root", type=Path, default=ROOT / "governance" / "generated")
    ap.add_argument("--component-id")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    registry = json.loads(args.registry.read_text("utf-8"))
    if registry.get("schema") != "kex.braink.governance-target-registry.v1":
        raise SystemExit("INVALID_GOVERNANCE_TARGET_REGISTRY")

    selected = []
    for target in registry.get("targets", []):
        if args.component_id and target.get("component_id") != args.component_id:
            continue
        if not target.get("spec"):
            continue
        selected.append(target)

    results = []
    for target in selected:
        spec = ROOT / target["spec"]
        if not spec.is_file():
            results.append({"component_id": target["component_id"], "status": "BLOCKED", "reason": "SPEC_NOT_FOUND"})
            continue
        out = args.output_root / target["component_id"]
        cmd = [sys.executable, str(GEN), "--spec", str(spec), "--output", str(out)]
        if args.force:
            cmd.append("--force")
        p = subprocess.run(cmd, capture_output=True, text=True)
        results.append({
            "component_id": target["component_id"],
            "status": "GENERATED" if p.returncode == 0 else "BLOCKED",
            "returncode": p.returncode,
            "stdout": p.stdout[-2000:],
            "stderr": p.stderr[-2000:],
            "output": str(out),
        })

    print(json.dumps({"schema":"kex.braink.governance-scaffold-run.v1","results":results}, indent=2, sort_keys=True))
    return 0 if all(r["status"] == "GENERATED" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
