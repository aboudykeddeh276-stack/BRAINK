#!/usr/bin/env python3
"""Resident validator for the BRAINK/KEX node-template system.

Validates the governed definition/runtime/native/public-surface chain without
requiring GitHub Actions or an external service.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def require(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def main() -> int:
    checks=[]
    governance=load_json(ROOT/"governance/node/BRAINK_NODE_TEMPLATE_R1.json")
    filegov=load_json(ROOT/"governance/file/BRAINK_FILE_GOVERNANCE_R1.json")
    control=load_json(ROOT/".kex/runner-control-plane.json")

    require(governance["schema"]=="braink.node-template.r1","node governance schema")
    require(set(governance["capability_classes"])=={"DUMB_NODE","SMART_NODE","AGENTIC_NODE","SYSTEM_NODE"},"capability classes")
    require("NODE_TEMPLATE" in filegov["artifact_classes"],"NODE_TEMPLATE file class")
    require("template_contract" in filegov,"file template contract")
    require(control["schema"]=="kex.github-runner-control-plane.v10","control plane v10")
    checks += ["governance","file_governance","control_plane"]

    runtime_path=ROOT/"runtime/node/braink_node_templates.py"
    spec=importlib.util.spec_from_file_location("braink_node_templates",runtime_path)
    module=importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    result=module.self_test()
    require(result.get("status")=="PASS","runtime self-test")
    checks += result.get("checks",[])

    gateway=(ROOT/"runtime/public_gateway.py").read_text(encoding="utf-8")
    for route in ["/nodes/templates","/nodes/instances","/nodes/instance","/nodes/instantiate","/nodes/mutate"]:
        require(route in gateway,f"missing gateway route {route}")
    checks.append("public_gateway_routes")

    swift=(ROOT/"NativeChatBot/Sources/BRAINKNodeTemplateRuntime.swift").read_text(encoding="utf-8")
    ui=(ROOT/"NativeChatBot/Sources/BRAINKUIContainers.swift").read_text(encoding="utf-8")
    for marker in ["instanceID","templateID","definitionID","lineageRoot","proofRoot"]:
        require(marker in swift,f"missing native identity {marker}")
    require("BRAINKTemplateBackedView" in swift,"native template backed view")
    require("TemplateBackedPanel" in ui,"native template panel")
    checks += ["native_identity","native_template_backed_hci"]

    forbidden_identity=[
        "copy_opaque_markup_as_identity",
        "time_or_randomness_as_lineage_identity"
    ]
    serialized=json.dumps(governance,sort_keys=True)
    for marker in forbidden_identity:
        require(marker in serialized,f"missing forbidden law {marker}")
    checks.append("anti_copy_identity_laws")

    print(json.dumps({"status":"PASS","checks":checks},indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
