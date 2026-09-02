#!/usr/bin/env python3
from __future__ import annotations

import math
import re
import time
from collections import Counter, deque
from dataclasses import dataclass, asdict
from typing import Any

from hardening import append_jsonl_fsync, canonical_json_bytes, sha256_bytes
from illlm_higher_order import TraversalFrame

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{1,}")


@dataclass(frozen=True)
class ContextAnchor:
    term: str
    weight: float
    source: str


@dataclass
class ContextFrame:
    traversal: TraversalFrame
    anchors: list[ContextAnchor]
    inherited_state: dict[str, Any]
    admissible_roles: list[str]
    relevance_floor: float
    context_hash: str


def _tokens(value: str) -> list[str]:
    return [m.group(0).casefold() for m in TOKEN_RE.finditer(value)]


def _normalize_anchors(context: str | dict[str, Any] | list[Any]) -> list[ContextAnchor]:
    if isinstance(context, str):
        text = context
    else:
        text = str(context)
    counts = Counter(_tokens(text))
    total = max(1, sum(counts.values()))
    anchors = [
        ContextAnchor(term=term, weight=count / total, source="current-context")
        for term, count in counts.most_common(128)
    ]
    return anchors


def _node_terms(node: dict[str, Any]) -> set[str]:
    material = " ".join(
        [
            str(node.get("identity", "")),
            str(node.get("role", "")),
            " ".join(map(str, node.get("evidence", []))),
            str(node.get("frame_class", "")),
        ]
    )
    return set(_tokens(material))


def _score(node: dict[str, Any], anchors: list[ContextAnchor], role_bias: dict[str, float] | None = None) -> float:
    terms = _node_terms(node)
    if not terms:
        return 0.0
    anchor_score = sum(anchor.weight for anchor in anchors if anchor.term in terms)
    role = str(node.get("role", "GENERAL")).upper()
    bias = (role_bias or {}).get(role, 0.0)
    depth_hint = str(node.get("identity", "")).count("/")
    specificity = min(0.1, depth_hint * 0.01)
    return anchor_score + bias + specificity


def begin_context_frame(
    traversal: TraversalFrame,
    context: str | dict[str, Any] | list[Any],
    *,
    inherited_state: dict[str, Any] | None = None,
    admissible_roles: list[str] | None = None,
    relevance_floor: float = 0.0,
) -> ContextFrame:
    anchors = _normalize_anchors(context)
    state = dict(inherited_state or {})
    roles = sorted({role.upper() for role in (admissible_roles or [])})
    unsigned = {
        "frameId": traversal.frame_id,
        "current": traversal.current,
        "anchors": [asdict(a) for a in anchors],
        "inheritedState": state,
        "admissibleRoles": roles,
        "relevanceFloor": relevance_floor,
    }
    return ContextFrame(
        traversal=traversal,
        anchors=anchors,
        inherited_state=state,
        admissible_roles=roles,
        relevance_floor=relevance_floor,
        context_hash=sha256_bytes(canonical_json_bytes(unsigned)),
    )


def resolve_contextual_targets(
    frame: ContextFrame,
    topology: dict[str, Any],
    *,
    limit: int = 16,
    role_bias: dict[str, float] | None = None,
    descendants_only: bool = True,
) -> list[dict[str, Any]]:
    nodes = {node["identity"]: node for node in topology.get("nodes", [])}
    current = nodes.get(frame.traversal.current)
    if current is None:
        return []

    candidate_ids: set[str] = set()
    if descendants_only:
        queue = deque(current.get("children", []))
        while queue and len(candidate_ids) < 10000:
            identity = queue.popleft()
            if identity in candidate_ids:
                continue
            candidate_ids.add(identity)
            queue.extend(nodes.get(identity, {}).get("children", []))
    else:
        candidate_ids = set(nodes)

    scored: list[dict[str, Any]] = []
    allowed_roles = set(frame.admissible_roles)
    for identity in candidate_ids:
        node = nodes.get(identity)
        if not node:
            continue
        role = str(node.get("role", "GENERAL")).upper()
        if allowed_roles and role not in allowed_roles:
            continue
        score = _score(node, frame.anchors, role_bias)
        if score < frame.relevance_floor:
            continue
        matched = [a.term for a in frame.anchors if a.term in _node_terms(node)]
        scored.append(
            {
                "identity": identity,
                "role": role,
                "score": score,
                "matchedAnchors": matched[:32],
                "parent": node.get("parent"),
                "executionState": node.get("execution_state"),
            }
        )
    scored.sort(key=lambda item: (-item["score"], item["identity"]))
    return scored[: max(1, limit)]


def enter_contextual_target(
    frame: ContextFrame,
    target: dict[str, Any],
    *,
    inherited_patch: dict[str, Any] | None = None,
    ledger_path=None,
) -> ContextFrame:
    identity = str(target["identity"])
    traversal = TraversalFrame(
        frame_id=frame.traversal.frame_id,
        root=frame.traversal.root,
        current=identity,
        ancestry=frame.traversal.ancestry + [identity],
        visited=frame.traversal.visited + [identity],
        logical_time=frame.traversal.logical_time + 1,
        state="OPEN",
    )
    inherited = dict(frame.inherited_state)
    inherited.update(inherited_patch or {})
    inherited["lastTraversalScore"] = target.get("score")
    inherited["lastMatchedAnchors"] = target.get("matchedAnchors", [])
    next_frame = begin_context_frame(
        traversal,
        [a.term for a in frame.anchors],
        inherited_state=inherited,
        admissible_roles=frame.admissible_roles,
        relevance_floor=frame.relevance_floor,
    )
    if ledger_path is not None:
        append_jsonl_fsync(
            ledger_path,
            {
                "ts": time.time(),
                "event": "CONTEXTUAL_FRAME_ENTER",
                "frameId": traversal.frame_id,
                "from": frame.traversal.current,
                "to": identity,
                "score": target.get("score"),
                "matchedAnchors": target.get("matchedAnchors", []),
                "contextHashBefore": frame.context_hash,
                "contextHashAfter": next_frame.context_hash,
            },
        )
    return next_frame


def contextual_reentry(frame: ContextFrame, *, ledger_path=None) -> ContextFrame:
    if len(frame.traversal.ancestry) <= 1:
        return frame
    parent = frame.traversal.ancestry[-2]
    traversal = TraversalFrame(
        frame_id=frame.traversal.frame_id,
        root=frame.traversal.root,
        current=parent,
        ancestry=frame.traversal.ancestry[:-1],
        visited=frame.traversal.visited + [parent],
        logical_time=frame.traversal.logical_time + 1,
        state="OPEN",
    )
    next_frame = begin_context_frame(
        traversal,
        [a.term for a in frame.anchors],
        inherited_state=frame.inherited_state,
        admissible_roles=frame.admissible_roles,
        relevance_floor=frame.relevance_floor,
    )
    if ledger_path is not None:
        append_jsonl_fsync(
            ledger_path,
            {
                "ts": time.time(),
                "event": "CONTEXTUAL_FRAME_REENTRY",
                "frameId": traversal.frame_id,
                "from": frame.traversal.current,
                "to": parent,
                "contextHashBefore": frame.context_hash,
                "contextHashAfter": next_frame.context_hash,
            },
        )
    return next_frame
