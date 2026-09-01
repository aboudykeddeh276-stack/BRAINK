#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from illlm_recursive_runtime import ILLLMNode, RecursiveILLLMRuntime, TraversalEdge, _tokens, seed_primitive_ladder

BASE = Path(__file__).resolve().parents[2]
CARRIER_PATH = BASE / "runtime" / "ILLLM_CROSS_REPOSITORY_CARRIERS_R1.json"


def _safe_identity(raw: str) -> str:
    value = raw.strip()
    if value.startswith("illlm://"):
        value = "il-llm://" + value[len("illlm://"):]
    return value


def _ensure_container(runtime: RecursiveILLLMRuntime, identity: str, role: str = "CONTAINER") -> None:
    identity = _safe_identity(identity)
    if identity in runtime.nodes:
        return
    parent = runtime.META_ROOT
    if identity.startswith("il-llm://braink/"):
        parent = "il-llm://braink" if "il-llm://braink" in runtime.nodes else runtime.META_ROOT
    runtime.register_node(ILLLMNode(
        identity=identity,
        role=role,
        parent=parent,
        semantic_terms=_tokens([identity, role]),
        observed_state="REGISTERED",
    ))


def hydrate_recursive_runtime(topology: dict[str, Any]) -> RecursiveILLLMRuntime:
    runtime = RecursiveILLLMRuntime()
    seed_primitive_ladder(runtime)
    _ensure_container(runtime, "il-llm://braink", "BRAINK_ROOT")

    pending = []
    for record in topology.get("nodes", []):
        identity = _safe_identity(str(record.get("identity", "")))
        if not identity or identity == runtime.META_ROOT:
            continue
        parent = _safe_identity(str(record.get("parent") or "il-llm://braink"))
        pending.append((identity, parent, record))

    # Resolve parents before children without assuming the input is topologically sorted.
    remaining = pending
    while remaining:
        next_round = []
        progressed = False
        for identity, parent, record in remaining:
            if identity in runtime.nodes:
                progressed = True
                continue
            if parent not in runtime.nodes:
                next_round.append((identity, parent, record))
                continue
            terms = [identity, str(record.get("role", "GENERAL")), *record.get("evidence", [])]
            runtime.register_node(ILLLMNode(
                identity=identity,
                role=str(record.get("role") or "GENERAL"),
                parent=parent,
                semantic_terms=_tokens(terms),
                mathematical_state={"logicalDepth": len(runtime.ancestry(parent)), "source": "higher-order-topology"},
                execution_routes=tuple(str(x) for x in record.get("entry_routes", []) if x),
                proof_refs=tuple(str(x) for x in record.get("evidence", []) if x),
                continuation=str(record.get("continuation")) if record.get("continuation") else None,
                observed_state=str(record.get("execution_state") or "REGISTERED"),
                metadata={"frameClass": record.get("frame_class")},
            ))
            progressed = True
        if not progressed:
            # Preserve unresolved lineage without inventing ancestry.
            for identity, parent, record in next_round:
                _ensure_container(runtime, parent)
            remaining = next_round
        else:
            remaining = next_round

    for edge in topology.get("edges", []):
        source = _safe_identity(str(edge.get("source", "")))
        target = _safe_identity(str(edge.get("target", "")))
        if source not in runtime.nodes or target not in runtime.nodes:
            continue
        relation = str(edge.get("relation") or "RELATED")
        # CONTAINS is already represented by parent/children; keep traversal edges
        # for re-entry/continuation and other semantic relations.
        if relation == "CONTAINS":
            continue
        runtime.add_edge(TraversalEdge(source, target, relation, cost=0.25 if relation == "REENTERS" else 1.0))

    ingest_cross_repository_carriers(runtime)
    return runtime


def ingest_cross_repository_carriers(runtime: RecursiveILLLMRuntime) -> None:
    if not CARRIER_PATH.exists():
        return
    payload = json.loads(CARRIER_PATH.read_text(encoding="utf-8"))
    parent = "il-llm://braink/infrastructure"
    if parent not in runtime.nodes:
        _ensure_container(runtime, parent, "INFRASTRUCTURE")
    for carrier in payload.get("carriers", []):
        repo = str(carrier.get("repository", ""))
        if not repo:
            continue
        slug = repo.lower().replace("/", "/repository/")
        identity = f"il-llm://carrier/{slug}"
        terms = [repo, str(carrier.get("role", "CARRIER")), *carrier.get("observed", []), *carrier.get("evidence", [])]
        runtime.register_node(ILLLMNode(
            identity=identity,
            role="REPOSITORY_CARRIER",
            parent=parent,
            semantic_terms=_tokens(terms),
            mathematical_state={"observedCapabilityCount": len(carrier.get("observed", []))},
            proof_refs=tuple(str(x) for x in carrier.get("evidence", [])),
            observed_state=str(carrier.get("state") or "DISCOVERED"),
            metadata={"repository": repo, "carrierRole": carrier.get("role")},
        ))
        runtime.add_edge(TraversalEdge(parent, identity, "CARRIED_BY_REPOSITORY", cost=0.5))
        runtime.add_edge(TraversalEdge(identity, parent, "REENTER_INFRASTRUCTURE_CONTEXT", cost=0.5))


def apply_delta(runtime: RecursiveILLLMRuntime, delta: dict[str, Any]) -> dict[str, Any]:
    before = runtime.graph_hash()
    applied = 0
    rejected: list[dict[str, Any]] = []
    for item in delta.get("upsertNodes", []):
        try:
            identity = _safe_identity(str(item["identity"]))
            parent = _safe_identity(str(item.get("parent") or runtime.META_ROOT))
            if parent not in runtime.nodes:
                raise KeyError(f"parent not resident: {parent}")
            runtime.register_node(ILLLMNode(
                identity=identity,
                role=str(item.get("role") or "GENERAL"),
                parent=parent,
                semantic_terms=_tokens(item.get("semanticTerms", [identity])),
                mathematical_state=dict(item.get("mathematicalState", {})),
                execution_routes=tuple(str(x) for x in item.get("executionRoutes", [])),
                proof_refs=tuple(str(x) for x in item.get("proofRefs", [])),
                continuation=item.get("continuation"),
                carrier=item.get("carrier"),
                observed_state=str(item.get("observedState") or "REGISTERED"),
                metadata=dict(item.get("metadata", {})),
            ))
            applied += 1
        except Exception as exc:
            rejected.append({"kind": "node", "identity": item.get("identity"), "error": type(exc).__name__, "message": str(exc)})
    for item in delta.get("addEdges", []):
        try:
            runtime.add_edge(TraversalEdge(
                source=_safe_identity(str(item["source"])),
                target=_safe_identity(str(item["target"])),
                relation=str(item.get("relation") or "RELATED"),
                cost=float(item.get("cost", 1.0)),
                executable=bool(item.get("executable", False)),
                execution_route=item.get("executionRoute"),
                guard=item.get("guard"),
            ))
            applied += 1
        except Exception as exc:
            rejected.append({"kind": "edge", "source": item.get("source"), "target": item.get("target"), "error": type(exc).__name__, "message": str(exc)})
    after = runtime.graph_hash()
    return {
        "status": "APPLIED" if not rejected else ("PARTIAL" if applied else "REJECTED"),
        "applied": applied,
        "rejected": rejected,
        "beforeGraphHash": before,
        "afterGraphHash": after,
        "changed": before != after,
        "generation": runtime.generation,
        "claimBoundary": "Delta application mutates the resident routing graph only; external execution remains separately receipted.",
    }
