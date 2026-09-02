#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from hardening import append_jsonl_fsync, atomic_write_text, canonical_json_bytes, sha256_bytes

BASE = Path(__file__).resolve().parents[2]
RUNTIME = BASE / "runtime"
STATE_ROOT = RUNTIME / "illlm"
TOPOLOGY_PATH = STATE_ROOT / "higher-order-topology.json"
TRAVERSAL_LEDGER = STATE_ROOT / "traversal-ledger.jsonl"
PROOF_LEDGER = BASE / "reports" / "kex-wbos" / "illlm-higher-order-proof.jsonl"
SEED_PATH = RUNTIME / "ILLLM_FEDERATION_SEED_R1.json"

ILLLM_URI = re.compile(r"^(?:il-llm|illlm)://", re.I)
SECTOR_RE = re.compile(r"/sector/s(\d+)", re.I)


@dataclass
class ILLLMNode:
    identity: str
    role: str
    parent: str | None
    children: list[str]
    entry_routes: list[str]
    reentry_routes: list[str]
    continuation: str | None
    frame_class: str
    evidence: list[str]
    execution_state: str


@dataclass
class TraversalFrame:
    frame_id: str
    root: str
    current: str
    ancestry: list[str]
    visited: list[str]
    logical_time: int
    state: str


def _load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def _role(identity: str) -> str:
    low = identity.lower()
    if "/planning/" in low or "/plan/" in low:
        return "PLANNING"
    if "/research/" in low:
        return "RESEARCH"
    if "/sector/" in low:
        return "SECTOR"
    if "/capability/" in low:
        return "CAPABILITY"
    if "/infrastructure/" in low or "/edge/" in low:
        return "INFRASTRUCTURE"
    if "lexicon" in low:
        return "LEXICON"
    if "proof" in low:
        return "PROOF"
    return "GENERAL"


def _infer_parent(identity: str) -> str | None:
    low = identity.lower()
    # Specific paths must precede generic /sector/ matching.
    if "/research/sector/" in low:
        return "il-llm://braink/research"
    match = SECTOR_RE.search(low)
    if match:
        return "il-llm://braink/sector"
    if "/planning/" in low:
        return "il-llm://braink/planning"
    if "/capability/" in low:
        return "il-llm://braink/capability"
    if "/infrastructure/" in low:
        return "il-llm://braink/infrastructure"
    return "il-llm://braink"


def build_topology(discovered: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    seed = _load(SEED_PATH, {})
    records: dict[str, ILLLMNode] = {}

    root_ids = [
        "il-llm://braink",
        "il-llm://braink/planning",
        "il-llm://braink/sector",
        "il-llm://braink/research",
        "il-llm://braink/capability",
        "il-llm://braink/infrastructure",
    ]
    for identity in root_ids:
        parent = None if identity == "il-llm://braink" else _infer_parent(identity)
        records[identity] = ILLLMNode(
            identity=identity,
            role="META" if identity == "il-llm://braink" else _role(identity),
            parent=parent,
            children=[],
            entry_routes=[],
            reentry_routes=[],
            continuation=None,
            frame_class="HIGHER_ORDER" if identity == "il-llm://braink" else "CONTAINER",
            evidence=["runtime/ILLLM_FEDERATION_SEED_R1.json"],
            execution_state="REGISTERED",
        )

    identities: list[dict[str, Any]] = list(seed.get("known_identities", []))
    template = seed.get("sector_template", {})
    try:
        first = int(template.get("first", 1)); last = int(template.get("last", 0))
        prefix = str(template.get("prefix", ""))
        for i in range(first, last + 1):
            identities.append({"identity": f"{prefix}{i:02d}", "class": "SECTOR", "carrier": None})
    except Exception:
        pass
    identities.extend(discovered or [])

    for item in identities:
        identity = str(item.get("identity", ""))
        if not ILLLM_URI.match(identity):
            continue
        parent = str(item.get("parent") or _infer_parent(identity) or "il-llm://braink")
        records.setdefault(parent, ILLLMNode(parent, _role(parent), _infer_parent(parent), [], [], [], None, "CONTAINER", [], "REGISTERED"))
        node = records.get(identity)
        evidence = [str(item.get("carrier"))] if item.get("carrier") else []
        if node is None:
            node = ILLLMNode(
                identity=identity,
                role=str(item.get("class") or _role(identity)),
                parent=parent,
                children=[],
                entry_routes=[],
                reentry_routes=[],
                continuation=str(item.get("continuation")) if item.get("continuation") else None,
                frame_class="NESTED",
                evidence=evidence,
                execution_state=str(item.get("execution_state") or "REGISTERED"),
            )
            records[identity] = node
        if identity not in records[parent].children:
            records[parent].children.append(identity)

    for node in records.values():
        if node.parent and node.parent in records:
            node.entry_routes = [f"{node.parent} -> {node.identity}"]
            node.reentry_routes = [f"{node.identity} -> {node.parent}"]
        node.children.sort()

    nodes = [asdict(records[key]) for key in sorted(records)]
    edges = []
    for node in nodes:
        if node["parent"]:
            edges.append({"source": node["parent"], "relation": "CONTAINS", "target": node["identity"]})
            edges.append({"source": node["identity"], "relation": "REENTERS", "target": node["parent"]})
        if node["continuation"]:
            edges.append({"source": node["identity"], "relation": "CONTINUES_AS", "target": node["continuation"]})

    payload = {
        "schema": "kex.illlm.higher-order-topology.v1",
        "root": "il-llm://braink",
        "model": "RECURSIVE_CONTAINMENT_AND_TRAVERSAL",
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "nodes": nodes,
        "edges": edges,
        "semantics": {
            "containment": "An IL-LLM may contain descendant IL-LLM state spaces.",
            "entry": "Traversal enters a descendant while preserving ancestry/frame identity.",
            "reentry": "Traversal returns through the parent ancestry rather than flattening descendant state into a peer result.",
            "continuation": "A traversal may externalise continuation state and later rehydrate the same logical frame.",
            "meta_runtime": "il-llm://braink selects, traverses and reconciles descendant IL-LLMs but is not treated as an ordinary peer member."
        },
        "claimBoundary": "Topology registration does not prove every historical descendant is resident or executing. Execution state is per-node evidence.",
        "createdAt": time.time(),
    }
    payload["topologyHash"] = sha256_bytes(canonical_json_bytes(payload))
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    atomic_write_text(TOPOLOGY_PATH, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    append_jsonl_fsync(PROOF_LEDGER, {"ts": time.time(), "event": "ILLLM_HIGHER_ORDER_TOPOLOGY_BUILT", "topologyHash": payload["topologyHash"], "nodeCount": len(nodes), "edgeCount": len(edges)})
    return payload


def begin_frame(root: str = "il-llm://braink") -> TraversalFrame:
    frame_id = f"continuation://braink/illlm/frame/{uuid.uuid4().hex}"
    frame = TraversalFrame(frame_id, root, root, [root], [root], 1, "OPEN")
    append_jsonl_fsync(TRAVERSAL_LEDGER, {"ts": time.time(), "event": "FRAME_OPEN", **asdict(frame)})
    return frame


def traverse(frame: TraversalFrame, target: str, topology: dict[str, Any]) -> TraversalFrame:
    nodes = {node["identity"]: node for node in topology.get("nodes", [])}
    if target not in nodes:
        raise KeyError(f"unknown IL-LLM target: {target}")
    current_node = nodes.get(frame.current)
    target_node = nodes[target]
    allowed = target in (current_node or {}).get("children", []) or target_node.get("parent") == frame.current
    if not allowed:
        raise ValueError(f"target {target} is not a direct descendant of current frame {frame.current}")
    next_frame = TraversalFrame(
        frame_id=frame.frame_id,
        root=frame.root,
        current=target,
        ancestry=frame.ancestry + [target],
        visited=frame.visited + [target],
        logical_time=frame.logical_time + 1,
        state="OPEN",
    )
    append_jsonl_fsync(TRAVERSAL_LEDGER, {"ts": time.time(), "event": "FRAME_ENTER", "from": frame.current, "to": target, **asdict(next_frame)})
    return next_frame


def reenter_parent(frame: TraversalFrame) -> TraversalFrame:
    if len(frame.ancestry) <= 1:
        return frame
    parent = frame.ancestry[-2]
    next_frame = TraversalFrame(
        frame_id=frame.frame_id,
        root=frame.root,
        current=parent,
        ancestry=frame.ancestry[:-1],
        visited=frame.visited + [parent],
        logical_time=frame.logical_time + 1,
        state="OPEN",
    )
    append_jsonl_fsync(TRAVERSAL_LEDGER, {"ts": time.time(), "event": "FRAME_REENTRY", "from": frame.current, "to": parent, **asdict(next_frame)})
    return next_frame


def route_to_role(role: str, topology: dict[str, Any]) -> list[str]:
    wanted = role.upper()
    return [node["identity"] for node in topology.get("nodes", []) if str(node.get("role", "")).upper() == wanted]


if __name__ == "__main__":
    topology = build_topology()
    print(json.dumps({"status": "BUILT", "root": topology["root"], "nodeCount": topology["nodeCount"], "edgeCount": topology["edgeCount"], "topologyHash": topology["topologyHash"]}, indent=2))
