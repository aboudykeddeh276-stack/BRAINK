#!/usr/bin/env python3
"""BRAINK R33 node-transition compatibility layer.

This module does not replace R15/R16 federation, host fabric, network intent,
agent orchestration, adapters, or sector runtimes. It converts their existing
outputs into one executable node identity so later bindings operate on the node
rather than silently promoting a queue/receipt/descriptor to authority.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, replace
from typing import Any, Mapping, Sequence
import hashlib
import json
import time

SCHEMA = "braink.node-transition.r33/v1"
STATE_ORDER = (
    "NODE_MATERIALIZED",
    "EDGE_BOUND",
    "TRANSITION_PROPAGATED",
    "EFFECT_READBACK",
    "QUALIFIED",
)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def sha(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class NodeTransition:
    schema: str
    node_id: str
    node_class: str
    source_uri: str
    source_root: str
    causal_id: str
    authority_root: str
    sector_id: str
    capability: str
    state: str
    state_definition: str
    allowed_transitions: tuple[str, ...]
    parent_context: str
    peer_edges: tuple[Mapping[str, Any], ...]
    payload: Mapping[str, Any]
    payload_root: str
    evidence_refs: tuple[str, ...]
    previous_transition_root: str | None
    transition_root: str
    updated_ns: int


def _root_body(value: Mapping[str, Any]) -> str:
    return sha({k: v for k, v in value.items() if k != "transition_root"})


def materialize(
    *,
    source_uri: str,
    source_state: Mapping[str, Any],
    causal_id: str,
    authority_root: str,
    sector_id: str,
    capability: str,
    payload: Mapping[str, Any],
    parent_context: str,
    peer_edges: Sequence[Mapping[str, Any]] = (),
    evidence_refs: Sequence[str] = (),
    node_class: str = "EXECUTION_TRANSITION",
) -> NodeTransition:
    if not source_uri or not causal_id or not capability:
        raise ValueError("NODE_IDENTITY_FIELDS_REQUIRED")
    if not authority_root or authority_root == "UNBOUND":
        raise PermissionError("NODE_AUTHORITY_UNBOUND")
    source_root = sha(source_state)
    payload_root = sha(payload)
    node_id = f"node:{sha({'source_uri':source_uri,'causal_id':causal_id,'capability':capability,'authority_root':authority_root})[:32]}"
    body = {
        "schema": SCHEMA,
        "node_id": node_id,
        "node_class": node_class,
        "source_uri": source_uri,
        "source_root": source_root,
        "causal_id": causal_id,
        "authority_root": authority_root,
        "sector_id": sector_id,
        "capability": capability,
        "state": "NODE_MATERIALIZED",
        "state_definition": "Executable identity materialized from preserved source object; no downstream effect claimed.",
        "allowed_transitions": STATE_ORDER[1:],
        "parent_context": parent_context,
        "peer_edges": tuple(dict(edge) for edge in peer_edges),
        "payload": dict(payload),
        "payload_root": payload_root,
        "evidence_refs": tuple(evidence_refs),
        "previous_transition_root": None,
        "updated_ns": time.time_ns(),
    }
    body["transition_root"] = _root_body(body)
    return NodeTransition(**body)


def transition(node: NodeTransition, next_state: str, *, evidence_ref: str, state_definition: str) -> NodeTransition:
    if next_state not in STATE_ORDER:
        raise ValueError(f"UNKNOWN_NODE_STATE:{next_state}")
    current_i = STATE_ORDER.index(node.state)
    next_i = STATE_ORDER.index(next_state)
    if next_i != current_i + 1:
        raise ValueError(f"NON_ADJACENT_NODE_TRANSITION:{node.state}->{next_state}")
    if not evidence_ref:
        raise ValueError("NODE_TRANSITION_EVIDENCE_REQUIRED")
    body = asdict(node)
    body.update({
        "state": next_state,
        "state_definition": state_definition,
        "allowed_transitions": tuple(STATE_ORDER[next_i + 1:]),
        "evidence_refs": tuple((*node.evidence_refs, evidence_ref)),
        "previous_transition_root": node.transition_root,
        "updated_ns": time.time_ns(),
        "transition_root": "",
    })
    body["transition_root"] = _root_body(body)
    return NodeTransition(**body)


def materialize_network_request(request: Mapping[str, Any]) -> NodeTransition:
    from runtime.network.braink_network_intent import compile_request
    compiled = compile_request(dict(request))
    env = compiled["envelope"]
    return materialize(
        source_uri="runtime://braink/network-intent",
        source_state=compiled,
        causal_id=env["causal_id"],
        authority_root=env["authority_root"],
        sector_id="NETWORK_FABRIC",
        capability=env["capability"],
        payload={"target": env["target"], "input": env["input"], "constraints": env["constraints"]},
        parent_context="braink://network",
        peer_edges=({"relation": "ADAPTER_ROUTE", "target": env["adapter"]},),
        evidence_refs=("runtime/network/braink_network_intent.py",),
    )


def materialize_agent_process(process_id: str, input_state: Mapping[str, Any], *, authority_root: str, sector_id: str = "ENTERPRISE_AUTOMATION") -> NodeTransition:
    from runtime.agents.BRAINK_PUBLIC_SERVICE_AGENT_ORCHESTRATOR import dispatch
    receipt = dispatch(process_id, dict(input_state))
    return materialize(
        source_uri="runtime://braink/public-service-agent-orchestrator",
        source_state=receipt,
        causal_id=receipt["receipt_sha256"],
        authority_root=authority_root,
        sector_id=sector_id,
        capability=process_id,
        payload=dict(input_state),
        parent_context=str(receipt["fabric"]),
        peer_edges=tuple({"relation": "HANDOFF", "target": target} for target in receipt.get("handoff", [])),
        evidence_refs=("runtime/agents/BRAINK_PUBLIC_SERVICE_AGENT_ORCHESTRATOR.py", "runtime/agents/BRAINK_PUBLIC_SERVICE_AGENT_FABRIC.json"),
        node_class="AGENT_PROCESS_TRANSITION",
    )


def self_test() -> dict[str, Any]:
    base = materialize(
        source_uri="test://working-source",
        source_state={"working": True, "version": 1},
        causal_id="test:1",
        authority_root="authority:test",
        sector_id="TEST",
        capability="test.capability",
        payload={"x": 1},
        parent_context="node://test/parent",
    )
    assert base.state == "NODE_MATERIALIZED"
    assert base.source_root == sha({"working": True, "version": 1})
    bound = transition(base, "EDGE_BOUND", evidence_ref="test://edge", state_definition="test edge bound")
    assert bound.previous_transition_root == base.transition_root
    assert bound.source_root == base.source_root
    try:
        transition(bound, "EFFECT_READBACK", evidence_ref="test://bad-skip", state_definition="must fail")
        raise AssertionError("non-adjacent transition must fail")
    except ValueError:
        pass
    return {"status": "PASS", "checks": ["source_preserved", "node_materialized", "adjacent_transition_only", "evidence_required", "transition_chain"]}


if __name__ == "__main__":
    print(json.dumps(self_test(), indent=2, sort_keys=True))
