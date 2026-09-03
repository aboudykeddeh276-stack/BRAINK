from __future__ import annotations

import os
import tempfile
from pathlib import Path

from mcp.braink_process_adapter.agent_authority_client import BRAINKAgentAuthorityClient, AgentAuthorityError
from mcp.braink_process_adapter.backend import BrainkProcessBackend
from mcp.braink_process_adapter.capability_runtime import AuthorizationError


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="braink-r6-agent-actual-") as td:
        state_dir=Path(td)/"runtime"
        key=bytes.fromhex("11"*32)
        backend=BrainkProcessBackend(state_dir=state_dir,key=key)
        lease=backend.acquire_lease("WORK-R6-ACTUAL","codex-agent",requested_epoch=1)
        assert lease["state"]=="LEASED" and lease["epoch"]==1

        client=BRAINKAgentAuthorityClient(backend)
        manifest=client.refresh_manifest()
        assert len(manifest)==14
        assert client.resolve("domain.provision").owner_repo=="BRAINK"
        assert client.resolve("server.release").requires_approval is True

        try:
            client.invoke(
                "domain.provision",
                work_id="WORK-R6-ACTUAL",actor_id="codex-agent",lease_epoch=1,
                scopes=["domain:read"],
                payload={"tx_id":"TX-R6-ACTUAL","domain":"r6-agent.keddeh","ip":"127.0.0.1"},
                idempotency_key="domain-provision-1",
            )
        except AgentAuthorityError as exc:
            assert "MISSING_SCOPE" in str(exc)
        else:
            raise AssertionError("agent adapter bypassed scope contract")

        provision=client.invoke_idempotent(
            "domain.provision",
            idempotency_key="domain-provision-1",
            work_id="WORK-R6-ACTUAL",actor_id="codex-agent",lease_epoch=1,
            scopes=["domain:write"],
            payload={"tx_id":"TX-R6-ACTUAL","domain":"r6-agent.keddeh","ip":"127.0.0.1"},
        )
        assert provision["result"]["status"]=="SUCCEEDED"
        assert len(provision["result"]["receipt_root"])==64
        readback=backend.observe_domain_authority("r6-agent.keddeh")
        assert readback

        replay=client.invoke_idempotent(
            "domain.provision",
            idempotency_key="domain-provision-1",
            work_id="WORK-R6-ACTUAL",actor_id="codex-agent",lease_epoch=1,
            scopes=["domain:write"],
            payload={"tx_id":"TX-R6-ACTUAL","domain":"r6-agent.keddeh","ip":"127.0.0.1"},
        )
        assert replay["result"]["status"]=="REPLAYED_SUCCESS"

        backend.acquire_lease("WORK-R6-ACTUAL","successor-agent",requested_epoch=2)
        try:
            backend.invoke_capability(
                "domain.observe",
                {"work_id":"WORK-R6-ACTUAL","actor_id":"codex-agent","lease_epoch":1,"scopes":["domain:read"]},
                {"domain":"r6-agent.keddeh"},
                "stale-observe",
            )
        except AuthorizationError:
            pass
        else:
            raise AssertionError("stale lease epoch remained authoritative")

        # The resident server bridge is deliberately unbound in this qualification.
        # The authority plane must record that as FAILED, not convert it to SUCCEEDED.
        failed=backend.invoke_capability(
            "server.probe",
            {"work_id":"WORK-R6-ACTUAL","actor_id":"successor-agent","lease_epoch":2,"scopes":["server:read"]},
            {},
            "server-probe-unbound",
        )
        assert failed["status"]=="FAILED"
        assert failed["error_type"]=="CapabilityExecutionRejected"

        assert not hasattr(client,"server_apply")
        assert not hasattr(client,"vfs_write")
        assert not hasattr(client,"provision_domain_authority")

        ledger=state_dir/"capability_receipts.sqlite"
        assert ledger.exists() and ledger.stat().st_size>0

    print("R6_AGENT_AUTHORITY_ACTUAL_PROCESS_PASS")


if __name__=="__main__":
    main()
