#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

_TOKEN = re.compile(r"[A-Za-z0-9_:\-./]+")


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canon(value)).hexdigest()


def _tokens(values: Iterable[str]) -> frozenset[str]:
    found: set[str] = set()
    for value in values:
        for token in _TOKEN.findall(str(value).lower()):
            if token:
                found.add(token)
    return frozenset(found)


@dataclass(slots=True)
class ILLLMNode:
    identity: str
    role: str
    parent: str | None = None
    semantic_terms: frozenset[str] = field(default_factory=frozenset)
    mathematical_state: dict[str, Any] = field(default_factory=dict)
    execution_routes: tuple[str, ...] = ()
    proof_refs: tuple[str, ...] = ()
    continuation: str | None = None
    carrier: str | None = None
    observed_state: str = "DEFINED"
    metadata: dict[str, Any] = field(default_factory=dict)

    def canonical(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "role": self.role,
            "parent": self.parent,
            "semanticTerms": sorted(self.semantic_terms),
            "mathematicalState": self.mathematical_state,
            "executionRoutes": list(self.execution_routes),
            "proofRefs": list(self.proof_refs),
            "continuation": self.continuation,
            "carrier": self.carrier,
            "observedState": self.observed_state,
            "metadata": self.metadata,
        }


@dataclass(slots=True, frozen=True)
class TraversalEdge:
    source: str
    target: str
    relation: str
    cost: float = 1.0
    executable: bool = False
    execution_route: str | None = None
    guard: str | None = None

    def canonical(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "cost": self.cost,
            "executable": self.executable,
            "executionRoute": self.execution_route,
            "guard": self.guard,
        }


@dataclass(slots=True)
class ContextFrame:
    frame_id: str
    entered_from: str | None
    current: str
    ancestry: tuple[str, ...]
    query_tokens: frozenset[str]
    created_at: float
    logical_time: int = 1


class RecursiveILLLMRuntime:
    """Higher-order IL-LLM traversal runtime.

    Containment is acyclic and establishes ancestry/re-entry. Traversal edges are
    independently allowed to cycle. The runtime keeps semantic, role and execution
    indices resident so normal contextual access does not require whole-estate scans.
    """

    META_ROOT = "il-llm://meta/il-llm-of-il-llms"

    def __init__(self) -> None:
        self.nodes: dict[str, ILLLMNode] = {}
        self.children: dict[str, set[str]] = defaultdict(set)
        self.edges_out: dict[str, list[TraversalEdge]] = defaultdict(list)
        self.role_index: dict[str, set[str]] = defaultdict(set)
        self.term_index: dict[str, set[str]] = defaultdict(set)
        self.execution_index: dict[str, set[str]] = defaultdict(set)
        self.frames: dict[str, ContextFrame] = {}
        self._generation = 0
        self._graph_hash = ""
        self._dirty = True
        self.register_node(
            ILLLMNode(
                identity=self.META_ROOT,
                role="META_RUNTIME",
                semantic_terms=_tokens(["IL-LLM", "recursive traversal", "context", "re-entry", "continuation"]),
                mathematical_state={"rank": 1, "class": "higher_order_root"},
                observed_state="RESIDENT",
            )
        )

    @property
    def generation(self) -> int:
        return self._generation

    def _assert_identity(self, identity: str) -> None:
        if not identity.startswith("il-llm://"):
            raise ValueError(f"invalid IL-LLM identity: {identity}")

    def _is_descendant(self, candidate: str, ancestor: str) -> bool:
        current = self.nodes.get(candidate)
        seen: set[str] = set()
        while current and current.parent:
            if current.parent == ancestor:
                return True
            if current.parent in seen:
                raise RuntimeError("containment cycle detected")
            seen.add(current.parent)
            current = self.nodes.get(current.parent)
        return False

    def register_node(self, node: ILLLMNode) -> None:
        self._assert_identity(node.identity)
        if node.parent:
            self._assert_identity(node.parent)
            if node.parent == node.identity or self._is_descendant(node.parent, node.identity):
                raise ValueError("IL-LLM containment must remain acyclic")
            if node.parent not in self.nodes:
                raise KeyError(f"parent not resident: {node.parent}")
        old = self.nodes.get(node.identity)
        if old:
            self._drop_indices(old)
            if old.parent:
                self.children[old.parent].discard(old.identity)
        self.nodes[node.identity] = node
        if node.parent:
            self.children[node.parent].add(node.identity)
        self._add_indices(node)
        self._touch()

    def _add_indices(self, node: ILLLMNode) -> None:
        self.role_index[node.role.upper()].add(node.identity)
        for term in node.semantic_terms:
            self.term_index[term].add(node.identity)
        for route in node.execution_routes:
            self.execution_index[route].add(node.identity)

    def _drop_indices(self, node: ILLLMNode) -> None:
        self.role_index[node.role.upper()].discard(node.identity)
        for term in node.semantic_terms:
            self.term_index[term].discard(node.identity)
        for route in node.execution_routes:
            self.execution_index[route].discard(node.identity)

    def add_edge(self, edge: TraversalEdge) -> None:
        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise KeyError("traversal endpoints must be resident")
        if edge.cost < 0 or not math.isfinite(edge.cost):
            raise ValueError("edge cost must be finite and non-negative")
        if edge.executable and not edge.execution_route:
            raise ValueError("executable traversal requires execution_route")
        if edge not in self.edges_out[edge.source]:
            self.edges_out[edge.source].append(edge)
            self._touch()

    def _touch(self) -> None:
        self._generation += 1
        self._dirty = True

    def ancestry(self, identity: str) -> tuple[str, ...]:
        if identity not in self.nodes:
            raise KeyError(identity)
        out: list[str] = []
        current: str | None = identity
        seen: set[str] = set()
        while current:
            if current in seen:
                raise RuntimeError("containment cycle detected")
            seen.add(current)
            out.append(current)
            current = self.nodes[current].parent
        return tuple(reversed(out))

    def descendants(self, identity: str, *, max_depth: int | None = None) -> set[str]:
        if identity not in self.nodes:
            raise KeyError(identity)
        found: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(identity, 0)])
        while queue:
            current, depth = queue.popleft()
            if max_depth is not None and depth >= max_depth:
                continue
            for child in self.children.get(current, ()):
                if child not in found:
                    found.add(child)
                    queue.append((child, depth + 1))
        return found

    def enter(self, identity: str, *, query: str = "", entered_from: str | None = None) -> ContextFrame:
        if identity not in self.nodes:
            raise KeyError(identity)
        frame_id = f"continuation://illlm/frame/{self._generation}/{len(self.frames)+1}"
        frame = ContextFrame(
            frame_id=frame_id,
            entered_from=entered_from,
            current=identity,
            ancestry=self.ancestry(identity),
            query_tokens=_tokens([query]),
            created_at=time.time(),
        )
        self.frames[frame_id] = frame
        return frame

    def reenter_parent(self, frame_id: str) -> ContextFrame:
        frame = self.frames[frame_id]
        node = self.nodes[frame.current]
        if not node.parent:
            return frame
        frame.current = node.parent
        frame.ancestry = self.ancestry(node.parent)
        frame.logical_time += 1
        return frame

    def contextual_candidates(
        self,
        query: str,
        *,
        role: str | None = None,
        within: str | None = None,
        require_execution: bool = False,
        limit: int = 32,
    ) -> list[dict[str, Any]]:
        q = _tokens([query])
        candidate_ids: set[str] = set()
        for token in q:
            candidate_ids.update(self.term_index.get(token, ()))
        if role:
            role_ids = self.role_index.get(role.upper(), set())
            candidate_ids = candidate_ids & role_ids if candidate_ids else set(role_ids)
        if within:
            permitted = self.descendants(within) | {within}
            candidate_ids &= permitted
        if require_execution:
            candidate_ids = {i for i in candidate_ids if self.nodes[i].execution_routes}
        scored: list[tuple[float, str, dict[str, Any]]] = []
        for identity in candidate_ids:
            node = self.nodes[identity]
            overlap = len(q & node.semantic_terms)
            exact_role = 1 if role and node.role.upper() == role.upper() else 0
            depth = len(self.ancestry(identity))
            execution_bonus = 1 if node.execution_routes else 0
            score = overlap * 8.0 + exact_role * 4.0 + execution_bonus * 2.0 + min(depth, 16) * 0.05
            scored.append((score, identity, {
                "identity": identity,
                "role": node.role,
                "score": score,
                "matchedTerms": sorted(q & node.semantic_terms),
                "ancestry": list(self.ancestry(identity)),
                "executionRoutes": list(node.execution_routes),
                "observedState": node.observed_state,
            }))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in scored[:limit]]

    def shortest_traversal(self, source: str, target: str, *, executable_only: bool = False) -> dict[str, Any]:
        if source not in self.nodes or target not in self.nodes:
            raise KeyError("source/target not resident")
        import heapq
        queue: list[tuple[float, str]] = [(0.0, source)]
        distance = {source: 0.0}
        previous: dict[str, tuple[str, TraversalEdge]] = {}
        while queue:
            cost, current = heapq.heappop(queue)
            if cost != distance.get(current):
                continue
            if current == target:
                break
            for edge in self.edges_out.get(current, ()):
                if executable_only and not edge.executable:
                    continue
                new_cost = cost + edge.cost
                if new_cost < distance.get(edge.target, float("inf")):
                    distance[edge.target] = new_cost
                    previous[edge.target] = (current, edge)
                    heapq.heappush(queue, (new_cost, edge.target))
        if target not in distance:
            return {"found": False, "source": source, "target": target}
        path_nodes = [target]
        path_edges: list[TraversalEdge] = []
        cursor = target
        while cursor != source:
            prior, edge = previous[cursor]
            path_edges.append(edge)
            path_nodes.append(prior)
            cursor = prior
        path_nodes.reverse()
        path_edges.reverse()
        return {
            "found": True,
            "source": source,
            "target": target,
            "cost": distance[target],
            "nodes": path_nodes,
            "edges": [edge.canonical() for edge in path_edges],
            "executionRoutes": [edge.execution_route for edge in path_edges if edge.execution_route],
        }

    def compile_context_plan(
        self,
        query: str,
        *,
        role: str | None = None,
        within: str | None = None,
        require_execution: bool = False,
    ) -> dict[str, Any]:
        candidates = self.contextual_candidates(
            query,
            role=role,
            within=within,
            require_execution=require_execution,
            limit=8,
        )
        selected = candidates[0] if candidates else None
        plan = {
            "query": query,
            "role": role,
            "within": within,
            "requireExecution": require_execution,
            "selected": selected,
            "alternates": candidates[1:],
            "runtimeGeneration": self._generation,
            "graphHash": self.graph_hash(),
            "claimBoundary": "A compiled contextual plan proves resident routing state, not execution of any selected actuator.",
        }
        plan["planHash"] = _sha(plan)
        return plan

    def graph_hash(self) -> str:
        if self._dirty:
            payload = {
                "nodes": [self.nodes[k].canonical() for k in sorted(self.nodes)],
                "containment": {k: sorted(v) for k, v in sorted(self.children.items()) if v},
                "edges": [edge.canonical() for src in sorted(self.edges_out) for edge in sorted(self.edges_out[src], key=lambda e: (e.target, e.relation, e.cost))],
                "generation": self._generation,
            }
            self._graph_hash = _sha(payload)
            self._dirty = False
        return self._graph_hash

    def snapshot(self) -> dict[str, Any]:
        role_counts = {role: len(ids) for role, ids in sorted(self.role_index.items()) if ids}
        edge_count = sum(len(edges) for edges in self.edges_out.values())
        return {
            "identity": self.META_ROOT,
            "generation": self._generation,
            "nodeCount": len(self.nodes),
            "edgeCount": edge_count,
            "roleCounts": role_counts,
            "graphHash": self.graph_hash(),
            "frameCount": len(self.frames),
            "semantics": {
                "containment": "ACYCLIC_ANCESTRY",
                "traversal": "CYCLIC_ALLOWED",
                "reentry": "PARENT_FRAME_CONTINUATION",
                "execution": "ROUTE_RESOLUTION_SEPARATE_FROM_ACTUATOR_EXECUTION",
            },
        }


def seed_primitive_ladder(runtime: RecursiveILLLMRuntime) -> None:
    ladder = [
        ("primitive", "PRIMITIVE", ["identity", "presence", "relation", "state"]),
        ("number", "NUMBER", ["number", "integer", "quantity", "ordinal"]),
        ("element", "ELEMENT", ["element", "symbol", "material", "periodic"]),
        ("language", "LANGUAGE", ["language", "symbol", "lexicon", "syntax"]),
        ("mathematics", "MATHEMATICS", ["mathematics", "algebra", "function", "relation"]),
        ("computer-science", "COMPUTER_SCIENCE", ["computer science", "algorithm", "state machine", "data structure"]),
        ("source-code", "SOURCE_CODE", ["source code", "function", "module", "runtime"]),
        ("sector", "SECTOR", ["professional sector", "domain", "service", "practice"]),
        ("data", "DATA", ["actual data", "record", "evidence", "observation"]),
        ("runtime", "RUNTIME", ["runtime", "execution", "service", "readback"]),
    ]
    parent = runtime.META_ROOT
    previous: str | None = None
    for index, (name, role, terms) in enumerate(ladder, start=1):
        identity = f"il-llm://foundation/{name}"
        runtime.register_node(ILLLMNode(
            identity=identity,
            role=role,
            parent=parent,
            semantic_terms=_tokens(terms),
            mathematical_state={"ordinal": index, "normalized": index / len(ladder)},
            observed_state="RESIDENT",
        ))
        if previous:
            runtime.add_edge(TraversalEdge(previous, identity, "ASCEND_ABSTRACTION", cost=0.25))
            runtime.add_edge(TraversalEdge(identity, previous, "DECOMPOSE_TO_FOUNDATION", cost=0.25))
        previous = identity
        parent = identity
