from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from mcp.braink_process_adapter.main import app as mcp_app

ENVIRONMENT_ID = "environment://keddeh/mcp-sdk"
RUNTIME_ID = "runtime://keddeh/mcp-sdk-environment"
SDK_ID = "sdk://keddeh/braink"

app = FastAPI(
    title="KEDDEH MCP + SDK Environment",
    version="1.0.0",
    docs_url="/sdk/docs",
    redoc_url=None,
)

app.mount("/mcp", mcp_app)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ACTIVE",
        "environment": ENVIRONMENT_ID,
        "runtime": RUNTIME_ID,
        "mcp_endpoint": "/mcp",
        "sdk_surface": "/sdk",
    }


@app.get("/environment")
def environment() -> dict[str, Any]:
    return {
        "schema": "kex.keddeh.environment.v1",
        "environment_id": ENVIRONMENT_ID,
        "runtime_id": RUNTIME_ID,
        "sdk_id": SDK_ID,
        "mcp": {
            "endpoint": "/mcp",
            "transport": "streamable-http",
            "source": "mcp.braink_process_adapter.main:app",
        },
        "sdk": {
            "manifest": "/sdk/manifest",
            "docs": "/sdk/docs",
            "authority": "BRAINK governed capability contracts",
        },
        "state": "READY",
    }


@app.get("/sdk/manifest")
def sdk_manifest() -> dict[str, Any]:
    return {
        "schema": "kex.keddeh.sdk-manifest.v1",
        "sdk_id": SDK_ID,
        "runtime": RUNTIME_ID,
        "environment": ENVIRONMENT_ID,
        "protocols": ["MCP"],
        "mcp_endpoint": "/mcp",
        "capability_discovery": "/mcp",
        "governance": {
            "invocation": "braink_invoke_capability",
            "typed_contracts": True,
            "idempotency": True,
            "durable_receipts": True,
        },
        "configuration": {
            "required_environment": ["BRAINK_MCP_HMAC_KEY_HEX"],
            "state_directory": os.environ.get("BRAINK_MCP_STATE_DIR", "runtime/braink_mcp"),
        },
    }
