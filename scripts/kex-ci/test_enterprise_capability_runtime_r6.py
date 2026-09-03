from __future__ import annotations

from pathlib import Path
import tempfile

from mcp.braink_process_adapter.capability_catalog import GovernedCapabilityService
from mcp.braink_process_adapter.capability_runtime import (
    ApprovalRequired,
    AuthorizationError,
    CircuitOpen,
    IdempotencyConflict,
)


class Backend:
    def __init__(self):
        self.calls=[]
        self.failures=0

    def resolve_identity(self): self.calls.append("identity"); return {"identity":"keddeh"}
    def observe_domain_authority(self,d): self.calls.append(("observe",d)); return {"domain":d}
    def provision_domain_authority(self,*a): self.calls.append(("provision",a)); return {"state":"COMMITTED"}
    def read_checkpoint(self,w): self.calls.append(("cpread",w)); return {"state":"READ"}
    def write_checkpoint(self,w,s): self.calls.append(("cpwrite",w)); return {"state":"CHECKPOINTED"}
    def server_probe(self): self.calls.append("probe"); return {"status":"READY"}
    def server_apply(self,op,p): self.calls.append((op,p)); return {"status":"EXECUTED","operation":op}
    def vfs_bind(self,l,b): self.calls.append(("bind",l,b)); return {"status":"BOUND"}
    def vfs_read(self,l,b): self.calls.append(("read",l,b)); return {"status":"READ"}
    def vfs_write(self,l,b,p): self.calls.append(("write",l,b)); return {"status":"COMMITTED"}
    def vfs_migrate(self,l,a,b): self.calls.append(("migrate",l,a,b)); return {"status":"COMMITTED"}


def ctx(scopes,approval=None):
    return {
        "work_id":"WORK-R6-TEST",
        "actor_id":"agent-A",
        "lease_epoch":4,
        "scopes":scopes,
        "approval_token":approval,
    }


def main():
    with tempfile.TemporaryDirectory() as td:
        backend=Backend()
        svc=GovernedCapabilityService(backend,Path(td)/"receipts.sqlite")
        manifest=svc.manifest()
        assert len(manifest)==14
        assert len({x["capability_id"] for x in manifest})==14

        observed=svc.invoke("domain.observe",ctx(["domain:read"]),{"domain":"braink.com.au"},"observe-1")
        assert observed["status"]=="SUCCEEDED"

        try:
            svc.invoke("domain.provision",ctx(["domain:read"]),{"tx_id":"T","domain":"d","ip":"127.0.0.1"},"p1")
        except AuthorizationError:
            pass
        else:
            raise AssertionError("domain.provision bypassed scope authorization")

        try:
            svc.invoke("server.amend",ctx(["server:write"]),{"origin":"o","target":"t","patch_id":"p"},"a1")
        except ApprovalRequired:
            pass
        else:
            raise AssertionError("server.amend bypassed approval")

        approved=svc.invoke("server.amend",ctx(["server:write"],"approval://test"),{"origin":"o","target":"t","patch_id":"p"},"a1")
        assert approved["status"]=="SUCCEEDED"

        first=svc.invoke("vfs.write",ctx(["vfs:write"]),{"logical":"L","backing":"B","payload":{"a":1}},"vfs-1")
        replay=svc.invoke("vfs.write",ctx(["vfs:write"]),{"logical":"L","backing":"B","payload":{"a":1}},"vfs-1")
        assert first["status"]=="SUCCEEDED" and replay["status"]=="REPLAYED_SUCCESS"

        try:
            svc.invoke("vfs.write",ctx(["vfs:write"]),{"logical":"L","backing":"B","payload":{"a":2}},"vfs-1")
        except IdempotencyConflict:
            pass
        else:
            raise AssertionError("conflicting idempotent replay accepted")

        try:
            svc.invoke("vfs.migrate",ctx(["vfs:migrate"]),{"logical":"L","current_backing":"A","new_backing":"B"},"m1")
        except ApprovalRequired:
            pass
        else:
            raise AssertionError("vfs.migrate bypassed approval")

        print("R6 enterprise capability controls PASS")


if __name__=="__main__":
    main()
