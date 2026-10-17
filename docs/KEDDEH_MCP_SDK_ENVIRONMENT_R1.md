# KEDDEH MCP + SDK Environment R1

This environment adds one governed server surface for the existing BRAINK MCP capability adapter and an explicit SDK discovery surface.

## Runtime

- runtime ID: `runtime://keddeh/mcp-sdk-environment`
- environment ID: `environment://keddeh/mcp-sdk`
- SDK ID: `sdk://keddeh/braink`

## HTTP surfaces

- `/health` — environment/runtime health
- `/environment` — machine-readable environment contract
- `/mcp` — existing BRAINK streamable HTTP MCP application
- `/sdk/manifest` — SDK/runtime discovery contract
- `/sdk/docs` — generated API documentation

The MCP application is mounted from the existing `mcp.braink_process_adapter.main:app`. No second capability implementation is created.

## Authority

All mutation remains behind the existing `braink_invoke_capability` governed path. The environment server is a transport and discovery surface; it is not a new authority plane.

The existing HMAC requirement remains mandatory. The server must not manufacture an ephemeral production key.

## Environment

Required:

`BRAINK_MCP_HMAC_KEY_HEX`

Optional:

`BRAINK_MCP_STATE_DIR`

The environment server therefore provides a concrete MCP runtime, a discoverable SDK surface and a machine-readable environment contract without falsely claiming public deployment.

## KEDDEH workflow

The corresponding workflow is registered in the KEDDEH runtime as:

`KEDDEH MCP SDK Environment Qualification`

Its purpose is to qualify the environment, inspect its MCP manifest, exercise the new-environment capability path and return durable workflow receipts.
