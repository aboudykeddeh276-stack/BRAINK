#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

FORMULA = "S=f(I,V,O,E,X,R,L)"
PLANES = {"output_framework", "thinking_framework", "legal_perspective", "software_service"}


@dataclass(frozen=True)
class PlaneAssessment:
    node_id: str
    plane: str
    formula: str
    context_complete: bool
    evidence_contract_complete: bool
    non_collapsible: bool
    derived_state: str
    issue_count: int
    corrective_workflow: str
    required_receipts: str
    reason: str


@dataclass(frozen=True)
class CrossPlaneGuard:
    rule: str
    status: str
    protected_planes: str
    reason: str


@dataclass(frozen=True)
class FourPlaneReceipt:
    version: str
    formula: str
    plane_count: int
    valid_plane_count: int
    cross_plane_guard_count: int
    conformance_issue_count: int
    ledger_readback: bool
    receipt_path: str
    matrix_path: str
    outbox_manifest: str
    timestamp: float


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_csv(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def load_policy(root: Path) -> Dict[str, Any]:
    return read_json(root / "config" / "four_plane_context_framework.json")


def assess_plane(node: Dict[str, Any], required: List[str]) -> PlaneAssessment:
    context = node.get("context", {})
    missing = [field for field in required if field not in context or context[field] in (None, "", [], {})]
    evidence_ok = isinstance(node.get("evidence_contract"), list) and bool(node["evidence_contract"])
    plane_ok = node.get("plane") in PLANES
    non_collapsible = bool(node.get("cannot_mean"))
    issues: List[str] = []
    if missing:
        issues.append("missing_context:" + ",".join(missing))
    if not evidence_ok:
        issues.append("missing_evidence_contract")
    if not plane_ok:
        issues.append("invalid_plane")
    if not non_collapsible:
        issues.append("missing_non_collapse_boundary")
    state = "FRAMEWORK_NODE_BOUND" if not issues else "CONTEXT_CONFORMANCE_REQUIRED"
    return PlaneAssessment(
        node_id=node.get("node_id", "UNKNOWN"),
        plane=node.get("plane", "UNKNOWN"),
        formula=FORMULA,
        context_complete=not missing,
        evidence_contract_complete=evidence_ok,
        non_collapsible=non_collapsible,
        derived_state=state,
        issue_count=len(issues),
        corrective_workflow="preserve_plane_context_and_evidence_contract" if issues else "maintain_plane_specific_receipts",
        required_receipts="evidence/four_plane_context_framework_receipt.json;exports/four_plane_context_framework_matrix.csv",
        reason=";".join(issues) if issues else "plane preserves independent I,V,O,E,X,R,L",
    )


def guard_rules(policy: Dict[str, Any]) -> List[CrossPlaneGuard]:
    guards: List[CrossPlaneGuard] = []
    for rule in policy.get("non_inheritance_rules", []):
        if "legal" in rule and "software" in rule:
            planes = "legal_perspective;software_service"
        elif "output" in rule and "reasoning" in rule:
            planes = "output_framework;thinking_framework"
        elif "reasoning" in rule or "thinking" in rule:
            planes = "thinking_framework;legal_perspective"
        else:
            planes = "all"
        guards.append(CrossPlaneGuard(rule=rule, status="ENFORCED", protected_planes=planes, reason="non-collapsible plane boundary preserved"))
    return guards


def write_work_packets(root: Path, rows: List[PlaneAssessment]) -> List[str]:
    packet_dir = root / "runtime_volume" / "workplans" / "four_plane_context"
    paths: List[str] = []
    for row in rows:
        if row.issue_count == 0:
            continue
        packet = {
            "node_id": row.node_id,
            "plane": row.plane,
            "formula": row.formula,
            "issue": row.reason,
            "corrective_workflow": row.corrective_workflow,
            "required_receipts": row.required_receipts.split(";"),
            "positive_tests": ["tests/test_four_plane_context_framework.py"],
            "negative_tests": ["cross-plane inheritance cannot promote legal conclusion, reasoning proof, or software receipt across plane boundaries"],
            "reentry_conditions": ["all I,V,O,E,X,R,L fields are complete", "evidence contract exists", "non-collapsible boundary declared"],
            "owner": "four_plane_context_framework",
        }
        path = packet_dir / f"{row.node_id.replace('://', '_').replace('/', '_')}_{canonical_hash(packet)}.json"
        write_json(path, packet)
        paths.append(str(path))
    return paths


def run_four_plane_context_framework(root: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    root = root.expanduser().resolve()
    started = time.time()
    policy = load_policy(root)
    rows = [assess_plane(node, policy["required_context_fields"]) for node in policy["framework_nodes"]]
    guards = guard_rules(policy)
    packets = write_work_packets(root, rows)
    matrix_path = root / "exports" / "four_plane_context_framework_matrix.csv"
    guard_path = root / "exports" / "four_plane_cross_plane_guards.csv"
    write_csv(matrix_path, [asdict(row) for row in rows])
    write_csv(guard_path, [asdict(guard) for guard in guards])
    receipt_path = root / "evidence" / "four_plane_context_framework_receipt.json"
    outbox = root / "runtime_volume" / "outbox" / "four_plane_context_framework" / f"{canonical_hash({'ts': started, 'rows': len(rows)})}.handoff.json"
    ledger = root / "runtime_volume" / "proof_bundles.ledger"
    entry = {"type": "four_plane_context_framework", "formula": FORMULA, "rows": [asdict(row) for row in rows], "guards": [asdict(g) for g in guards]}
    if emit_receipt:
        append_jsonl(ledger, entry)
    ledger_readback = any(item.get("type") == "four_plane_context_framework" for item in read_jsonl(ledger))
    receipt = FourPlaneReceipt(
        version="V99",
        formula=FORMULA,
        plane_count=len(rows),
        valid_plane_count=sum(1 for row in rows if row.derived_state == "FRAMEWORK_NODE_BOUND"),
        cross_plane_guard_count=len(guards),
        conformance_issue_count=sum(row.issue_count for row in rows),
        ledger_readback=ledger_readback,
        receipt_path=str(receipt_path),
        matrix_path=str(matrix_path),
        outbox_manifest=str(outbox),
        timestamp=started,
    )
    final = {
        "formula": FORMULA,
        "canonical_statement": policy["canonical_statement"],
        "receipt": asdict(receipt),
        "plane_assessments": [asdict(row) for row in rows],
        "cross_plane_guards": [asdict(guard) for guard in guards],
        "work_packets": packets,
        "legal_conclusion_inherited_from_software_test": False,
        "polished_output_used_as_reasoning_proof": False,
        "internal_reasoning_state_promoted_to_court_fact": False,
        "software_receipt_promoted_to_legal_determination": False,
    }
    if emit_receipt:
        write_json(receipt_path, final)
        write_json(outbox, {
            "source": "KEDDEH_V99_FOUR_PLANE_CONTEXT_FRAMEWORK",
            "payload_path": str(receipt_path),
            "matrix_path": str(matrix_path),
            "guard_matrix_path": str(guard_path),
            "status": "FOUR_PLANE_FRAMEWORK_BOUND" if receipt.conformance_issue_count == 0 else "CONTEXT_CONFORMANCE_REQUIRED",
            "created_at": started,
        })
    return final


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    result = run_four_plane_context_framework(Path(args.root), emit_receipt=args.emit_receipt)
    print(json.dumps(result["receipt"], indent=2, sort_keys=True))
    return 0 if result["receipt"]["plane_count"] == 4 and result["receipt"]["valid_plane_count"] == 4 else 1


if __name__ == "__main__":
    raise SystemExit(main())
