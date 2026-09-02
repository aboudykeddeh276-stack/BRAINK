from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .backend import BrainkProcessBackend

mcp = FastMCP("BRAINK Process Adapter")


def backend() -> BrainkProcessBackend:
    return BrainkProcessBackend()


@mcp.tool(
    description="Use this when the agent needs the canonical legal and operating identity binding for Keddeh Systems before executing a process.",
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
def braink_resolve_identity() -> dict[str, Any]:
    return backend().resolve_identity()


@mcp.tool(
    description="Use this when beginning a BRAINK process and a signed durable work envelope is required before any mutating action.",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
def braink_create_work_envelope(work_id: str, intent: str, state: dict[str, Any] | None = None, epoch: int = 1) -> dict[str, Any]:
    return backend().create_envelope(work_id, intent, state, epoch)


@mcp.tool(
    description="Use this immediately before executing a signed work envelope. It verifies integrity and permanently consumes the nonce so replay is rejected.",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
def braink_consume_work_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    return backend().consume_envelope(envelope)


@mcp.tool(
    description="Use this when assigning or replacing the active agent or worker for a work item. It advances or validates the fenced lease epoch.",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
def braink_acquire_work_lease(work_id: str, holder: str, requested_epoch: int | None = None) -> dict[str, Any]:
    return backend().acquire_lease(work_id, holder, requested_epoch)


@mcp.tool(
    description="Use this to read the current authoritative lease holder and epoch for a work item without changing state.",
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
def braink_get_work_lease(work_id: str) -> dict[str, Any]:
    return backend().current_lease(work_id)


@mcp.tool(
    description="Use this when a domain intent has reached DOMAIN_AUTHORITY and the control-plane domain row plus authoritative zone and A record must commit atomically and then be read back.",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
def braink_provision_domain_authority(tx_id: str, domain: str, ip: str, owner_scope: str = "KEDDEH_SYSTEMS") -> dict[str, Any]:
    return backend().provision_domain_authority(tx_id, domain, ip, owner_scope)


@mcp.tool(
    description="Use this to inspect current BRAINK DOMAIN_AUTHORITY state for a domain without mutating it.",
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
def braink_observe_domain_authority(domain: str) -> dict[str, Any]:
    return backend().observe_domain_authority(domain)


@mcp.tool(
    description="Use this after a meaningful transition to persist a signed logical checkpoint that a successor process or agent can later verify and resume.",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
def braink_write_checkpoint(work_id: str, state: dict[str, Any]) -> dict[str, Any]:
    return backend().write_checkpoint(work_id, state)


@mcp.tool(
    description="Use this when a successor process or agent needs to verify and read a previously persisted BRAINK checkpoint.",
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
def braink_read_checkpoint(work_id: str) -> dict[str, Any]:
    return backend().read_checkpoint(work_id)


app = mcp.streamable_http_app()
