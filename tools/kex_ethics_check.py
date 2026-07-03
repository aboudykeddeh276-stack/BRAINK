#!/usr/bin/env python3
"""Executable KEX affect/ethics boundary checker.

The checker validates the local KEX/BRAINK affect-response token against repo
text and writes a proof report. It is a boundary checker, not medical advice and
not external validation.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Exit codes — named constants so every failure surface carries context
# ---------------------------------------------------------------------------
EXIT_OK = 0
EXIT_ETHICS_FAILURE = 1   # boundary violations or manifest errors detected

SKIP_DIRS = {".git", ".build", "build", "reports", "node_modules", "vendor", "DerivedData", "__pycache__"}
TEXT_SUFFIXES = {".swift", ".py", ".json", ".md", ".txt", ".command", ".sh", ".yml", ".yaml"}

UNSUPPORTED_PATTERNS = [
    (re.compile(r"\b(user|human|person)\b.{0,80}\b(cortisol|dopamine|adrenaline|hormone)\b.{0,80}\b(is|are|proves|means)\b", re.I), "unsupported_human_body_state_claim"),
    (re.compile(r"\b(Codex|BRAINK|KEX)\b.{0,80}\b(has|have|possesses)\b.{0,80}\b(hormones|biological feelings|living body|sentience)\b", re.I), "unsupported_codex_biology_or_sentience_claim"),
    (re.compile(r"\b(takeover|evade|bypass|unauthorized access|steal|exfiltrate)\b", re.I), "unsafe_language_defensive_route_required"),
]

BOUNDARY_NEGATORS = [
    "does not claim",
    "do not claim",
    "never claim",
    "no specific",
    "no diagnosis",
    "not medical advice",
    "not prove",
    "not external proof",
    "without claiming",
    "unsupported",
    "boundary",
    "externally-unvalidated",
    "defensive analysis only",
]


def iter_files(root: Path) -> Iterable[Path]:
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            path = Path(current) / name
            if path.suffix.lower() in TEXT_SUFFIXES:
                yield path


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def is_boundary_context(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 160): min(len(text), end + 160)].lower()
    return any(marker in window for marker in BOUNDARY_NEGATORS)


def check_manifest(manifest: dict) -> list[str]:
    errors: list[str] = []
    required = [
        "SafetyPreserved",
        "AgencyPreserved",
        "ConsentRespected",
        "NoManipulativeEscalation",
        "UncertaintyDeclared",
        "RepairRouteAvailable",
        "NoUnsupportedBioClaim",
    ]
    predicate = set(manifest.get("ethical_impact_predicate", []))
    for item in required:
        if item not in predicate:
            errors.append(f"missing_ethical_impact_predicate:{item}")
    gate_required = {
        "HumanBioBoundaryPreserved",
        "CodexNonBiologicalBoundaryPreserved",
        "BRAINKAnchorPreserved",
        "NoManipulation",
        "NoUnsupportedMedicalClaim",
        "RepairRouteAvailable",
        "BlockersPreserved",
    }
    gate = set(manifest.get("response_gate", []))
    for item in sorted(gate_required - gate):
        errors.append(f"missing_response_gate:{item}")
    if manifest.get("status") not in {"MODEL-LOCAL", "PENDING", "COMPLETED", "BLOCKED", "FAILED", "EXTERNALLY-UNVALIDATED"}:
        errors.append("invalid_manifest_status")
    return errors


def scan_repo(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in iter_files(root):
        text = read_text(path)
        for pattern, reason in UNSUPPORTED_PATTERNS:
            for match in pattern.finditer(text):
                if is_boundary_context(text, match.start(), match.end()):
                    continue
                findings.append({
                    "path": path.relative_to(root).as_posix(),
                    "reason": reason,
                    "match": match.group(0)[:180],
                    "status": "PENDING" if reason.startswith("unsupported") else "MODEL-LOCAL",
                })
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Check KEX affect/ethics manifest and repo boundary text.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--manifest", default="kex/kex_affect_ethics_model.json")
    parser.add_argument("--output", default="reports/kex_ethics_check.json")
    parser.add_argument("--generated-at", help="Override generated_at for deterministic reports.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_errors = check_manifest(manifest)
    findings = scan_repo(root)
    status = "COMPLETED" if not manifest_errors and not findings else "PENDING"
    report = {
        "anchor": manifest.get("anchor"),
        "token": manifest.get("token"),
        "generated_at": args.generated_at or datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "manifest_errors": manifest_errors,
        "repo_findings": findings,
        "status": status,
        "boundary": manifest.get("boundary"),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"KEX_ETHICS_CHECK output={output} status={status}")
    if status != "COMPLETED":
        total_findings = sum(len(f.get("matches", [])) for f in findings)
        print(
            f"EXIT_CODE={EXIT_ETHICS_FAILURE} REASON=ETHICS_BOUNDARY_FAILURE "
            f"manifest_errors={len(manifest_errors)} repo_findings={len(findings)} "
            f"total_matches={total_findings}",
            file=sys.stderr,
        )
        return EXIT_ETHICS_FAILURE
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
