from __future__ import annotations

from pathlib import Path

from runtime.mcp_sdk_environment_server import app


def route_manifest() -> dict[str, object]:
    return {
        "runtime_id": "runtime://keddeh/mcp-sdk-environment",
        "runtime_class": "HTTP_SERVICE",
        "entrypoint": "runtime/mcp_sdk_environment_server.py",
        "health_endpoint": "/health",
        "mcp_endpoint": "/mcp",
        "sdk_manifest": "/sdk/manifest",
        "environment_manifest": "/environment",
        "dependencies": [
            "mcp[cli]>=1.27.2",
            "uvicorn>=0.30",
            "fastapi",
        ],
        "state": "SOURCE_BOUND",
    }


__all__ = ["app", "route_manifest"]
