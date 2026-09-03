from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from mcp.braink_process_adapter.agent_authority_client import BRAINKAgentAuthorityClient
from mcp.braink_process_adapter.backend import BrainkProcessBackend
from mcp.braink_process_adapter.function_contracts import FunctionContractError


def invocation_count(path: Path) -> int:
    with sqlite3.connect(path) as db:
        row=db.execute("SELECT COUNT(*) FROM invocations").fetchone()
    return int(row[0])


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="braink-r7-function-actual-") as td:
        state_dir=Path(td)/"runtime"
        backend=BrainkProcessBackend(state_dir=state_dir,key=bytes.fromhex("22"*32))
        lease=backend.acquire_lease("WORK-R7-ACTUAL","codex-agent",requested_epoch=1)
        assert lease["epoch"]==1

        client=BRAINKAgentAuthorityClient(backend)
        functions=client.function_manifest()
        assert len(functions)==14
        by_cap={row["capability_id"]:row for row in functions}
        assert by_cap["domain.provision"]["invoke_via"]=="braink_invoke_capability"
        assert by_cap["server.release"]["authority"]["requires_approval"] is True
        assert by_cap["vfs.read"]["authority"]["required_scopes"]==["vfs:read"]

        ledger=state_dir/"capability_receipts.sqlite"
        before=invocation_count(ledger)
        try:
            client.invoke_idempotent(
                "domain.provision",
                idempotency_key="r7-domain-1",
                work_id="WORK-R7-ACTUAL",actor_id="codex-agent",lease_epoch=1,
                scopes=["domain:write"],
                payload={"domain":"r7-agent.keddeh","ip":"127.0.0.1"},
            )
        except FunctionContractError as exc:
            assert "missing required parameters" in str(exc)
        else:
            raise AssertionError("typed function contract accepted missing tx_id")
        assert invocation_count(ledger)==before, "invalid typed payload reached governed invocation ledger"

        provision=client.invoke_idempotent(
            "domain.provision",
            idempotency_key="r7-domain-1",
            work_id="WORK-R7-ACTUAL",actor_id="codex-agent",lease_epoch=1,
            scopes=["domain:write"],
            payload={"tx_id":"TX-R7-ACTUAL","domain":"r7-agent.keddeh","ip":"127.0.0.1"},
        )
        assert provision["function_name"]=="braink_domain_provision"
        assert provision["payload"]["owner_scope"]=="KEDDEH_SYSTEMS"
        assert provision["result"]["status"]=="SUCCEEDED"
        assert len(provision["result"]["receipt_root"])==64
        assert invocation_count(ledger)==before+1

        observed=client.invoke_idempotent(
            "domain.observe",
            idempotency_key="r7-observe-1",
            work_id="WORK-R7-ACTUAL",actor_id="codex-agent",lease_epoch=1,
            scopes=["domain:read"],
            payload={"domain":"r7-agent.keddeh"},
        )
        assert observed["function_name"]=="braink_domain_observe"
        assert observed["result"]["status"]=="SUCCEEDED"
        result=observed["result"]["result"]
        assert result and result.get("domain")=="r7-agent.keddeh"

        replay=client.invoke_idempotent(
            "domain.provision",
            idempotency_key="r7-domain-1",
            work_id="WORK-R7-ACTUAL",actor_id="codex-agent",lease_epoch=1,
            scopes=["domain:write"],
            payload={"tx_id":"TX-R7-ACTUAL","domain":"r7-agent.keddeh","ip":"127.0.0.1"},
        )
        assert replay["result"]["status"]=="REPLAYED_SUCCESS"
        assert invocation_count(ledger)==before+2

    print("R7_AGENT_FUNCTION_ACTUAL_PROCESS_PASS")


if __name__=="__main__":
    main()
