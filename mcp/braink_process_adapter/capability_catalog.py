from __future__ import annotations
from typing import Any
from .capability_runtime import (
    CapabilityContract, CapabilityRegistry, CapabilityRuntime,
    InvocationContext, ReceiptLedger, Risk,
)


def build_registry(backend) -> CapabilityRegistry:
    reg=CapabilityRegistry()

    def add(cid,sector,repo,operation,risk,scopes,idempotent,handler,approval=False):
        reg.register(CapabilityContract(
            capability_id=cid, sector=sector, owner_repo=repo, operation=operation,
            risk=risk, required_scopes=tuple(scopes), idempotent=idempotent,
            requires_approval=approval
        ), handler)

    add("identity.resolve","LEGAL_GOVERNANCE","GENERAL-GOVERNANCE-","RESOLVE",Risk.READ,
        ["identity:read"],True,lambda p: backend.resolve_identity())

    add("domain.observe","DOMAIN_AUTHORITY","BRAINK","OBSERVE",Risk.READ,
        ["domain:read"],True,lambda p: backend.observe_domain_authority(p["domain"]))
    add("domain.provision","DOMAIN_AUTHORITY","BRAINK","PROVISION",Risk.MUTATE,
        ["domain:write"],True,lambda p: backend.provision_domain_authority(
            p["tx_id"],p["domain"],p["ip"],p.get("owner_scope","KEDDEH_SYSTEMS")))

    add("checkpoint.read","BRAINK","BRAINK","READ_CHECKPOINT",Risk.READ,
        ["checkpoint:read"],True,lambda p: backend.read_checkpoint(p["work_id"]))
    add("checkpoint.write","BRAINK","BRAINK","WRITE_CHECKPOINT",Risk.MUTATE,
        ["checkpoint:write"],True,lambda p: backend.write_checkpoint(p["work_id"],p["state"]))

    add("server.probe","SERVERS","SERVERS-KEDDEHSYSTEMS","PROBE",Risk.READ,
        ["server:read"],True,lambda p: backend.server_probe())
    add("server.validate_origin","SERVERS","SERVERS-KEDDEHSYSTEMS","VALIDATE_ORIGIN",Risk.READ,
        ["server:read"],True,lambda p: backend.server_apply("VALIDATE_ORIGIN",p))
    add("server.readback","SERVERS","SERVERS-KEDDEHSYSTEMS","READBACK",Risk.READ,
        ["server:read"],True,lambda p: backend.server_apply("READBACK",p))
    add("server.amend","SERVERS","SERVERS-KEDDEHSYSTEMS","AMEND",Risk.MUTATE,
        ["server:write"],True,lambda p: backend.server_apply("AMEND",p),approval=True)
    add("server.release","SERVERS","SERVERS-KEDDEHSYSTEMS","RELEASE",Risk.DESTRUCTIVE,
        ["server:release"],False,lambda p: backend.server_apply("RELEASE",p),approval=True)

    add("vfs.bind","K_DRIVE_VFS","VIRTUALISED_MEMORY","BIND",Risk.MUTATE,
        ["vfs:write"],True,lambda p: backend.vfs_bind(p["logical"],p["backing"]))
    add("vfs.read","K_DRIVE_VFS","VIRTUALISED_MEMORY","READ",Risk.READ,
        ["vfs:read"],True,lambda p: backend.vfs_read(p["logical"],p["backing"]))
    add("vfs.write","K_DRIVE_VFS","VIRTUALISED_MEMORY","WRITE",Risk.MUTATE,
        ["vfs:write"],True,lambda p: backend.vfs_write(p["logical"],p["backing"],p["payload"]))
    add("vfs.migrate","K_DRIVE_VFS","VIRTUALISED_MEMORY","MIGRATE",Risk.MUTATE,
        ["vfs:migrate"],True,lambda p: backend.vfs_migrate(
            p["logical"],p["current_backing"],p["new_backing"]),approval=True)

    return reg


class GovernedCapabilityService:
    def __init__(self, backend, ledger_path):
        self.registry=build_registry(backend)
        self.runtime=CapabilityRuntime(ReceiptLedger(ledger_path),self.registry)

    def manifest(self):
        return self.registry.manifest()

    def invoke(self, capability_id: str, context: dict[str,Any], payload: dict[str,Any],
               idempotency_key: str|None=None):
        ctx=InvocationContext(
            work_id=context["work_id"],
            actor_id=context["actor_id"],
            lease_epoch=int(context["lease_epoch"]),
            scopes=tuple(context.get("scopes",[])),
            approval_token=context.get("approval_token"),
        )
        return self.runtime.invoke(capability_id,ctx,payload,idempotency_key)
