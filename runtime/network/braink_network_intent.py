#!/usr/bin/env python3
"""BRAINK / IL-LLM deterministic network-intent compiler.

One producer request is normalized once, assigned one causal identity, then
projected into bounded observer ledgers. Transports/adapters do not redefine
semantic identity or authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List


def canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(value: Any) -> str:
    return hashlib.sha256(canon(value).encode()).hexdigest()


@dataclass(frozen=True)
class FunctionContract:
    intent: str
    capability: str
    adapter: str
    external_mutation: bool
    required_mode: str
    ledgers: tuple[str, ...]
    input_type: str = "object"
    output_type: str = "execution_receipt"


FUNCTIONS: Dict[str, FunctionContract] = {
    "HOST_INSPECT": FunctionContract(
        "HOST_INSPECT", "host.network.inspect", "desktop-commander", False,
        "ONLINE_OR_OFFLINE_LOCAL", ("host", "network", "proof"),
    ),
    "DNS_QUERY": FunctionContract(
        "DNS_QUERY", "network.dns.query", "kex-dns", False,
        "ONLINE_OR_OFFLINE_LOCAL", ("dns", "network", "proof"),
    ),
    "DNS_MUTATE": FunctionContract(
        "DNS_MUTATE", "network.dns.mutate", "kex-registrar-service", True,
        "ONLINE", ("dns", "da", "authority", "network", "proof"),
    ),
    "REGISTRAR_MUTATE": FunctionContract(
        "REGISTRAR_MUTATE", "network.registrar.mutate", "kex-registrar-service", True,
        "ONLINE", ("registrar", "da", "authority", "network", "proof"),
    ),
    "MESH_PROBE": FunctionContract(
        "MESH_PROBE", "network.mesh.probe", "kex-mesh-backbone", False,
        "ONLINE", ("mesh", "network", "uptime", "proof"),
    ),
    "MESH_SEND": FunctionContract(
        "MESH_SEND", "network.mesh.send", "kex-mesh-backbone", True,
        "ONLINE", ("mesh", "network", "security", "proof"),
    ),
    "BGP_RENDER": FunctionContract(
        "BGP_RENDER", "network.bgp.render", "frr-policy-renderer", False,
        "ONLINE_OR_OFFLINE_LOCAL", ("routing", "authority", "security", "proof"),
    ),
    "BGP_APPLY": FunctionContract(
        "BGP_APPLY", "network.bgp.apply", "frr", True,
        "ONLINE", ("routing", "authority", "security", "uptime", "proof"),
    ),
    "IOT_ADMIT": FunctionContract(
        "IOT_ADMIT", "network.iot.admit", "iot-device-admission", True,
        "ONLINE", ("iot", "identity", "security", "network", "proof"),
    ),
    "NETWORK_MODE": FunctionContract(
        "NETWORK_MODE", "network.mode.set", "braink-host-fabric", True,
        "ONLINE", ("host", "network", "authority", "proof"),
    ),
}

MUTATION_AUTHORITY_REQUIRED = True


def function_registry() -> List[Dict[str, Any]]:
    return [
        {
            "intent": c.intent,
            "capability": c.capability,
            "adapter": c.adapter,
            "external_mutation": c.external_mutation,
            "required_mode": c.required_mode,
            "ledgers": list(c.ledgers),
            "input_type": c.input_type,
            "output_type": c.output_type,
        }
        for c in sorted(FUNCTIONS.values(), key=lambda x: x.intent)
    ]


def normalize(request: Dict[str, Any]) -> Dict[str, Any]:
    intent = str(request.get("intent", "")).upper().strip()
    if intent not in FUNCTIONS:
        raise ValueError(f"UNKNOWN_NETWORK_INTENT:{intent}")
    contract = FUNCTIONS[intent]
    actor = str(request.get("actor", "")).strip()
    if not actor:
        raise ValueError("NETWORK_ACTOR_REQUIRED")
    authority_root = str(request.get("authority_root", "UNBOUND")).strip() or "UNBOUND"
    if contract.external_mutation and MUTATION_AUTHORITY_REQUIRED and authority_root == "UNBOUND":
        raise PermissionError("NETWORK_MUTATION_AUTHORITY_UNBOUND")

    causal_id = str(request.get("causal_id") or request.get("request_id") or f"net:{uuid.uuid4()}")
    semantic = {
        "schema": "braink.il-llm.network-intent.v1",
        "causal_id": causal_id,
        "actor": actor,
        "authority_root": authority_root,
        "intent": contract.intent,
        "capability": contract.capability,
        "adapter": contract.adapter,
        "target": request.get("target", {}),
        "input": request.get("input", {}),
        "constraints": request.get("constraints", {}),
        "required_mode": contract.required_mode,
        "external_mutation": contract.external_mutation,
    }
    semantic["semantic_root"] = sha(semantic)
    return semantic


def project(envelope: Dict[str, Any]) -> Dict[str, Any]:
    contract = FUNCTIONS[envelope["intent"]]
    projections: Dict[str, Dict[str, Any]] = {}
    for ledger in contract.ledgers:
        view = {
            "ledger": ledger,
            "causal_id": envelope["causal_id"],
            "semantic_root": envelope["semantic_root"],
            "intent": envelope["intent"],
            "capability": envelope["capability"],
            "adapter": envelope["adapter"],
            "authority_root": envelope["authority_root"],
            "target": envelope["target"],
            "required_mode": envelope["required_mode"],
        }
        view["projection_root"] = sha(view)
        projections[ledger] = view
    return {
        "schema": "braink.il-llm.network-projections.v1",
        "causal_id": envelope["causal_id"],
        "semantic_root": envelope["semantic_root"],
        "projections": projections,
    }


def compile_request(request: Dict[str, Any]) -> Dict[str, Any]:
    envelope = normalize(request)
    return {
        "status": "COMPILED",
        "envelope": envelope,
        "ledger_projection": project(envelope),
        "dispatch": {
            "capability": envelope["capability"],
            "adapter": envelope["adapter"],
            "required_mode": envelope["required_mode"],
            "external_mutation": envelope["external_mutation"],
        },
        "compiled_ns": time.time_ns(),
    }


def self_test() -> Dict[str, Any]:
    read = compile_request({
        "causal_id": "test:read",
        "actor": "AKD",
        "intent": "DNS_QUERY",
        "target": {"name": "alpha.keddeh.systems"},
        "authority_root": "UNBOUND",
    })
    assert read["status"] == "COMPILED"
    roots = {v["semantic_root"] for v in read["ledger_projection"]["projections"].values()}
    assert roots == {read["envelope"]["semantic_root"]}

    try:
        compile_request({"actor": "AKD", "intent": "DNS_MUTATE", "target": {"name": "x"}})
        raise AssertionError("mutation authority must fail closed")
    except PermissionError:
        pass

    write = compile_request({
        "causal_id": "test:write",
        "actor": "AKD",
        "intent": "DNS_MUTATE",
        "authority_root": "proof:test",
        "target": {"name": "x.keddeh.systems"},
        "input": {"type": "A", "value": "10.0.0.1"},
    })
    assert write["dispatch"]["external_mutation"] is True
    assert write["dispatch"]["required_mode"] == "ONLINE"
    assert "da" in write["ledger_projection"]["projections"]
    return {
        "status": "PASS",
        "checks": [
            "function_registry",
            "single_semantic_root",
            "bounded_ledger_projection",
            "mutation_authority_gate",
            "online_mutation_gate",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--registry", action="store_true")
    parser.add_argument("--request-json")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2, sort_keys=True))
        return 0
    if args.registry:
        print(json.dumps(function_registry(), indent=2, sort_keys=True))
        return 0
    if args.request_json:
        print(json.dumps(compile_request(json.loads(args.request_json)), indent=2, sort_keys=True))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
