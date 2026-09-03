from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .backend import BrainkProcessBackend


class AgentAuthorityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResolvedCapability:
    capability_id: str
    sector: str
    owner_repo: str
    operation: str
    risk: str
    required_scopes: tuple[str, ...]
    idempotent: bool
    requires_approval: bool


class BRAINKAgentAuthorityClient:
    """Agent-side adapter derived from the tested R6 enterprise execution path.

    It deliberately has no raw mutation methods. Every invocation resolves the
    live capability manifest first, checks the caller context against the contract,
    and then calls the backend's authoritative invoke_capability() path.
    """

    def __init__(self, backend: BrainkProcessBackend):
        self.backend = backend
        self._manifest: dict[str, ResolvedCapability] = {}
        self.refresh_manifest()

    def refresh_manifest(self) -> list[ResolvedCapability]:
        manifest: dict[str, ResolvedCapability] = {}
        for item in self.backend.capability_manifest():
            cap = ResolvedCapability(
                capability_id=str(item["capability_id"]),
                sector=str(item["sector"]),
                owner_repo=str(item["owner_repo"]),
                operation=str(item["operation"]),
                risk=str(item["risk"]),
                required_scopes=tuple(item.get("required_scopes", ())),
                idempotent=bool(item.get("idempotent")),
                requires_approval=bool(item.get("requires_approval")),
            )
            if cap.capability_id in manifest:
                raise AgentAuthorityError(f"DUPLICATE_CAPABILITY:{cap.capability_id}")
            manifest[cap.capability_id] = cap
        self._manifest = manifest
        return [manifest[key] for key in sorted(manifest)]

    def resolve(self, capability_id: str) -> ResolvedCapability:
        cap = self._manifest.get(capability_id)
        if cap is None:
            raise AgentAuthorityError(f"CAPABILITY_NOT_DISCOVERED:{capability_id}")
        return cap

    def invoke(
        self,
        capability_id: str,
        *,
        work_id: str,
        actor_id: str,
        lease_epoch: int,
        scopes: list[str] | tuple[str, ...],
        payload: dict[str, Any],
        approval_token: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        cap = self.resolve(capability_id)
        supplied = set(scopes)
        missing = sorted(set(cap.required_scopes) - supplied)
        if missing:
            raise AgentAuthorityError(f"MISSING_SCOPE:{','.join(missing)}")
        if cap.requires_approval and not approval_token:
            raise AgentAuthorityError(f"APPROVAL_REQUIRED:{capability_id}")
        if idempotency_key is not None and not cap.idempotent:
            raise AgentAuthorityError(f"IDEMPOTENCY_NOT_ALLOWED:{capability_id}")

        context = {
            "work_id": work_id,
            "actor_id": actor_id,
            "lease_epoch": int(lease_epoch),
            "scopes": sorted(supplied),
            "approval_token": approval_token,
        }
        result = self.backend.invoke_capability(capability_id, context, payload, idempotency_key)
        if not isinstance(result, dict):
            raise AgentAuthorityError("CAPABILITY_RESULT_NOT_STRUCTURED")
        return {
            "contract": {
                "capability_id": cap.capability_id,
                "sector": cap.sector,
                "owner_repo": cap.owner_repo,
                "operation": cap.operation,
                "risk": cap.risk,
                "required_scopes": list(cap.required_scopes),
                "idempotent": cap.idempotent,
                "requires_approval": cap.requires_approval,
            },
            "context": context,
            "result": result,
        }

    def invoke_idempotent(
        self,
        capability_id: str,
        *,
        idempotency_key: str,
        work_id: str,
        actor_id: str,
        lease_epoch: int,
        scopes: list[str] | tuple[str, ...],
        payload: dict[str, Any],
        approval_token: str | None = None,
    ) -> dict[str, Any]:
        cap = self.resolve(capability_id)
        if not cap.idempotent:
            raise AgentAuthorityError(f"CAPABILITY_NOT_IDEMPOTENT:{capability_id}")
        return self.invoke(
            capability_id,
            work_id=work_id,
            actor_id=actor_id,
            lease_epoch=lease_epoch,
            scopes=scopes,
            payload=payload,
            approval_token=approval_token,
            idempotency_key=idempotency_key,
        )
