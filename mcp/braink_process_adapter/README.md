# BRAINK MCP Process Adapter R1

Tool-only MCP adapter over `enterprise/orchestration/durable_execution_r5.py`.

It converts resident BRAINK process mechanics into callable MCP tools instead of treating a skill, prompt, or ChatGPT UI control as the execution boundary.

## Exposed tools

- `braink_resolve_identity`
- `braink_create_work_envelope`
- `braink_consume_work_envelope`
- `braink_acquire_work_lease`
- `braink_get_work_lease`
- `braink_provision_domain_authority`
- `braink_observe_domain_authority`
- `braink_write_checkpoint`
- `braink_read_checkpoint`

## Run

From the BRAINK repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r mcp/braink_process_adapter/requirements.txt
export BRAINK_MCP_HMAC_KEY_HEX="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export BRAINK_MCP_STATE_DIR="$PWD/runtime/braink_mcp"
uvicorn mcp.braink_process_adapter.main:app --host 0.0.0.0 --port 8000
```

The MCP endpoint is `/mcp`.

For ChatGPT, the MCP server must be reachable as a remote MCP server. Private/on-prem/local deployments should use the supported secure MCP tunnel path rather than weakening the service to expose it publicly.

For the Responses API, configure a tool with `type: "mcp"`, this server's remote `server_url`, an `allowed_tools` list if desired, and approval policy appropriate to the mutation surface.

## Security boundary

`BRAINK_MCP_HMAC_KEY_HEX` is required and must decode to at least 32 bytes. The adapter deliberately refuses to generate an ephemeral production key.

The MCP layer does not duplicate R5 persistence logic. It calls the existing resident classes:

- `SignedEnvelopeAuthority`
- `DomainAuthorityAtomicCoordinator`
- `CheckpointStore`
