from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from enterprise.orchestration.durable_execution_r5 import (
    CheckpointStore,
    DomainAuthorityAtomicCoordinator,
    SignedEnvelopeAuthority,
)
from .sector_bridges import ServerRuntimeBridge, VirtualMemoryBridge
from .capability_catalog import GovernedCapabilityService
from .function_contracts import manifest as function_manifest_projection, validate_payload
from enterprise.orchestration.committed_projection_bridge_r8 import (
    CallableProjectionAdapter,
    CommittedProjectionBridge,
    ProjectionEnvelope,
    ProjectionReceiptLedger,
    ProjectionSigner,
    Surface,
)

LEGAL_ENTITY = {
    "identity": "organisation://the-layna-company",
    "legal_name": "THE LAYNA COMPANY PTY LIMITED",
    "acn": "691036236",
    "abn": "79691036236",
}
OPERATING_IDENTITY = {
    "identity": "business-name://keddeh-systems",
    "business_name": "Keddeh Systems",
    "legal_holder": LEGAL_ENTITY["identity"],
    "operating_authority": "KEDDEH_SYSTEMS",
}


class BrainkProcessBackend:
    """Resident BRAINK mechanics plus one governed enterprise capability invocation path."""

    def __init__(self, state_dir: str | Path | None = None, key: bytes | None = None):
        self.state_dir = Path(state_dir or os.environ.get("BRAINK_MCP_STATE_DIR", "runtime/braink_mcp")).resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.key = key or self._load_key()
        self.authority = SignedEnvelopeAuthority(self.state_dir / "authority_ledger.sqlite", self.key)
        self.domain = DomainAuthorityAtomicCoordinator(
            self.state_dir / "domain_control.sqlite",
            self.state_dir / "domain_authority.sqlite",
        )
        self.servers = ServerRuntimeBridge()
        self.vfs = VirtualMemoryBridge()
        self.capabilities = GovernedCapabilityService(self, self.state_dir / "capability_receipts.sqlite")
        self.projection_bridge = CommittedProjectionBridge(
            ProjectionSigner(self.key),
            ProjectionReceiptLedger(self.state_dir / "projection_receipts.sqlite"),
        )

    @staticmethod
    def _load_key() -> bytes:
        raw = os.environ.get("BRAINK_MCP_HMAC_KEY_HEX", "")
        if not raw:
            raise RuntimeError("BRAINK_MCP_HMAC_KEY_HEX must be configured; no ephemeral production key is generated")
        try:
            key = bytes.fromhex(raw)
        except ValueError as exc:
            raise RuntimeError("BRAINK_MCP_HMAC_KEY_HEX must be valid hex") from exc
        if len(key) < 32:
            raise RuntimeError("BRAINK_MCP_HMAC_KEY_HEX must decode to at least 32 bytes")
        return key

    def resolve_identity(self) -> dict[str, Any]:
        return {
            "legal_entity": LEGAL_ENTITY,
            "operating_identity": OPERATING_IDENTITY,
            "relationship": "BUSINESS_NAME_HELD_BY_LEGAL_ENTITY",
        }

    def create_envelope(self, work_id: str, intent: str, state: dict[str, Any] | None = None, epoch: int = 1) -> dict[str, Any]:
        envelope = {
            "work_id": work_id,
            "organisation_identity": LEGAL_ENTITY["identity"],
            "operating_identity": OPERATING_IDENTITY["identity"],
            "intent": intent,
            "state": state or {},
            "lineage": [],
            "evidence": [],
            "continuation": {"epoch": epoch, "status": "READY"},
        }
        return self.authority.sign(envelope)

    def consume_envelope(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self.authority.consume_once(envelope)
        return {
            "state": "CONSUMED",
            "work_id": envelope["work_id"],
            "epoch": int(envelope["continuation"]["epoch"]),
            "nonce": envelope["nonce"],
        }

    def acquire_lease(self, work_id: str, holder: str, requested_epoch: int | None = None) -> dict[str, Any]:
        epoch = self.authority.acquire_lease(work_id, holder, requested_epoch=requested_epoch)
        return {"work_id": work_id, "holder": holder, "epoch": epoch, "state": "LEASED"}

    def current_lease(self, work_id: str) -> dict[str, Any]:
        row = self.authority.current_lease(work_id)
        if not row:
            return {"work_id": work_id, "state": "UNLEASED"}
        return {"work_id": work_id, "epoch": row[0], "holder": row[1], "state": "LEASED"}

    # Raw resident mechanics. MCP mutation tools should not call these directly.
    def provision_domain_authority(self, tx_id: str, domain: str, ip: str, owner_scope: str = "KEDDEH_SYSTEMS") -> dict[str, Any]:
        result = self.domain.provision(tx_id, domain, owner_scope, ip)
        return {"result": result, "readback": self.domain.observe(domain)}

    def observe_domain_authority(self, domain: str) -> dict[str, Any]:
        return self.domain.observe(domain)

    def write_checkpoint(self, work_id: str, state: dict[str, Any]) -> dict[str, Any]:
        path = self.state_dir / "checkpoints" / f"{work_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        root = CheckpointStore(path, self.key).write(state)
        return {"work_id": work_id, "checkpoint_root": root, "state": "CHECKPOINTED"}

    def read_checkpoint(self, work_id: str) -> dict[str, Any]:
        path = self.state_dir / "checkpoints" / f"{work_id}.json"
        payload = CheckpointStore(path, self.key).read()
        return {"work_id": work_id, "state": "READ_BACK", "checkpoint": payload}

    def server_probe(self) -> dict[str, Any]:
        return self.servers.probe()

    def server_apply(self, operation: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.servers.apply(operation, payload)

    def vfs_bind(self, logical: str, backing: str) -> dict[str, Any]:
        return self.vfs.bind(logical, backing)

    def vfs_write(self, logical: str, backing: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.vfs.write(logical, backing, payload)

    def vfs_read(self, logical: str, backing: str) -> dict[str, Any]:
        return self.vfs.read(logical, backing)

    def vfs_migrate(self, logical: str, current_backing: str, new_backing: str) -> dict[str, Any]:
        return self.vfs.migrate(logical, current_backing, new_backing)

    # Authoritative enterprise surfaces.
    def capability_manifest(self) -> list[dict[str, Any]]:
        return self.capabilities.manifest()

    def function_manifest(self) -> list[dict[str, Any]]:
        """Typed agent-function projection over the governed capability catalog."""
        return function_manifest_projection(self.capability_manifest())

    def apply_committed_projection(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Project one already-committed DomainState transition through MCP governance.

        MCP is an execution surface, not a source of producer truth. The envelope
        must already be signed and AUTHORITATIVELY_COMMITTED. The embedded
        capability still passes through the existing lease/scope/approval/
        idempotency runtime.
        """
        projection = ProjectionEnvelope.from_mapping(envelope)

        def apply(item: ProjectionEnvelope) -> dict[str, Any]:
            payload = dict(item.payload)
            capability_id = str(payload.pop("capability_id"))
            context = dict(payload.pop("context"))
            capability_payload = dict(payload.pop("payload", {}))
            idempotency_key = payload.pop("idempotency_key", None)
            if payload:
                raise ValueError(f"UNEXPECTED_PROJECTION_FIELDS:{sorted(payload)}")
            result = self.invoke_capability(
                capability_id,
                context,
                capability_payload,
                idempotency_key,
            )
            if result.get("status") not in {"SUCCEEDED", "REPLAYED_SUCCESS"}:
                raise RuntimeError(f"CAPABILITY_PROJECTION_FAILED:{result.get('status')}")
            return {
                "source_event_hash": item.event_hash,
                "producer_truth_hash": item.producer_truth_hash,
                "capability_id": capability_id,
                "capability_result": result,
            }

        adapter = CallableProjectionAdapter(
            adapter_id="BRAINK_MCP_CAPABILITY",
            surface=Surface.MCP,
            apply_fn=apply,
            readback_fn=lambda item, result: {
                "source_event_hash": item.event_hash,
                "producer_truth_hash": item.producer_truth_hash,
                "capability_id": result["capability_id"],
                "status": result["capability_result"].get("status"),
                "receipt_root": result["capability_result"].get("receipt_root"),
            },
            mutating=True,
            readback_required=True,
        )
        return self.projection_bridge.project(projection, adapter)

    def projection_reconciliation_debt(self) -> list[dict[str, Any]]:
        return self.projection_bridge.ledger.debt()

    def verify_projection_receipts(self) -> dict[str, Any]:
        return self.projection_bridge.ledger.verify_chain()

    def invoke_capability(
        self,
        capability_id: str,
        context: dict[str, Any],
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        normalized = validate_payload(capability_id, payload)
        return self.capabilities.invoke(capability_id, context, normalized, idempotency_key)
