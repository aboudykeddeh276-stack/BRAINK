from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


class MCPError(RuntimeError):
    pass


class BRAINKMCPClient:
    """Small deterministic client for the BRAINK MCP ABI.

    This is the software-side adapter used by agents/Codex-style callers.  It does
    not duplicate BRAINK mechanics; it discovers and invokes the MCP tools exposed
    by enterprise.mcp.server, then preserves structured receipts/readback.
    """

    def __init__(self, command: Iterable[str], *, cwd: str | Path | None = None, env: dict[str, str] | None = None):
        self.command = list(command)
        self.cwd = None if cwd is None else str(cwd)
        self.env = env
        self.proc: subprocess.Popen[str] | None = None
        self._next_id = 1
        self.server_info: dict[str, Any] | None = None
        self.protocol_version: str | None = None
        self.tools: dict[str, dict[str, Any]] = {}

    @classmethod
    def local_r23(cls, state_path: str | Path, *, repo_root: str | Path | None = None) -> "BRAINKMCPClient":
        root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
        return cls(
            [sys.executable, "-m", "enterprise.mcp.server", "--state", str(state_path)],
            cwd=root,
            env=env,
        )

    def __enter__(self) -> "BRAINKMCPClient":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> "BRAINKMCPClient":
        if self.proc is not None:
            return self
        self.proc = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            env=self.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        init = self.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "braink-agent-adapter", "version": "1"},
            },
        )
        self.server_info = dict(init.get("serverInfo") or {})
        self.protocol_version = init.get("protocolVersion")
        listed = self.request("tools/list", {})
        self.tools = {tool["name"]: tool for tool in listed.get("tools", [])}
        return self

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.proc is None or self.proc.stdin is None or self.proc.stdout is None:
            raise MCPError("MCP_CLIENT_NOT_STARTED")
        request_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
        self.proc.stdin.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            stderr = self.proc.stderr.read() if self.proc.stderr else ""
            raise MCPError(f"MCP_SERVER_CLOSED:{stderr}")
        response = json.loads(line)
        if response.get("id") != request_id:
            raise MCPError("MCP_RESPONSE_ID_MISMATCH")
        if "error" in response:
            error = response["error"]
            raise MCPError(f"MCP_ERROR:{error.get('code')}:{error.get('message')}")
        return dict(response.get("result") or {})

    def list_tools(self) -> list[dict[str, Any]]:
        return [self.tools[name] for name in sorted(self.tools)]

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if name not in self.tools:
            raise MCPError(f"MCP_TOOL_NOT_DISCOVERED:{name}")
        result = self.request("tools/call", {"name": name, "arguments": arguments or {}})
        if result.get("isError"):
            raise MCPError(f"MCP_TOOL_ERROR:{name}")
        structured = result.get("structuredContent")
        if not isinstance(structured, dict):
            raise MCPError(f"MCP_STRUCTURED_CONTENT_REQUIRED:{name}")
        return structured

    def state(self) -> dict[str, Any]:
        return self.call_tool("braink_r23_state", {})

    def operate(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.call_tool("braink_r23_operate", {"action": action, "payload": payload})
        required = {"status", "state_before_root", "state_after_root", "receipt_root", "descendants", "readback", "blockers"}
        missing = sorted(required - set(result))
        if missing:
            raise MCPError(f"BRAINK_OPERATION_CONTRACT_MISSING:{','.join(missing)}")
        return result

    def receipt(self, receipt_root: str) -> dict[str, Any]:
        return self.call_tool("braink_r23_receipt", {"receipt_root": receipt_root})

    def descendants(self) -> list[str]:
        result = self.call_tool("braink_r23_list_descendants", {})
        return list(result.get("descendants") or [])

    def invoke_with_readback(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.operate(action, payload)
        receipt = self.receipt(result["receipt_root"])
        observed = self.state()
        return {
            "operation": result,
            "receipt_readback": receipt,
            "state_readback": observed,
            "descendants": self.descendants(),
        }

    def close(self) -> None:
        if self.proc is None:
            return
        proc, self.proc = self.proc, None
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        if proc.returncode not in (0, -15):
            stderr = proc.stderr.read() if proc.stderr else ""
            raise MCPError(f"MCP_SERVER_EXIT:{proc.returncode}:{stderr}")
