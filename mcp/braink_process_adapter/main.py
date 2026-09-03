from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .backend import BrainkProcessBackend

mcp = FastMCP("BRAINK Process Adapter")


def backend() -> BrainkProcessBackend:
    return BrainkProcessBackend()


@mcp.tool(description="Use this when the agent needs the canonical legal and operating identity binding for Keddeh Systems before executing a process.",annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_resolve_identity() -> dict[str, Any]: return backend().resolve_identity()

@mcp.tool(description="Use this when beginning a BRAINK process and a signed durable work envelope is required before any mutating action.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=False,openWorldHint=False))
def braink_create_work_envelope(work_id:str,intent:str,state:dict[str,Any]|None=None,epoch:int=1)->dict[str,Any]: return backend().create_envelope(work_id,intent,state,epoch)

@mcp.tool(description="Use this immediately before executing a signed work envelope. It verifies integrity and permanently consumes the nonce so replay is rejected.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=False,openWorldHint=False))
def braink_consume_work_envelope(envelope:dict[str,Any])->dict[str,Any]: return backend().consume_envelope(envelope)

@mcp.tool(description="Use this when assigning or replacing the active agent or worker for a work item. It advances or validates the fenced lease epoch.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=False,openWorldHint=False))
def braink_acquire_work_lease(work_id:str,holder:str,requested_epoch:int|None=None)->dict[str,Any]: return backend().acquire_lease(work_id,holder,requested_epoch)

@mcp.tool(description="Use this to read the current authoritative lease holder and epoch for a work item without changing state.",annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_get_work_lease(work_id:str)->dict[str,Any]: return backend().current_lease(work_id)

@mcp.tool(description="Use this when a domain intent has reached DOMAIN_AUTHORITY and the control-plane domain row plus authoritative zone and A record must commit atomically and then be read back.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=False,openWorldHint=False))
def braink_provision_domain_authority(tx_id:str,domain:str,ip:str,owner_scope:str="KEDDEH_SYSTEMS")->dict[str,Any]: return backend().provision_domain_authority(tx_id,domain,ip,owner_scope)

@mcp.tool(description="Use this to inspect current BRAINK DOMAIN_AUTHORITY state for a domain without mutating it.",annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_observe_domain_authority(domain:str)->dict[str,Any]: return backend().observe_domain_authority(domain)

@mcp.tool(description="Use this after a meaningful transition to persist a signed logical checkpoint that a successor process or agent can later verify and resume.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=False,openWorldHint=False))
def braink_write_checkpoint(work_id:str,state:dict[str,Any])->dict[str,Any]: return backend().write_checkpoint(work_id,state)

@mcp.tool(description="Use this when a successor process or agent needs to verify and read a previously persisted BRAINK checkpoint.",annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_read_checkpoint(work_id:str)->dict[str,Any]: return backend().read_checkpoint(work_id)

@mcp.tool(description="Use this to probe the verified SERVERS-KEDDEHSYSTEMS production actuator bridge. Returns UNBOUND_RUNTIME_PATH or UNBOUND_ACTUATOR instead of inventing execution.",annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_server_probe()->dict[str,Any]: return backend().server_probe()

@mcp.tool(description="Use this when a work envelope reaches SERVERS and must invoke the resident production actuator operation PROBE, VALIDATE_ORIGIN, AMEND, RELEASE, or READBACK.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=True,idempotentHint=False,openWorldHint=True))
def braink_server_apply(operation:str,payload:dict[str,Any]|None=None)->dict[str,Any]: return backend().server_apply(operation,payload)

@mcp.tool(description="Use this to resolve a logical VFS/K-DRIVE address to an existing file:// or sqlite:// backing through the verified VirtualMemoryRuntime adapter.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_vfs_bind(logical:str,backing:str)->dict[str,Any]: return backend().vfs_bind(logical,backing)

@mcp.tool(description="Use this to write JSON state through a verified VFS binding and return the resident adapter's committed value hash.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_vfs_write(logical:str,backing:str,payload:dict[str,Any])->dict[str,Any]: return backend().vfs_write(logical,backing,payload)

@mcp.tool(description="Use this to read a logical VFS value through its backing and return resident readback plus value hash.",annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False))
def braink_vfs_read(logical:str,backing:str)->dict[str,Any]: return backend().vfs_read(logical,backing)

@mcp.tool(description="Use this to migrate a logical VFS value from one backing to another; the resident runtime performs write, readback, and value-hash verification before rebinding.",annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=False,openWorldHint=False))
def braink_vfs_migrate(logical:str,current_backing:str,new_backing:str)->dict[str,Any]: return backend().vfs_migrate(logical,current_backing,new_backing)

app=mcp.streamable_http_app()
