from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from enterprise.mcp.r23_adapter import ALLOWED_ACTIONS, R23ClosureToolAdapter

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "braink-r24-mcp", "version": "0.1.0"}

TOOLS = [
    {
        "name": "braink_r23_state",
        "description": "Read bounded R23 foundary-closure runtime state without exposing internal customer data.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "braink_r23_operate",
        "description": "Invoke one allowlisted resident R23 closure operation and return receipt, readback, descendants and blockers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": sorted(ALLOWED_ACTIONS)},
                "payload": {"type": "object"},
            },
            "required": ["action", "payload"],
            "additionalProperties": False,
        },
    },
    {
        "name": "braink_r23_receipt",
        "description": "Read a persisted R23 transition receipt by its SHA-256 receipt root.",
        "inputSchema": {
            "type": "object",
            "properties": {"receipt_root": {"type": "string", "minLength": 64, "maxLength": 64}},
            "required": ["receipt_root"],
            "additionalProperties": False,
        },
    },
    {
        "name": "braink_r23_list_descendants",
        "description": "List recursively addressable descendants instantiated in the R23 closure volume.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


class MCPServer:
    def __init__(self, state_path: str | Path):
        self.adapter = R23ClosureToolAdapter(state_path)

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = request.get("method")
        request_id = request.get("id")
        if request_id is None and method == "notifications/initialized":
            return None
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": SERVER_INFO,
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                params = request.get("params") or {}
                result = self.call_tool(params.get("name"), params.get("arguments") or {})
            else:
                return self.error(request_id, -32601, f"METHOD_NOT_FOUND:{method}")
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except PermissionError as exc:
            return self.error(request_id, -32001, str(exc))
        except (KeyError, ValueError, RuntimeError, TypeError) as exc:
            return self.error(request_id, -32602, str(exc))

    def call_tool(self, name: str | None, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "braink_r23_state":
            value = self.adapter.state()
        elif name == "braink_r23_operate":
            value = self.adapter.operate(arguments["action"], arguments["payload"])
        elif name == "braink_r23_receipt":
            value = self.adapter.receipt(arguments["receipt_root"])
        elif name == "braink_r23_list_descendants":
            value = self.adapter.list_descendants()
        else:
            raise KeyError(f"UNKNOWN_TOOL:{name}")
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return {"content": [{"type": "text", "text": text}], "structuredContent": value, "isError": False}

    @staticmethod
    def error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def serve_stdio(state_path: str | Path) -> None:
    server = MCPServer(state_path)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = server.dispatch(request)
        except json.JSONDecodeError as exc:
            response = MCPServer.error(None, -32700, f"PARSE_ERROR:{exc.msg}")
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":"), ensure_ascii=False) + "\n")
            sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="BRAINK MCP stdio adapter")
    parser.add_argument("--state", required=True, help="R23 durable-state JSON path")
    args = parser.parse_args()
    serve_stdio(args.state)


if __name__ == "__main__":
    main()
