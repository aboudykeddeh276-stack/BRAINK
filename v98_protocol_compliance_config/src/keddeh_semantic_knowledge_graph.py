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

CANONICAL_STATEMENT = "The codebase is an executable encyclopedia of contextual state transitions."
EXPLAINABILITY_STATEMENT = "Every execution can explain itself linguistically, structurally and evidentially."


@dataclass(frozen=True)
class WordPage:
    word: str
    canonical_id: str
    part_of_speech: str
    source_definitions: Dict[str, str]
    invariants: List[str]
    allowed_variants: List[str]
    prohibited_conflations: List[str]
    backlinks: Dict[str, List[str]]


@dataclass(frozen=True)
class ExpressionPage:
    expression_id: str
    words: List[Dict[str, str]]
    source_meaning: Dict[str, str]
    composed_definition: str
    not_allowed: List[str]
    backlinks: Dict[str, List[str]]


@dataclass(frozen=True)
class SemanticBindingRow:
    service_id: str
    owner_plane: str
    semantic_word: str
    semantic_expression: str
    sector: str
    code_binding: str
    evidence_contract: str
    conformance_state: str
    reason: str


@dataclass(frozen=True)
class StoryTransition:
    transition_id: str
    prior_story: Dict[str, Any]
    expression: str
    execution_service: str
    handler: str
    evidence: Dict[str, Any]
    next_story: Dict[str, Any]
    timestamp: float


@dataclass(frozen=True)
class SemanticGraphReceipt:
    version: str
    word_count: int
    expression_count: int
    service_binding_count: int
    story_transition_count: int
    conformance_issue_count: int
    ledger_readback: bool
    receipt_path: str
    edge_matrix_path: str
    binding_matrix_path: str
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


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_").lower() or "item"


def load_policy(root: Path) -> Dict[str, Any]:
    return read_json(root / "config" / "semantic_knowledge_graph_policy.json")


def load_services(root: Path) -> List[Dict[str, Any]]:
    return read_json(root / "config" / "service_protocols.json")["services"]


def validate_word(raw: Dict[str, Any], required: List[str]) -> List[str]:
    errors: List[str] = []
    for field in required:
        if field not in raw or raw[field] in (None, "", [], {}):
            errors.append(f"word_missing:{raw.get('canonical_id', raw.get('word', 'UNKNOWN'))}:{field}")
    return errors


def validate_expression(raw: Dict[str, Any], word_ids: set[str], required: List[str]) -> List[str]:
    errors: List[str] = []
    for field in required:
        if field not in raw or raw[field] in (None, "", [], {}):
            errors.append(f"expression_missing:{raw.get('expression_id', 'UNKNOWN')}:{field}")
    for item in raw.get("words", []):
        if item.get("canonical") not in word_ids:
            errors.append(f"expression_unknown_word:{raw.get('expression_id')}:{item.get('canonical')}")
    return errors


def build_word_pages(policy: Dict[str, Any]) -> List[WordPage]:
    expression_links: Dict[str, List[str]] = {}
    for expression in policy["expressions"]:
        for word in expression["words"]:
            expression_links.setdefault(word["canonical"], []).append(expression["expression_id"])
    pages: List[WordPage] = []
    for raw in policy["canonical_words"]:
        pages.append(WordPage(
            word=raw["word"],
            canonical_id=raw["canonical_id"],
            part_of_speech=raw["part_of_speech"],
            source_definitions=dict(raw["source_definitions"]),
            invariants=list(raw["invariants"]),
            allowed_variants=list(raw["allowed_variants"]),
            prohibited_conflations=list(raw["prohibited_conflations"]),
            backlinks={"expressions": expression_links.get(raw["canonical_id"], []), "services": [], "code_bindings": []},
        ))
    return pages


def build_expression_pages(policy: Dict[str, Any]) -> List[ExpressionPage]:
    return [
        ExpressionPage(
            expression_id=raw["expression_id"],
            words=list(raw["words"]),
            source_meaning=dict(raw["source_meaning"]),
            composed_definition=raw["composed_definition"],
            not_allowed=list(raw["not_allowed"]),
            backlinks={"services": [], "code_bindings": [], "story_transitions": []},
        )
        for raw in policy["expressions"]
    ]


def choose_binding(service: Dict[str, Any]) -> tuple[str, str, str]:
    service_id = service["service_id"]
    text = f"{service_id} {service.get('boundary', '')} {service.get('owner_plane', '')}".lower()
    if "health" in text:
        return "word://health", "expression://observe-node-health", "sector://mesh-infrastructure"
    if "agent" in text:
        return "word://agent", "expression://instantiate-governed-agent-worker", "sector://agent-operations"
    if "failure" in text or "recover" in text or "deferred" in text:
        return "word://recover", "expression://reconcile-deferred-work-after-dependency-recovery", "sector://runtime-continuity"
    if "cloud" in text or "deploy" in text or "package" in text or "application" in text:
        return "word://deploy", "expression://run-kapp-on-eligible-node", "sector://application-deployment"
    if "verify" in text or "schema" in text or "acceptance" in text or "receipt" in text:
        return "word://verify", "expression://verify-manifest-before-node-execution", "sector://evidence-governance"
    return "word://service", "expression://verify-manifest-before-node-execution", "sector://service-governance"


def service_bindings(services: List[Dict[str, Any]]) -> List[SemanticBindingRow]:
    rows: List[SemanticBindingRow] = []
    for service in services:
        word, expression, sector = choose_binding(service)
        stages = service.get("stages", {})
        has_full_contract = all(stages.get(stage) is True for stage in ["recognize", "execute", "verify", "write_receipt", "readback", "handoff"])
        has_boundary = bool(service.get("boundary"))
        state = "SEMANTICALLY_BOUND" if has_full_contract and has_boundary else "SEMANTIC_CONFORMANCE_REQUIRED"
        reason = "service contract and boundary available" if state == "SEMANTICALLY_BOUND" else "missing service contract stage or boundary"
        rows.append(SemanticBindingRow(
            service_id=service["service_id"],
            owner_plane=service.get("owner_plane", "unknown"),
            semantic_word=word,
            semantic_expression=expression,
            sector=sector,
            code_binding=f"config/service_protocols.json::{service['service_id']}",
            evidence_contract="recognize→execute→verify→write_receipt→readback→handoff",
            conformance_state=state,
            reason=reason,
        ))
    return rows


def update_backlinks(words: List[WordPage], expressions: List[ExpressionPage], bindings: List[SemanticBindingRow]) -> tuple[List[WordPage], List[ExpressionPage]]:
    service_by_word: Dict[str, List[str]] = {}
    binding_by_word: Dict[str, List[str]] = {}
    service_by_expr: Dict[str, List[str]] = {}
    binding_by_expr: Dict[str, List[str]] = {}
    for row in bindings:
        service_by_word.setdefault(row.semantic_word, []).append(f"service://{row.service_id}")
        binding_by_word.setdefault(row.semantic_word, []).append(row.code_binding)
        service_by_expr.setdefault(row.semantic_expression, []).append(f"service://{row.service_id}")
        binding_by_expr.setdefault(row.semantic_expression, []).append(row.code_binding)
    next_words: List[WordPage] = []
    for word in words:
        backlinks = dict(word.backlinks)
        backlinks["services"] = sorted(set(backlinks.get("services", []) + service_by_word.get(word.canonical_id, [])))
        backlinks["code_bindings"] = sorted(set(backlinks.get("code_bindings", []) + binding_by_word.get(word.canonical_id, [])))
        next_words.append(WordPage(**{**asdict(word), "backlinks": backlinks}))
    next_expressions: List[ExpressionPage] = []
    for expression in expressions:
        backlinks = dict(expression.backlinks)
        backlinks["services"] = sorted(set(backlinks.get("services", []) + service_by_expr.get(expression.expression_id, [])))
        backlinks["code_bindings"] = sorted(set(backlinks.get("code_bindings", []) + binding_by_expr.get(expression.expression_id, [])))
        next_expressions.append(ExpressionPage(**{**asdict(expression), "backlinks": backlinks}))
    return next_words, next_expressions


def story_transitions(bindings: List[SemanticBindingRow]) -> List[StoryTransition]:
    transitions: List[StoryTransition] = []
    for row in bindings:
        if row.conformance_state != "SEMANTICALLY_BOUND":
            continue
        transition_seed = {"service": row.service_id, "expression": row.semantic_expression, "ts": time.time()}
        transitions.append(StoryTransition(
            transition_id=f"transition://semantic/{row.service_id}/{canonical_hash(transition_seed)[:12]}",
            prior_story={"service_state": "declared", "meaning_state": "unlinked_or_partial"},
            expression=row.semantic_expression,
            execution_service=f"service://{row.service_id}",
            handler=row.code_binding,
            evidence={"receipt_class": "semantic_graph_receipt", "observer": "semantic_knowledge_graph", "evidence_required": "service contract and linked expression"},
            next_story={"service_state": "addressable", "meaning_state": "linked"},
            timestamp=time.time(),
        ))
    return transitions


def write_graph(root: Path, words: List[WordPage], expressions: List[ExpressionPage], bindings: List[SemanticBindingRow], transitions: List[StoryTransition]) -> Dict[str, str]:
    graph_root = root / "runtime_volume" / "semantic_graph"
    word_dir = graph_root / "lexicon" / "words"
    expr_dir = graph_root / "expressions"
    service_dir = graph_root / "services"
    story_dir = graph_root / "story"
    for word in words:
        write_json(word_dir / f"{safe_name(word.canonical_id)}.json", asdict(word))
    for expression in expressions:
        write_json(expr_dir / f"{safe_name(expression.expression_id)}.json", asdict(expression))
    for binding in bindings:
        write_json(service_dir / f"{safe_name(binding.service_id)}.json", asdict(binding))
    current_context = {
        "canonical_statement": CANONICAL_STATEMENT,
        "word_count": len(words),
        "expression_count": len(expressions),
        "service_binding_count": len(bindings),
        "last_transition_count": len(transitions),
        "updated_at": time.time(),
    }
    write_json(graph_root / "current_context.json", current_context)
    ledger = graph_root / "transition_ledger.jsonl"
    for transition in transitions:
        append_jsonl(ledger, {"type": "semantic_story_transition", "transition": asdict(transition)})
    edge_rows: List[Dict[str, str]] = []
    for word in words:
        for expr in word.backlinks.get("expressions", []):
            edge_rows.append({"from": word.canonical_id, "relation": "used_in_expression", "to": expr})
        for service in word.backlinks.get("services", []):
            edge_rows.append({"from": word.canonical_id, "relation": "backlinked_service", "to": service})
    for expression in expressions:
        for service in expression.backlinks.get("services", []):
            edge_rows.append({"from": expression.expression_id, "relation": "bound_to_service", "to": service})
    edge_matrix = root / "exports" / "semantic_knowledge_graph_edges.csv"
    binding_matrix = root / "exports" / "semantic_knowledge_graph_bindings.csv"
    write_csv(edge_matrix, edge_rows)
    write_csv(binding_matrix, [asdict(row) for row in bindings])
    return {"edge_matrix": str(edge_matrix), "binding_matrix": str(binding_matrix), "ledger": str(ledger), "story_dir": str(story_dir)}


def conformance_issues(policy: Dict[str, Any], words: List[WordPage], expressions: List[ExpressionPage], bindings: List[SemanticBindingRow]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    word_ids = {word.canonical_id for word in words}
    for raw in policy["canonical_words"]:
        for error in validate_word(raw, policy["required_word_fields"]):
            issues.append({"issue": error, "corrective_action": "complete canonical word page"})
    for raw in policy["expressions"]:
        for error in validate_expression(raw, word_ids, policy["required_expression_fields"]):
            issues.append({"issue": error, "corrective_action": "repair expression source word links"})
    for row in bindings:
        if row.conformance_state != "SEMANTICALLY_BOUND":
            issues.append({"issue": f"binding_incomplete:{row.service_id}", "corrective_action": "add service boundary and full service contract"})
    return issues


def run_semantic_knowledge_graph(root: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    root = root.expanduser().resolve()
    started = time.time()
    policy = load_policy(root)
    services = load_services(root)
    words = build_word_pages(policy)
    expressions = build_expression_pages(policy)
    bindings = service_bindings(services)
    words, expressions = update_backlinks(words, expressions, bindings)
    transitions = story_transitions(bindings)
    paths = write_graph(root, words, expressions, bindings, transitions)
    issues = conformance_issues(policy, words, expressions, bindings)
    receipt_path = root / "evidence" / "semantic_knowledge_graph_receipt.json"
    outbox = root / "runtime_volume" / "outbox" / "semantic_knowledge_graph" / f"{canonical_hash({'ts': started, 'bindings': len(bindings)})}.handoff.json"
    ledger_readback = any(item.get("type") == "semantic_story_transition" for item in read_jsonl(Path(paths["ledger"])))
    receipt = SemanticGraphReceipt(
        version="V99",
        word_count=len(words),
        expression_count=len(expressions),
        service_binding_count=len(bindings),
        story_transition_count=len(transitions),
        conformance_issue_count=len(issues),
        ledger_readback=ledger_readback,
        receipt_path=str(receipt_path),
        edge_matrix_path=paths["edge_matrix"],
        binding_matrix_path=paths["binding_matrix"],
        outbox_manifest=str(outbox),
        timestamp=started,
    )
    final = {
        "canonical_statement": CANONICAL_STATEMENT,
        "explainability_statement": EXPLAINABILITY_STATEMENT,
        "receipt": asdict(receipt),
        "issues": issues,
        "words": [asdict(word) for word in words],
        "expressions": [asdict(expression) for expression in expressions],
        "bindings": [asdict(row) for row in bindings],
        "transitions": [asdict(transition) for transition in transitions],
        "single_file_claim": False,
        "isolated_file_model_rejected": True,
        "execution_explainability_enabled": True,
    }
    if emit_receipt:
        write_json(receipt_path, final)
        write_json(outbox, {
            "source": "KEDDEH_V99_SEMANTIC_KNOWLEDGE_GRAPH",
            "payload_path": str(receipt_path),
            "edge_matrix": paths["edge_matrix"],
            "binding_matrix": paths["binding_matrix"],
            "status": "SEMANTIC_GRAPH_READY" if not issues else "SEMANTIC_CONFORMANCE_REQUIRED",
            "created_at": started,
        })
    return final


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    result = run_semantic_knowledge_graph(Path(args.root), emit_receipt=args.emit_receipt)
    print(json.dumps(result["receipt"], indent=2, sort_keys=True))
    return 0 if result["receipt"]["word_count"] > 0 and result["receipt"]["expression_count"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
