#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from hardening import append_jsonl_fsync, atomic_write_text, canonical_json_bytes, sha256_bytes

BASE = Path(__file__).resolve().parents[2]
RUNTIME = BASE / "runtime"
STATE_ROOT = RUNTIME / "illlm"
GRAPH_PATH = STATE_ROOT / "executable-semantic-graph.json"
PROOF_PATH = BASE / "reports" / "kex-wbos" / "illlm-executable-graph-proof.jsonl"
STRATA_PATH = RUNTIME / "ILLLM_PRIMITIVE_STRATIFICATION_R1.json"
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{1,}")


@dataclass(frozen=True)
class ExecutableObject:
    identity: str
    object_class: str
    semantic_terms: tuple[str, ...]
    mathematical_state: dict[str, Any]
    knowledge_edges: tuple[str, ...]
    execution_edges: tuple[str, ...]
    state_edges: tuple[str, ...]
    proof_edges: tuple[str, ...]
    source: str | None
    execution_state: str


def _tokens(value: Any) -> tuple[str, ...]:
    return tuple(sorted({m.group(0).casefold() for m in TOKEN_RE.finditer(str(value))}))


def _load_strata() -> dict[str, Any]:
    if not STRATA_PATH.exists():
        return {"strata": []}
    return json.loads(STRATA_PATH.read_text(encoding="utf-8"))


def _classify(identity: str, payload: dict[str, Any]) -> str:
    low = f"{identity} {payload}".lower()
    for label, needles in (
        ("RUNTIME_SERVICE", ("runtime://", "service://", "route", "launch", "dispatch")),
        ("SOURCE_CODE", (".py", ".swift", ".js", ".ts", "function", "class", "module")),
        ("PROFESSIONAL_PRACTICE", ("standard", "procedure", "regulation", "benchmark", "quality")),
        ("SECTOR_ONTOLOGY", ("sector", "domain object", "workflow")),
        ("MATHEMATICS", ("formula", "algebra", "graph", "recurrence", "ratio")),
        ("ELEMENTS", ("hydrogen", "lithium", "silicon", "oganesson", "element")),
        ("NUMBERS", ("number", "integer", "ordinal", "cardinal", "ratio")),
    ):
        if any(n in low for n in needles):
            return label
    return "GENERAL"


def _math_state(identity: str, payload: dict[str, Any], terms: tuple[str, ...]) -> dict[str, Any]:
    raw = canonical_json_bytes({"identity": identity, "payload": payload})
    digest = sha256_bytes(raw)
    return {
        "contentHash": digest,
        "termCardinality": len(terms),
        "byteLength": len(raw),
        "identityScalar": int(digest[:16], 16),
        "normalisedIdentity": int(digest[:16], 16) / float(0xFFFFFFFFFFFFFFFF),
    }


def build_executable_graph(objects: list[dict[str, Any]]) -> dict[str, Any]:
    strata = _load_strata()
    nodes: dict[str, ExecutableObject] = {}
    term_index: dict[str, set[str]] = defaultdict(set)
    knowledge_edges: list[dict[str, str]] = []
    execution_edges: list[dict[str, str]] = []
    state_edges: list[dict[str, str]] = []
    proof_edges: list[dict[str, str]] = []

    for raw in objects:
        identity = str(raw.get("identity") or raw.get("id") or raw.get("uri") or raw.get("source") or "").strip()
        if not identity:
            continue
        terms = _tokens(raw)
        node = ExecutableObject(
            identity=identity,
            object_class=str(raw.get("objectClass") or _classify(identity, raw)),
            semantic_terms=terms,
            mathematical_state=_math_state(identity, raw, terms),
            knowledge_edges=tuple(sorted(set(map(str, raw.get("knowledgeEdges", []))))),
            execution_edges=tuple(sorted(set(map(str, raw.get("executionEdges", []))))),
            state_edges=tuple(sorted(set(map(str, raw.get("stateEdges", []))))),
            proof_edges=tuple(sorted(set(map(str, raw.get("proofEdges", []))))),
            source=str(raw.get("source")) if raw.get("source") else None,
            execution_state=str(raw.get("executionState") or "REGISTERED"),
        )
        nodes[identity] = node
        for term in terms:
            term_index[term].add(identity)

    for node in nodes.values():
        for target in node.knowledge_edges:
            knowledge_edges.append({"source": node.identity, "relation": "KNOWS", "target": target})
        for target in node.execution_edges:
            execution_edges.append({"source": node.identity, "relation": "EXECUTES_VIA", "target": target})
        for target in node.state_edges:
            state_edges.append({"source": node.identity, "relation": "TRANSITIONS_TO", "target": target})
        for target in node.proof_edges:
            proof_edges.append({"source": node.identity, "relation": "PROVES_VIA", "target": target})

    graph = {
        "schema": "kex.illlm.executable-semantic-graph.v1",
        "model": "CONTEXTUAL_SEMANTIC_MATHEMATICAL_EXECUTION_GRAPH",
        "strata": strata.get("strata", []),
        "nodeCount": len(nodes),
        "nodes": [asdict(nodes[key]) for key in sorted(nodes)],
        "termIndex": {term: sorted(ids) for term, ids in sorted(term_index.items())},
        "edges": {
            "knowledge": knowledge_edges,
            "execution": execution_edges,
            "state": state_edges,
            "proof": proof_edges,
        },
        "semantics": {
            "knowledgeAndExecutionCoResidence": "A node may expose contextual knowledge relations and executable routes in the same identity frame.",
            "mathematicalIdentity": "Each node carries deterministic content-derived state descriptors used for equality, change and routing evidence.",
            "contextPathway": "Traversal follows typed relations from current context to relevant semantic objects and, where bound, their executable/state/proof routes.",
            "claimBoundary": "An execution edge is a machine-resolvable route declaration. It does not prove the target actuator executed until a runtime receipt exists."
        },
        "createdAt": time.time(),
    }
    graph["graphHash"] = sha256_bytes(canonical_json_bytes(graph))
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    atomic_write_text(GRAPH_PATH, json.dumps(graph, indent=2, sort_keys=True) + "\n")
    append_jsonl_fsync(PROOF_PATH, {"ts": time.time(), "event": "ILLLM_EXECUTABLE_GRAPH_BUILT", "graphHash": graph["graphHash"], "nodeCount": graph["nodeCount"]})
    return graph


def contextual_machine_path(context: Any, graph: dict[str, Any], *, limit: int = 16) -> list[dict[str, Any]]:
    query_terms = set(_tokens(context))
    if not query_terms:
        return []
    candidates: set[str] = set()
    term_index = graph.get("termIndex", {})
    for term in query_terms:
        candidates.update(term_index.get(term, []))

    nodes = {node["identity"]: node for node in graph.get("nodes", [])}
    ranked: list[dict[str, Any]] = []
    for identity in candidates:
        node = nodes[identity]
        node_terms = set(node.get("semantic_terms", []))
        intersection = query_terms & node_terms
        union = query_terms | node_terms
        semantic_score = len(intersection) / max(1, len(union))
        exec_bonus = 0.15 if node.get("execution_edges") else 0.0
        proof_bonus = 0.05 if node.get("proof_edges") else 0.0
        score = semantic_score + exec_bonus + proof_bonus
        ranked.append({
            "identity": identity,
            "objectClass": node.get("object_class"),
            "score": score,
            "matchedTerms": sorted(intersection),
            "mathematicalState": node.get("mathematical_state"),
            "knowledgeEdges": node.get("knowledge_edges", []),
            "executionEdges": node.get("execution_edges", []),
            "stateEdges": node.get("state_edges", []),
            "proofEdges": node.get("proof_edges", []),
            "executionState": node.get("execution_state"),
        })
    ranked.sort(key=lambda item: (-item["score"], item["identity"]))
    return ranked[:max(1, limit)]


def resolve_executable_context(context: Any, graph: dict[str, Any], *, limit: int = 16) -> dict[str, Any]:
    paths = contextual_machine_path(context, graph, limit=limit)
    return {
        "context": context,
        "contextHash": sha256_bytes(canonical_json_bytes(context)),
        "paths": paths,
        "machineExecutableCandidates": [p for p in paths if p.get("executionEdges")],
        "proofBoundCandidates": [p for p in paths if p.get("proofEdges")],
        "resolutionModel": "CONTEXT_TO_SEMANTIC_AND_EXECUTABLE_PATHS_IN_ONE_FRAME",
    }
