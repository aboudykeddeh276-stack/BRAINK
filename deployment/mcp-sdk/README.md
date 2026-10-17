# KEDDEH MCP + SDK public server

This deployment target runs the existing BRAINK MCP capability adapter behind the KEDDEH MCP + SDK environment server.

Runtime:
- runtime://keddeh/mcp-sdk-environment
- environment://keddeh/mcp-sdk
- sdk://keddeh/braink

Public routes:
- /health
- /environment
- /sdk/manifest
- /sdk/docs
- /mcp

Required production secret:
- BRAINK_MCP_HMAC_KEY_HEX

Persistent state:
- BRAINK_MCP_STATE_DIR=/data/braink_mcp

The deployment image is built from the repository root so the existing enterprise, MCP and runtime modules remain available. No alternate capability authority is introduced.
