#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

PATTERNS = {
    "GENERATED_VALUE": re.compile(r"Math\.random\s*\(|random\.(?:random|randint)\s*\("),
    "HARDWARE_REPRESENTATION": re.compile(r"(?:Infinity\s*x\s*Infinity|∞\s*GHz|4096GiB|1024GB\s*HBM|quantum\s+core)", re.I),
    "ASSURANCE_REPRESENTATION": re.compile(r"(?:ISO[- ]?9001|ISO[- ]?27001|CERTIFIED|ATTESTED|MERKLE_VERIFIED|LATTICE_SIGNED)", re.I),
    "DECLARED_HEALTH": re.compile(r"(?:status\s*[:=]\s*['\"](?:ONLINE|STABLE|SYNCHRONIZED|HEALTHY)['\"])", re.I),
    "EXECUTION_REPRESENTATION": re.compile(r"(?:simulat(?:e|ed|ion)|command executed securely|Deploying workload across|Synchronization complete)", re.I),
}
SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".py", ".html"}
INVARIANTS = {
    "I1_SOURCE_PRESERVATION": "The source expression and its role must be preserved.",
    "I2_CONTEXT_DECLARATION": "Environment, observer, execution plane and purpose must be declared.",
    "I3_EVIDENCE_SEPARATION": "Projection, fixture, model and live observation must remain distinguishable.",
    "I4_CAPABILITY_SCOPING": "A finding may constrain only the capability it concerns.",
    "I5_NON_TERMINAL_CLASSIFICATION": "A lexical finding is not by itself proof of invalidity or impossibility.",
    "I6_LINEAGE_AND_FRESHNESS": "Observed evidence must retain source lineage, timestamp and freshness policy.",
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
class EvidenceContext:
    capability: str
    purpose: str
    observer: str
    environment: str
    execution_plane: str
    evidence_class: str
    promotion_boundary: str
    source: str

@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    category: str
    excerpt: str
    context: Dict[str, str]
    invariant_assessment: str
    evidence_requirement: str
    capability_effect: str
    derived_state: str
    continuation_packet: str


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def iter_sources(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES:
            if any(part in {"node_modules", ".git", "dist", "build", "runtime_volume"} for part in path.parts):
                continue
            yield path


def load_registry(root: Path) -> Dict[str, Any]:
    return read_json(root / "config" / "evidence_context_registry.json", {"contexts": []})


def registry_context(relative: str, registry: Dict[str, Any]) -> Optional[EvidenceContext]:
    for item in registry.get("contexts", []):
        if fnmatch.fnmatch(relative, item["path_pattern"]):
            return EvidenceContext(
                capability=item["capability"], purpose=item["purpose"], observer=item["observer"],
                environment=item["environment"], execution_plane=item["execution_plane"],
                evidence_class=item["evidence_class"], promotion_boundary=item["promotion_boundary"],
                source=f"registry:{item['path_pattern']}",
            )
    return None


def inferred_context(relative: str, line: str) -> EvidenceContext:
    joined = f"{relative} {line}"
    purpose = "UNDECLARED"
    for name, pattern in CONTEXT_MARKERS.items():
        if pattern.search(joined):
            purpose = name
            break
    if purpose in {"FIXTURE", "LOAD_TEST"}:
        evidence_class, plane, observer = "GENERATED", "LOCAL_PROCESS", "TEST_HARNESS"
    elif purpose in {"PROJECTION", "SIMULATION"}:
        evidence_class, plane, observer = "MODELED", "BROWSER_PROJECTION", "UI_PROJECTION"
    elif purpose == "OBSERVED":
        evidence_class, plane, observer = "OBSERVED", "UNDECLARED", "UNDECLARED"
    elif purpose == "TARGET_DECLARATION":
        evidence_class, plane, observer = "DECLARED", "UNDECLARED", "CONFIGURATION"
    else:
        evidence_class, plane, observer = "UNDECLARED", "UNDECLARED", "UNDECLARED"
    return EvidenceContext(
        capability="UNDECLARED_CAPABILITY", purpose=purpose, observer=observer,
        environment="UNDECLARED", execution_plane=plane, evidence_class=evidence_class,
        promotion_boundary="UNDECLARED", source="inferred",
    )


def assess(category: str, context: EvidenceContext) -> tuple[str, str, str, str]:
    if context.purpose in {"FIXTURE", "SIMULATION", "PROJECTION", "LOAD_TEST", "TARGET_DECLARATION"}:
        return (
            "CONTEXTUALLY_VALID_VARIANT",
            "Preserve the declared role and enforce its promotion boundary.",
            f"Constrain only {context.capability}; no global stop.",
            "DECLARED_VARIANT",
        )
    if context.evidence_class in {"OBSERVED", "MEASURED"}:
        return (
            "REQUIRES_RECEIPT_CORRELATION",
            "Bind timestamp, freshness, observer, node, source receipt and independent readback.",
            f"Hold only promotion of {context.capability} until correlation succeeds.",
            "EVIDENCE_CORRELATION_REQUIRED",
        )
    requirements = {
        "GENERATED_VALUE": "Declare fixture, model, uncertainty, animation, load-test or fallback purpose.",
        "HARDWARE_REPRESENTATION": "Declare target, emulator, imported, measured, host or provider execution plane.",
        "ASSURANCE_REPRESENTATION": "Declare policy alignment, target gate, imported assertion or verified receipt.",
        "DECLARED_HEALTH": "Bind health to observer, freshness, heartbeat/readback source and failure policy.",
        "EXECUTION_REPRESENTATION": "Declare modeled, emulated, delegated, local, remote or hardware-backed execution.",
    }
    return (
        "CONTEXT_INCOMPLETE",
        requirements[category],
        f"Open bounded resolution for {context.capability}; preserve unaffected domains.",
        "CONTEXT_RESOLUTION_REQUIRED",
    )


def continuation_task(root: Path, relative: str, number: int, category: str, excerpt: str,
                      context: EvidenceContext, requirement: str, state: str) -> str:
    if state == "DECLARED_VARIANT":
        return ""
    packet = {
        "blocked_capability": context.capability,
        "blocked_domain": relative,
        "criticality": "CORE_DEGRADED",
        "root_cause": f"{category}:{state}",
        "impact_radius": [context.capability],
        "unaffected_domains": ["all capabilities outside declared impact radius"],
        "continuation_mode": "preserve source and continue unrelated runtime domains",
        "fallback_adapter": "context_registry_or_receipt_correlation",
        "durable_outbox": "runtime_volume/outbox/evidence_context/",
        "research_basis": ["invariant-variant contextual evidence model", "capability-scoped promotion"],
        "required_changes": [requirement],
        "positive_tests": ["declared context resolves to bounded derived state"],
        "negative_tests": ["one lexical signal cannot produce global stop"],
        "failover_tests": ["unrelated capabilities remain operational"],
        "recovery_tests": ["receipt or context declaration satisfies re-entry"],
        "reentry_conditions": ["observer, environment, execution plane, evidence class and promotion boundary resolved"],
        "promotion_evidence": ["context registry entry or timestamped correlated receipt"],
        "owner": "evidence-context-governance",
        "source": {"path": relative, "line": number, "excerpt": excerpt},
        "context": asdict(context),
    }
    packet_id = canonical_hash(packet)
    path = root / "runtime_volume" / "workplans" / "evidence_context" / f"{packet_id}.json"
    write_json(path, packet)
    return str(path)


def scan_file(root: Path, path: Path, registry: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    relative = str(path.relative_to(root))
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return findings
    for number, line in enumerate(lines, start=1):
        for category, pattern in PATTERNS.items():
            if not pattern.search(line):
                continue
            context = registry_context(relative, registry) or inferred_context(relative, line)
            invariant, requirement, effect, state = assess(category, context)
            packet = continuation_task(root, relative, number, category, line.strip()[:240], context, requirement, state)
            findings.append(Finding(
                path=relative, line=number, category=category, excerpt=line.strip()[:240],
                context=asdict(context), invariant_assessment=invariant,
                evidence_requirement=requirement, capability_effect=effect,
                derived_state=state, continuation_packet=packet,
            ))
    return findings


def run_gate(root: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    root = root.expanduser().resolve()
    registry = load_registry(root)
    sources = list(iter_sources(root))
    findings: List[Finding] = []
    for path in sources:
        findings.extend(scan_file(root, path, registry))
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
        "version": "V99-EVIDENCE-CONTEXT-3",
        "scanned_root": str(root),
        "source_files_scanned": len(sources),
        "invariants": INVARIANTS,
        "registry_version": registry.get("version", "UNDECLARED"),
        "finding_count": len(findings),
        "declared_variant_count": len(declared),
        "evidence_correlation_count": len(correlation),
        "context_resolution_count": len(unresolved),
        "continuation_packet_count": sum(bool(f.continuation_packet) for f in findings),
        "categories": sorted({finding.category for finding in findings}),
        "findings": [asdict(finding) for finding in findings],
        "promotion_state": promotion_state,
        "global_stop": False,
        "rule": "status derives from invariant-preserving contextual resolution, not one-word matching",
        "timestamp": time.time(),
    }
    if emit_receipt:
        write_json(root / "evidence" / "evidence_authenticity_gate_receipt.json", payload)
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
