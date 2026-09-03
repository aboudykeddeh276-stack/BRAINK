from __future__ import annotations

import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MAIN=ROOT/"mcp/braink_process_adapter/main.py"
BACKEND=ROOT/"mcp/braink_process_adapter/backend.py"


def function_calls(fn: ast.FunctionDef) -> set[str]:
    calls=set()
    for node in ast.walk(fn):
        if isinstance(node,ast.Call):
            target=node.func
            if isinstance(target,ast.Name): calls.add(target.id)
            elif isinstance(target,ast.Attribute):
                parts=[]
                cur=target
                while isinstance(cur,ast.Attribute):
                    parts.append(cur.attr); cur=cur.value
                if isinstance(cur,ast.Name): parts.append(cur.id)
                calls.add(".".join(reversed(parts)))
    return calls


def main():
    tree=ast.parse(MAIN.read_text())
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}

    required={
        "braink_capability_manifest",
        "braink_invoke_capability",
        "braink_provision_domain_authority",
        "braink_write_checkpoint",
        "braink_server_apply",
        "braink_vfs_bind",
        "braink_vfs_write",
        "braink_vfs_migrate",
    }
    assert required <= functions.keys(), f"missing MCP governance functions: {sorted(required-functions.keys())}"

    legacy_mutators={
        "braink_provision_domain_authority",
        "braink_write_checkpoint",
        "braink_server_apply",
        "braink_vfs_bind",
        "braink_vfs_write",
        "braink_vfs_migrate",
    }
    forbidden={
        "backend.provision_domain_authority",
        "backend.write_checkpoint",
        "backend.server_apply",
        "backend.vfs_bind",
        "backend.vfs_write",
        "backend.vfs_migrate",
    }
    for name in legacy_mutators:
        calls=function_calls(functions[name])
        assert "governed_required" in calls, f"{name} no longer fences legacy mutation"
        assert not (calls & forbidden), f"{name} bypasses governance: {sorted(calls & forbidden)}"

    invoke_calls=function_calls(functions["braink_invoke_capability"])
    assert "backend.invoke_capability" in invoke_calls, "authoritative invocation tool does not call governed backend"

    backend_text=BACKEND.read_text()
    assert "GovernedCapabilityService" in backend_text
    assert "capability_receipts.sqlite" in backend_text
    print("R6 MCP governance surface PASS")


if __name__=="__main__":
    main()
