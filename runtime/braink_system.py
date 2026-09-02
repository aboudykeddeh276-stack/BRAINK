from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import hashlib

from .braink_core import (
    BRAINK_ROOT_SLOT, SERVICE_ROOT_SLOT, MUTATION_SLOT,
    BlockFileController, BrainkRoot, MachineIdentity, ObjectEnvelope,
    Replicator, Reconciler, ServiceDescriptor, ServiceFabric,
    IntegrityError,
)

DEFAULT_SERVICES = {
    "SERVER_ROOT": ("LEX://SERVER/GLOBAL", "SERVER"),
    "DOMAIN_ROOT": ("LEX://DOMAIN/keddeh.com", "DOMAIN"),
    "DNS_ROOT": ("LEX://DNS/keddeh.com", "DNS"),
    "REGISTRAR_ROOT": ("LEX://REGISTRAR/keddeh.com", "REGISTRAR"),
    "TLS_ROOT": ("LEX://TLS/keddeh.com", "TLS"),
    "CLOUD_ROOT": ("LEX://CLOUD/BRAINK/GLOBAL", "CLOUD"),
}

class MachineRuntime:
    """Stable BRAINK machine API. R8-R15 remain evidence/migration fixtures around this contract."""
    SCHEMA = "braink.machine.runtime.v1"

    def __init__(self, disk: Path):
        self.disk = Path(disk)

    @staticmethod
    def derive_child_identity(parent: MachineIdentity, ordinal: int) -> MachineIdentity:
        material = f"{parent.machine_id}|{parent.braink_id}|child:{ordinal}".encode()
        suffix = hashlib.sha256(material).hexdigest()[:12].upper()
        machine_id = f"KEX-MACHINE-{ordinal+1:03d}-{suffix}"
        braink_id = f"BRAINK::{machine_id}"
        lineage = f"{parent.lineage_root}::DESCENDANT::{suffix}"
        return MachineIdentity(machine_id, braink_id, lineage, parent.machine_id, parent.braink_id)

    @classmethod
    def create(cls, disk: Path, identity: MachineIdentity, *, disk_bytes: int = 64*1024*1024) -> "MachineRuntime":
        root = BrainkRoot(
            identity=identity,
            medium_root=f"DEVICE://{identity.machine_id}/STORAGE/BLOCK0",
            controller_root=f"KEX_STORAGE_CONTROLLER://{identity.machine_id}",
            storage_root=f"KEX://MACHINE/{identity.machine_id}/STORAGE/",
            vfs_root=f"KEX://VFS/{identity.machine_id}/",
            vfs_role="RESOLVER_ONLY",
            network_root=f"LEX://BRAINK/{identity.machine_id}",
            vector_root=f"VEC://MACHINE/{identity.machine_id}/LOCAL",
            observer_root=f"OBS://BRAINK/{identity.machine_id}",
            proof_root=f"PROOF://BRAINK/{identity.machine_id}",
        )
        root.validate()
        with BlockFileController(disk, disk_bytes=disk_bytes, create=True) as c:
            root_digest = c.write_object(BRAINK_ROOT_SLOT, {**asdict(root), "identity": asdict(root.identity)})
            c.write_object(0, {
                "schema": cls.SCHEMA,
                "machine_id": identity.machine_id,
                "braink_id": identity.braink_id,
                "lineage_root": identity.lineage_root,
                "braink_root_slot": BRAINK_ROOT_SLOT,
                "braink_root_sha256": root_digest,
                "state": "BRAINK_RESIDENT",
            })
            c.sync()
        return cls(disk)

    def boot(self) -> BrainkRoot:
        with BlockFileController(self.disk) as c:
            superblock = c.read_object(0)
            if not superblock: raise IntegrityError("missing superblock")
            root_block = c.read_object(superblock["value"]["braink_root_slot"])
            if not root_block: raise IntegrityError("missing BRAINK root")
            if root_block["sha256"] != superblock["value"]["braink_root_sha256"]:
                raise IntegrityError("BRAINK root digest mismatch")
            d = root_block["value"]
            identity = MachineIdentity(**d["identity"])
            root = BrainkRoot(identity=identity, **{k:v for k,v in d.items() if k != "identity"})
            root.validate()
            if identity.machine_id != superblock["value"]["machine_id"] or identity.braink_id != superblock["value"]["braink_id"]:
                raise IntegrityError("superblock/root identity mismatch")
            return root

    def install_default_services(self) -> ServiceFabric:
        root = self.boot()
        services = {}
        for name, (lexical, kind) in DEFAULT_SERVICES.items():
            services[name] = ServiceDescriptor(
                object_type=name,
                lexical_id=lexical,
                vector_id=f"VEC://{root.identity.machine_id}/{kind}/LOCAL",
                route_id=f"KEX://MACHINE/{root.identity.machine_id}/{kind}/",
                adapter_id=f"BRAINK_{kind}_ADAPTER_V1",
                authority_class="INTERNAL" if kind in {"SERVER","CLOUD","DOMAIN"} else "INTERNAL_STATE_EXTERNAL_AUTHORITY_SEPARATE",
            )
        payload = {k: asdict(v) for k,v in services.items()}
        with BlockFileController(self.disk) as c:
            c.write_object(SERVICE_ROOT_SLOT, {
                "schema":"braink.service-fabric.v1",
                "machine_id":root.identity.machine_id,
                "braink_id":root.identity.braink_id,
                "lineage_root":root.identity.lineage_root,
                "services":payload,
            })
            c.sync()
        return ServiceFabric(root.identity, services)

    def load_services(self) -> ServiceFabric:
        root = self.boot()
        with BlockFileController(self.disk) as c:
            block=c.read_object(SERVICE_ROOT_SLOT)
        if not block: raise IntegrityError("service fabric not installed")
        p=block["value"]
        if p["machine_id"] != root.identity.machine_id or p["lineage_root"] != root.identity.lineage_root:
            raise IntegrityError("service fabric identity mismatch")
        services={k:ServiceDescriptor(**v) for k,v in p["services"].items()}
        return ServiceFabric(root.identity, services)

    def write_state(self, envelope: ObjectEnvelope) -> str:
        envelope.verify()
        with BlockFileController(self.disk) as c:
            digest=c.write_object(MUTATION_SLOT, asdict(envelope)); c.sync(); return digest

    def read_state(self) -> ObjectEnvelope | None:
        with BlockFileController(self.disk) as c:
            block=c.read_object(MUTATION_SLOT)
        if not block: return None
        env=ObjectEnvelope(**block["value"]); env.verify(); return env

class FabricRuntime:
    def __init__(self, machines: list[MachineRuntime]):
        if not machines: raise ValueError("fabric requires at least one machine")
        self.machines=machines

    def resolve(self, lexical_id: str):
        results=[]
        for m in self.machines:
            try:
                svc=m.load_services().resolve(lexical_id)
                results.append((m.boot().identity, svc))
            except (IntegrityError, FileNotFoundError):
                continue
        if not results: raise IntegrityError(f"no available service for {lexical_id}")
        return results

    def replicate_state(self, source: MachineRuntime, destinations: list[MachineRuntime]) -> list[str]:
        env=source.read_state()
        if env is None: raise IntegrityError("source has no state object")
        receipts=[]
        for dst in destinations:
            lineage=dst.boot().identity.lineage_root
            replica=Replicator.replicate(env,lineage)
            receipts.append(dst.write_state(replica))
        return receipts

    def reconcile_state(self, local: MachineRuntime, remote: MachineRuntime) -> str:
        l=local.read_state(); r=remote.read_state()
        if l is None or r is None: raise IntegrityError("both machines need state")
        merged=Reconciler.reconcile(l,r)
        return local.write_state(merged)
