#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
OUT = ROOT / "reports" / "kex-ci" / "security.json"

findings = []
patterns = [
    ("UNSAFE_WORKFLOW_PERMISSION", re.compile(r"permissions\s*:\s*write-all", re.I)),
    ("UNSAFE_TRIGGER", re.compile(r"pull_request_target\s*:", re.I)),
    ("REMOTE_PIPE_TO_SHELL", re.compile(r"curl[^\n]*\|\s*(?:ba)?sh", re.I)),
    ("SECRET_ECHO_PATTERN", re.compile(r"echo[^\n]*secrets\.", re.I)),
]

for path in sorted(WORKFLOWS.glob("kex-*.yml")):
    text = path.read_text(encoding="utf-8")
    for code, pattern in patterns:
        if pattern.search(text):
            findings.append({
                "kind": "DEFECT",
                "code": code,
                "path": path.relative_to(ROOT).as_posix()
            })

receipt = {
    "schema": "kex.security-boundary.receipt.v1",
    "state": "PASS" if not findings else "FAIL",
    "files_scanned": len(list(WORKFLOWS.glob("kex-*.yml"))),
    "findings": findings,
    "claim_boundary": "PASS covers only the declared static workflow-boundary patterns; it does not prove host security or secret correctness."
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, indent=2))
raise SystemExit(0 if not findings else 1)
