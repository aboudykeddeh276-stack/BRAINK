from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from enterprise.mcp.governance_r25 import GovernedR23Adapter

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "braink-r25-governed-mcp", "version": "0.1.0"}

TOOLS = [
    {
        "name": "braink_r25_contracts",
        "description": "List governed BRAINK R23 action contracts, including sector, owner, risk, scopes, idempotency and approval requirements.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "braink_r25_operate",
        "description": "Invoke one governed resident R23 action with explicit work/actor context, scopes, lease epoch, approval and idempotency semantics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "payload": {"type": "object"},
                "context": {
                    "type": "object",
                    "properties": {
                        "work_id": {"type": "string"},
                        "actor_id": {"type": "string"},
                        "lease_epoch": {"type": "integer", "minimum": 1},
                        "scopes": {"type": "array", "items": {"type": "string"}},
                        "approval_token": {"type": ["string", "null"]}
                    },
                    "required": ["work_id", "actor_id", "lease_epoch", "scopes"],
                    "additionalProperties": False
                },
                "idempotency_key": {"type": ["string", "null"]}
            },
            "required": ["action", "payload", "context"],
            "additionalProperties": False
        }
    },
    {
        "name": "braink_r25_state",
        "description": "Read bounded durable R23 state through the R25 governed adapter.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}
    },
    {
        "name": "braink_r25_receipt",
        "description": "Read a resident transition receipt by SHA-256 root.",
        "inputSchema": {"type": "object", "properties": {"receipt_root": {"type": "string", "minLength": 64, "maxLength": 64}}, "required": ["receipt_root"], "additionalProperties": False}
    },
    {
        "name": "braink_r25_list_descendants",
        "description": "List durable descendants instantiated by the resident R23 process volume.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}
    }
]


class MCPServerR25:
    def __init__(self, state_path: str | Path):
        self.adapter = GovernedR23Adapter(state_path)

    def call_tool(self, name: str | None, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "braink_r25_contracts": value = {"contracts": self.adapter.contracts()}
        elif name == "braink_r25_operate": value = self.adapter.operate(arguments["action"], arguments["payload"], arguments["context"], arguments.get("idempotency_key"))
        elif name == "braink_r25_state": value = self.adapter.state()
        elif name == "braink_r25_receipt": value = self.adapter.receipt(arguments["receipt_root"])
        elif name == "braink_r25_list_descendants": value = self.adapter.list_descendants()
        else: raise KeyError(f"UNKNOWN_TOOL:{name}")
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return {"content": [{"type": "text", "text": text}], "structuredContent": value, "isError": False}

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method=request.get("method"); rid=request.get("id")
        if rid is None and method == "notifications/initialized": return None
        try:
            if method == "initialize": result={"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {"listChanged": False}}, "serverInfo": SERVER_INFO}
            elif method == "ping": result={}
            elif method == "tools/list": result={"tools": TOOLS}
            elif method == "tools/call":
                params=request.get("params") or {}; result=self.call_tool(params.get("name"), params.get("arguments") or {})
            else: return self.error(rid,-32601,f"METHOD_NOT_FOUND:{method}")
            return {"jsonrpc":"2.0","id":rid,"result":result}
        except PermissionError as exc: return self.error(rid,-32001,str(exc))
        except (KeyError,ValueError,RuntimeError,TypeError) as exc: return self.error(rid,-32602,str(exc))

    @staticmethod
    def error(rid: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc":"2.0","id":rid,"error":{"code":code,"message":message}}


def serve_stdio(state_path: str | Path) -> None:
    server=MCPServerR25(state_path)
    for line in sys.stdin:
        if not line.strip(): continue
        try: response=server.dispatch(json.loads(line))
        except json.JSONDecodeError as exc: response=server.error(None,-32700,f"PARSE_ERROR:{exc.msg}")
        if response is not None:
            sys.stdout.write(json.dumps(response,separators=(",",":"),ensure_ascii=False)+"\n"); sys.stdout.flush()


def main() -> None:
    parser=argparse.ArgumentParser(description="BRAINK R25 governed MCP stdio adapter")
    parser.add_argument("--state",required=True)
    args=parser.parse_args(); serve_stdio(args.state)


if __name__ == "__main__": main()
