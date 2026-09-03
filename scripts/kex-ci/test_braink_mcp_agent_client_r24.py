from __future__ import annotations

import json
import tempfile
from pathlib import Path

from enterprise.mcp.client import BRAINKMCPClient, MCPError

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="braink-mcp-agent-r24-") as tmp:
        state = Path(tmp) / "r23-state.json"

        # First agent session: discover the live tool ABI, execute the actual R23
        # process, and follow the returned receipt/descendant addresses.
        with BRAINKMCPClient.local_r23(state, repo_root=ROOT) as client:
            assert client.server_info and client.server_info["name"] == "braink-r24-mcp"
            names = {tool["name"] for tool in client.list_tools()}
            assert {
                "braink_r23_state",
                "braink_r23_operate",
                "braink_r23_receipt",
                "braink_r23_list_descendants",
            } <= names

            created = client.invoke_with_readback(
                "customer.lifecycle.create",
                {
                    "file_id": "CF-AGENT-001",
                    "customer_id": "CUSTOMER-AGENT-001",
                    "consent": {"privacy": True},
                },
            )
            op = created["operation"]
            assert op["status"] == "EXECUTED"
            assert op["state_before_root"] != op["state_after_root"]
            assert created["receipt_readback"]["receipt"]["receipt_root"] == op["receipt_root"]
            assert "customer-file://CF-AGENT-001" in created["descendants"]
            first_root = created["state_readback"]["state_root"]
            first_generation = created["state_readback"]["generation"]

            transitioned = client.invoke_with_readback(
                "customer.lifecycle.transition",
                {"file_id": "CF-AGENT-001", "target": "ACTIVE", "reason": "agent-conformance"},
            )
            assert transitioned["operation"]["status"] == "EXECUTED"
            assert transitioned["state_readback"]["state_root"] != first_root
            assert transitioned["state_readback"]["generation"] > first_generation
            second_root = transitioned["state_readback"]["state_root"]
            second_generation = transitioned["state_readback"]["generation"]

            # The actual resident domain path remains executable through the same
            # agent adapter even when it reaches a real external-actuator boundary.
            deferred = client.invoke_with_readback(
                "domain.public_activation.request",
                {
                    "release_id": "REL-AGENT-001",
                    "domain": "agent.example.invalid",
                    "dns_changes": [],
                    "tls_required": True,
                },
            )
            assert deferred["operation"]["status"] == "DEFERRED_EXTERNAL_ACTUATOR"
            assert deferred["operation"]["blockers"]
            assert "domain-intent://agent.example.invalid" in deferred["descendants"]

            # Client-side discovery is authoritative: an agent cannot silently
            # invoke an operation that the live server did not expose.
            try:
                client.call_tool("shell.exec", {"command": "id"})
            except MCPError as exc:
                assert "MCP_TOOL_NOT_DISCOVERED" in str(exc)
            else:
                raise AssertionError("undiscovered tool was callable")

        # Second independent agent session: prove that the adapter reconnects to
        # the same durable process state rather than a synthetic in-memory mock.
        with BRAINKMCPClient.local_r23(state, repo_root=ROOT) as client2:
            rehydrated = client2.state()
            assert rehydrated["generation"] > second_generation
            assert rehydrated["state_root"] != second_root
            assert rehydrated["counts"]["customer_files"] == 1
            assert rehydrated["counts"]["domain_intents"] == 1
            assert "customer-file://CF-AGENT-001" in client2.descendants()
            assert "domain-intent://agent.example.invalid" in client2.descendants()

            appended = client2.invoke_with_readback(
                "customer.lifecycle.event",
                {
                    "file_id": "CF-AGENT-001",
                    "kind": "COMMUNICATION",
                    "payload": {"channel": "agent", "event": "rehydrated-session"},
                },
            )
            assert appended["operation"]["status"] == "EXECUTED"
            assert appended["state_readback"]["generation"] > rehydrated["generation"]

        persisted = json.loads(state.read_text())
        assert persisted["customer_files"]["CF-AGENT-001"]["state"] == "ACTIVE"
        assert persisted["customer_files"]["CF-AGENT-001"]["communications"][-1]["event"] == "rehydrated-session"
        assert persisted["domain_intents"]["agent.example.invalid"]["state"] == "DEFERRED_EXTERNAL_ACTUATOR"

    print("R24_BRAINK_MCP_AGENT_CLIENT_PASS")


if __name__ == "__main__":
    main()
