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
    "GENERATED_VALUE": re.compile(r"Math\.random\s*\(|random\.(?:random|randint)\s*\("),
    "HARDWARE_REPRESENTATION": re.compile(r"(?:Infinity\s*x\s*Infinity|∞\s*GHz|4096GiB|1024GB\s*HBM|quantum\s+core)", re.I),
    "ASSURANCE_REPRESENTATION": re.compile(r"(?:ISO[- ]?9001|ISO[- ]?27001|CERTIFIED|ATTESTED|MERKLE_VERIFIED|LATTICE_SIGNED)", re.I),
    "DECLARED_HEALTH": re.compile(r"(?:status\s*[:=]\s*['\"](?:ONLINE|STABLE|SYNCHRONIZED|HEALTHY)['\"])", re.I),
    "EXECUTION_REPRESENTATION": re.compile(r"(?:simulat(?:e|ed|ion)|command executed securely|Deploying workload across|Synchronization complete)", re.I),
}

SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".py", ".html"}

# Invariants apply to every execution plane. Variants are contextual and may be valid
# when their environment, observer, purpose and evidence source are explicitly declared.
INVARIANTS = {
    "I1_SOURCE_PRESERVATION": "The source expression and its role must be preserved.",
    "I2_CONTEXT_DECLARATION": "Environment, observer, execution plane and purpose must be declared.",
    "I3_EVIDENCE_SEPARATION": "Projection, fixture, model and live observation must remain distinguishable.",
    "I4_CAPABILITY_SCOPING": "A finding may constrain only the capability it concerns.",
    "I5_NON_TERMINAL_CLASSIFICATION": "A lexical finding is not by itself proof of invalidity or impossibility.",
}

CONTEXT_MARKERS = {
    "FIXTURE": re.compile(r"fixture|test[_ -]?data|mock[_ -]?input", re.I),
    "SIMULATION": re.compile(r"simulat(?:e|ed|ion)|synthetic", re.I),
    "PROJECTION": re.compile(r"projection|display|visual|animation|demo", re.I),
    "OBSERVED": re.compile(r"observed|readback|receipt|probe|heartbeat|measured", re.I),
    "TARGET_DECLARATION": re.compile(r"target|expected|desired|profile|manifest", re.I),
    "LOAD_TEST": re.compile(r"load[_ -]?test|fuzz|stress|benchmark[_ -]?input", re.I),
}

@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    category: str
    excerpt: str
    context_variant: str
    invariant_assessment: str
    evidence_requirement: str
    capability_effect: str
    derived_state: str


def iter_sources(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES:
            if any(part in {"node_modules", ".git", "dist", "build"} for part in path.parts):
                continue
            yield path


def infer_context(path: Path, line: str) -> str:
    joined = f"{path.as_posix()} {line}"
    for name, pattern in CONTEXT_MARKERS.items():
        if pattern.search(joined):
            return name
    return "UNDECLARED_CONTEXT"


def assess(category: str, context: str) -> tuple[str, str, str, str]:
    if context in {"FIXTURE", "SIMULATION", "PROJECTION", "LOAD_TEST", "TARGET_DECLARATION"}:
        return (
            "CONTEXTUALLY_VALID_VARIANT",
            "Preserve the declared non-live role and prevent promotion as direct runtime observation.",
            "No capability stop; retain explicit context label.",
            "DECLARED_VARIANT",
        )
    if context == "OBSERVED":
        return (
            "REQUIRES_RECEIPT_CORRELATION",
            "Bind the value to a timestamped source receipt, observer, node and readback path.",
            "Hold only the associated promotion claim until correlation succeeds.",
            "EVIDENCE_CORRELATION_REQUIRED",
        )
    requirements = {
        "GENERATED_VALUE": "Declare whether the generator is fixture, model, uncertainty, animation, test load or fallback.",
        "HARDWARE_REPRESENTATION": "Declare target, emulated, imported, measured or host-readback hardware plane.",
        "ASSURANCE_REPRESENTATION": "Declare whether this is policy alignment, target gate, imported assertion or verified receipt.",
        "DECLARED_HEALTH": "Bind health to an observer, freshness limit, heartbeat/readback source and failure policy.",
        "EXECUTION_REPRESENTATION": "Declare whether execution is modeled, emulated, delegated, local, remote or hardware-backed.",
    }
    return (
        "CONTEXT_INCOMPLETE",
        requirements[category],
        "Do not globally stop; open a bounded context-and-evidence resolution task.",
        "CONTEXT_RESOLUTION_REQUIRED",
    )


def scan_file(root: Path, path: Path) -> List[Finding]:
    findings: List[Finding] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return findings
    for number, line in enumerate(lines, start=1):
        for category, pattern in PATTERNS.items():
            if pattern.search(line):
                context = infer_context(path.relative_to(root), line)
                invariant, requirement, effect, state = assess(category, context)
                findings.append(Finding(
                    path=str(path.relative_to(root)),
                    line=number,
                    category=category,
                    excerpt=line.strip()[:240],
                    context_variant=context,
                    invariant_assessment=invariant,
                    evidence_requirement=requirement,
                    capability_effect=effect,
                    derived_state=state,
                ))
    return findings


def run_gate(root: Path, emit_receipt: bool = False) -> dict:
    root = root.expanduser().resolve()
    sources = list(iter_sources(root))
    findings: List[Finding] = []
    for path in sources:
        findings.extend(scan_file(root, path))

    unresolved = [f for f in findings if f.derived_state == "CONTEXT_RESOLUTION_REQUIRED"]
    correlation = [f for f in findings if f.derived_state == "EVIDENCE_CORRELATION_REQUIRED"]
    declared = [f for f in findings if f.derived_state == "DECLARED_VARIANT"]

    promotion_state = "LOCAL_PASS"
    if unresolved:
        promotion_state = "CONTEXT_RESOLUTION_REQUIRED"
    elif correlation:
        promotion_state = "EVIDENCE_CORRELATION_REQUIRED"
    elif declared:
        promotion_state = "PASS_WITH_DECLARED_VARIANTS"

    payload = {
        "version": "V99-EVIDENCE-CONTEXT-2",
        "scanned_root": str(root),
        "source_files_scanned": len(sources),
        "invariants": INVARIANTS,
        "finding_count": len(findings),
        "declared_variant_count": len(declared),
        "evidence_correlation_count": len(correlation),
        "context_resolution_count": len(unresolved),
        "categories": sorted({finding.category for finding in findings}),
        "findings": [asdict(finding) for finding in findings],
        "promotion_state": promotion_state,
        "global_stop": False,
        "rule": "lexical indicators are contextual variants; status is derived only after environment, observer, purpose, execution plane and evidence are resolved",
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
