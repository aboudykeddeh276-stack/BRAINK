from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def send(proc: subprocess.Popen[str], payload: dict) -> dict:
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    assert line, "MCP server closed stdout"
    return json.loads(line)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="braink-mcp-r24-") as tmp:
        state = Path(tmp) / "r23-state.json"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.Popen(
            [sys.executable, "-m", "enterprise.mcp.server", "--state", str(state)],
            cwd=ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            init = send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "r24-invariant", "version": "1"}}})
            assert init["result"]["serverInfo"]["name"] == "braink-r24-mcp"

            tools = send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            names = {tool["name"] for tool in tools["result"]["tools"]}
            assert {"braink_r23_state", "braink_r23_operate", "braink_r23_receipt", "braink_r23_list_descendants"} <= names

            created = send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "braink_r23_operate", "arguments": {"action": "customer.lifecycle.create", "payload": {"file_id": "CF-MCP-001", "customer_id": "CUSTOMER-001", "consent": {"privacy": True}}}}})
            result = created["result"]["structuredContent"]
            assert result["status"] == "EXECUTED"
            assert result["state_before_root"] != result["state_after_root"]
            assert "customer-file://CF-MCP-001" in result["descendants"]
            receipt_root = result["receipt_root"]
            assert len(receipt_root) == 64

            receipt = send(proc, {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "braink_r23_receipt", "arguments": {"receipt_root": receipt_root}}})
            assert receipt["result"]["structuredContent"]["receipt"]["receipt_root"] == receipt_root

            descendants = send(proc, {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "braink_r23_list_descendants", "arguments": {}}})
            assert "customer-file://CF-MCP-001" in descendants["result"]["structuredContent"]["descendants"]

            deferred = send(proc, {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "braink_r23_operate", "arguments": {"action": "domain.public_activation.request", "payload": {"release_id": "REL-MCP-001", "domain": "mcp.example.invalid", "dns_changes": [], "tls_required": True}}}})
            deferred_result = deferred["result"]["structuredContent"]
            assert deferred_result["status"] == "DEFERRED_EXTERNAL_ACTUATOR"
            assert deferred_result["blockers"]
            assert "domain-intent://mcp.example.invalid" in deferred_result["descendants"]

            denied = send(proc, {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "braink_r23_operate", "arguments": {"action": "shell.exec", "payload": {"command": "id"}}}})
            assert denied["error"]["code"] == -32001
            assert "ACTION_NOT_EXPOSED" in denied["error"]["message"]

            state_readback = send(proc, {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "braink_r23_state", "arguments": {}}})
            summary = state_readback["result"]["structuredContent"]
            assert summary["counts"]["customer_files"] == 1
            assert summary["counts"]["domain_intents"] == 1
            assert "customer_id" not in json.dumps(summary)

            persisted = json.loads(state.read_text())
            assert persisted["customer_files"]["CF-MCP-001"]["customer_id"] == "CUSTOMER-001"
            assert len(persisted["receipts"]) >= 2
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            if proc.returncode not in (0, -15):
                stderr = proc.stderr.read() if proc.stderr else ""
                raise AssertionError(f"MCP server exit {proc.returncode}: {stderr}")

    print("R24_BRAINK_MCP_ADAPTER_PASS")


if __name__ == "__main__":
    main()
