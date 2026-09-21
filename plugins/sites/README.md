# @Sites Plugin

Portable Agent Plugin package for the BRAINK × KEX Sites control plane.

The package follows the current Agent Plugins structure: `plugin.json`, `mcp.json`, and `skills/sites/SKILL.md`. The MCP server is `server/mcp_server.py`.

## Tool surface
`sites_list`, `site_get`, `site_create`, `domain_bind`, `version_create`, `deploy`, `public_readback`, `ledger_verify`, `estate_import`.

## Local MCP
```
pip install -r server/requirements.txt
python server/mcp_server.py
```

The checked-in `mcp.json` points at `http://127.0.0.1:8000/mcp` for local/desktop development. ChatGPT web requires a registered reachable HTTPS MCP endpoint (or supported secure tunnel) before @Sites can become an installed callable plugin in that web environment. Do not replace the URL with a guessed public endpoint.

Once the server has a real HTTPS endpoint, replace only `mcpServers.sites.url` with that endpoint, register it in ChatGPT Developer Mode, then bind the resulting app ID to the plugin package. Site identity and execution semantics remain unchanged.
