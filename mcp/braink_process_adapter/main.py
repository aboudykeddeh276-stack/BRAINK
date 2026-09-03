from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .backend import BrainkProcessBackend

mcp = FastMCP("BRAINK Enterprise Capability Adapter")


def backend() -> BrainkProcessBackend:
    return BrainkProcessBackend()


def governed_required(capability_id: str) -> dict[str, Any]:
    return {
        "status": "GOVERNED_PATH_REQUIRED",
        "capability_id": capability_id,
        "use_tool": "braink_invoke_capability",
    }


@mcp.tool(description="Return the governed enterprise capability manifest including sector owner, repository owner, operation, risk, authorization scopes, idempotency and approval requirements.",annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_capability_manifest()->list[dict[str,Any]]:
    return backend().capability_manifest()


@mcp.tool(description="Return the typed agent function-call manifest for governed BRAINK capabilities. Each function has an explicit parameter schema/defaults but still executes only through braink_invoke_capability.",annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_function_manifest()->list[dict[str,Any]]:
    return backend().function_manifest()


@mcp.tool(description="Authoritative enterprise invocation path. Payload is validated against the selected typed function contract, then scope, lease, approval, idempotency, circuit, durable invocation and resident-mechanic controls are enforced.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=True,idempotentHint=False,openWorldHint=True))
def braink_invoke_capability(capability_id:str,context:dict[str,Any],payload:dict[str,Any],idempotency_key:str|None=None)->dict[str,Any]:
    return backend().invoke_capability(capability_id,context,payload,idempotency_key)


@mcp.tool(description="Resolve the canonical legal and operating identity binding for Keddeh Systems.",annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_resolve_identity()->dict[str,Any]:
    return backend().resolve_identity()


@mcp.tool(description="Create a signed durable BRAINK work envelope before governed capability execution.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=False,openWorldHint=False))
def braink_create_work_envelope(work_id:str,intent:str,state:dict[str,Any]|None=None,epoch:int=1)->dict[str,Any]:
    return backend().create_envelope(work_id,intent,state,epoch)


@mcp.tool(description="Verify and permanently consume a signed work-envelope nonce so replay is rejected.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=False,openWorldHint=False))
def braink_consume_work_envelope(envelope:dict[str,Any])->dict[str,Any]:
    return backend().consume_envelope(envelope)


@mcp.tool(description="Acquire or advance the fenced work lease epoch for an agent or worker.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=False,openWorldHint=False))
def braink_acquire_work_lease(work_id:str,holder:str,requested_epoch:int|None=None)->dict[str,Any]:
    return backend().acquire_lease(work_id,holder,requested_epoch)


@mcp.tool(description="Read the authoritative lease holder and epoch without changing state.",annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_get_work_lease(work_id:str)->dict[str,Any]:
    return backend().current_lease(work_id)


# Read-only convenience projections remain callable directly.
@mcp.tool(description="Read DOMAIN_AUTHORITY state. For the governed contract use capability domain.observe.",annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_observe_domain_authority(domain:str)->dict[str,Any]:
    return backend().observe_domain_authority(domain)


@mcp.tool(description="Read a signed checkpoint. For the governed contract use capability checkpoint.read.",annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_read_checkpoint(work_id:str)->dict[str,Any]:
    return backend().read_checkpoint(work_id)


@mcp.tool(description="Probe the verified SERVERS-KEDDEHSYSTEMS actuator bridge. For the governed contract use capability server.probe.",annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_server_probe()->dict[str,Any]:
    return backend().server_probe()


@mcp.tool(description="Read a VFS value through the verified VirtualMemoryRuntime. For the governed contract use capability vfs.read.",annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_vfs_read(logical:str,backing:str)->dict[str,Any]:
    return backend().vfs_read(logical,backing)


# Legacy mutating entry points are fenced instead of bypassing enterprise governance.
@mcp.tool(description="Legacy domain mutation entry point. Direct mutation is disabled; use braink_invoke_capability with domain.provision.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_provision_domain_authority(tx_id:str,domain:str,ip:str,owner_scope:str="KEDDEH_SYSTEMS")->dict[str,Any]:
    return governed_required("domain.provision")


@mcp.tool(description="Legacy checkpoint mutation entry point. Direct mutation is disabled; use braink_invoke_capability with checkpoint.write.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_write_checkpoint(work_id:str,state:dict[str,Any])->dict[str,Any]:
    return governed_required("checkpoint.write")


@mcp.tool(description="Legacy server mutation entry point. Direct mutation is disabled. Resolve server.amend, server.release, server.validate_origin or server.readback through braink_invoke_capability.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=True,idempotentHint=False,openWorldHint=True))
def braink_server_apply(operation:str,payload:dict[str,Any]|None=None)->dict[str,Any]:
    mapping={"AMEND":"server.amend","RELEASE":"server.release","VALIDATE_ORIGIN":"server.validate_origin","READBACK":"server.readback","PROBE":"server.probe"}
    return governed_required(mapping.get(operation.upper(),"server.unknown"))


@mcp.tool(description="Legacy VFS bind mutation entry point. Direct mutation is disabled; use braink_invoke_capability with vfs.bind.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_vfs_bind(logical:str,backing:str)->dict[str,Any]:
    return governed_required("vfs.bind")


@mcp.tool(description="Legacy VFS write entry point. Direct mutation is disabled; use braink_invoke_capability with vfs.write.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_vfs_write(logical:str,backing:str,payload:dict[str,Any])->dict[str,Any]:
    return governed_required("vfs.write")


@mcp.tool(description="Legacy VFS migration entry point. Direct mutation is disabled; use braink_invoke_capability with vfs.migrate and an approval token.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_vfs_migrate(logical:str,current_backing:str,new_backing:str)->dict[str,Any]:
    return governed_required("vfs.migrate")


app=mcp.streamable_http_app()
