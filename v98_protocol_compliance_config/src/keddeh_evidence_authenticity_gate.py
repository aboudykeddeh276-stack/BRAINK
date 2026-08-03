#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List

PATTERNS = {
    "RANDOMIZED_TELEMETRY": re.compile(r"Math\.random\s*\(|random\.(?:random|randint)\s*\("),
    "SYNTHETIC_HARDWARE_CLAIM": re.compile(r"(?:Infinity\s*x\s*Infinity|∞\s*GHz|4096GiB|1024GB\s*HBM|quantum\s+core)", re.I),
    "UNSUPPORTED_CERTIFICATION_CLAIM": re.compile(r"(?:ISO[- ]?9001|ISO[- ]?27001|CERTIFIED|ATTESTED|MERKLE_VERIFIED|LATTICE_SIGNED)", re.I),
    "HARDCODED_HEALTH": re.compile(r"(?:status\s*[:=]\s*['\"](?:ONLINE|STABLE|SYNCHRONIZED|HEALTHY)['\"])", re.I),
    "SIMULATED_EXECUTION": re.compile(r"(?:simulat(?:e|ed|ion)|command executed securely|Deploying workload across|Synchronization complete)", re.I),
}

SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".py", ".html"}

@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    category: str
    excerpt: str
    evidence_class: str


def iter_sources(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES:
            if any(part in {"node_modules", ".git", "dist", "build"} for part in path.parts):
                continue
            yield path


def scan_file(root: Path, path: Path) -> List[Finding]:
    findings: List[Finding] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return findings
    for number, line in enumerate(lines, start=1):
        for category, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append(Finding(
                    path=str(path.relative_to(root)),
                    line=number,
                    category=category,
                    excerpt=line.strip()[:240],
                    evidence_class="SIMULATED_OR_EVIDENCE_REQUIRED",
                ))
    return findings


def run_gate(root: Path, emit_receipt: bool = False) -> dict:
    root = root.expanduser().resolve()
    findings: List[Finding] = []
    for path in iter_sources(root):
        findings.extend(scan_file(root, path))
    categories = sorted({finding.category for finding in findings})
    payload = {
        "version": "V99-EVIDENCE-AUTHENTICITY-1",
        "scanned_root": str(root),
        "source_files_scanned": sum(1 for _ in iter_sources(root)),
        "finding_count": len(findings),
        "categories": categories,
        "findings": [asdict(finding) for finding in findings],
        "promotion_state": "EVIDENCE_REQUIRED" if findings else "LOCAL_PASS",
        "rule": "simulated, randomized, hard-coded or unsupported claims cannot be promoted as live capability evidence",
        "timestamp": time.time(),
    }
    if emit_receipt:
        target = root / "evidence" / "evidence_authenticity_gate_receipt.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args()
    result = run_gate(Path(args.root), emit_receipt=args.emit_receipt)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
