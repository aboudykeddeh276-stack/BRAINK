from __future__ import annotations

"""Projection adapter for authenticated external connector services.

The connector binding proves an execution carrier exists. It does not make the
connector a source of canonical DomainState truth. Every mutation is driven by
an AUTHORITATIVELY_COMMITTED envelope and requires outside readback.
"""

from pathlib import Path
from typing import Any, Callable, Mapping

from enterprise.orchestration.committed_projection_bridge_r8 import (
    AuthorityClass,
    CallableProjectionAdapter,
    CommittedProjectionBridge,
    ProjectionEnvelope,
    ProjectionReceiptLedger,
    ProjectionSigner,
    Surface,
)
from enterprise.market.connector_service_registry_r25 import registry


def build_connector_adapter(
    *,
    service: str,
    execute: Callable[[str, str, Mapping[str, Any]], Mapping[str, Any]],
    readback: Callable[[str, str, Mapping[str, Any]], Mapping[str, Any]],
) -> CallableProjectionAdapter:
    bindings = registry()
    binding = bindings.get(service)
    if binding is None:
        raise ValueError(f"CONNECTOR_NOT_REGISTERED:{service}")
    if not binding.get("projection_only"):
        raise ValueError(f"CONNECTOR_NOT_PROJECTION_ONLY:{service}")
    if binding.get("authority_class") != AuthorityClass.EXTERNALLY_DELEGATED.value:
        raise ValueError(f"CONNECTOR_AUTHORITY_CLASS_INVALID:{service}")
    if not binding.get("readback_required"):
        raise ValueError(f"CONNECTOR_READBACK_REQUIRED:{service}")

    allowed = set(binding.get("capabilities") or ())

    def apply(envelope: ProjectionEnvelope) -> dict[str, Any]:
        payload = dict(envelope.payload)
        capability = str(payload.pop("capability"))
        if capability not in allowed:
            raise ValueError(f"CONNECTOR_CAPABILITY_NOT_REGISTERED:{service}:{capability}")
        result = dict(execute(service, capability, payload))
        return {
            "source_event_hash": envelope.event_hash,
            "producer_truth_hash": envelope.producer_truth_hash,
            "service": service,
            "capability": capability,
            "provider_result": result,
        }

    def observe(envelope: ProjectionEnvelope, result: Mapping[str, Any]) -> dict[str, Any]:
        observed = dict(readback(service, str(result["capability"]), result))
        return {
            "source_event_hash": envelope.event_hash,
            "producer_truth_hash": envelope.producer_truth_hash,
            "service": service,
            "capability": result["capability"],
            "provider_readback": observed,
        }

    return CallableProjectionAdapter(
        adapter_id=f"CONNECTOR:{service}",
        surface=Surface.CONNECTOR,
        apply_fn=apply,
        readback_fn=observe,
        mutating=True,
        readback_required=True,
    )


def project_external_connector(
    *,
    envelope: Mapping[str, Any],
    service: str,
    key: bytes,
    ledger_path: str | Path,
    execute: Callable[[str, str, Mapping[str, Any]], Mapping[str, Any]],
    readback: Callable[[str, str, Mapping[str, Any]], Mapping[str, Any]],
) -> dict[str, Any]:
    projection = ProjectionEnvelope.from_mapping(envelope)
    if projection.authority_class != AuthorityClass.EXTERNALLY_DELEGATED.value:
        raise ValueError("CONNECTOR_PROJECTION_REQUIRES_EXTERNALLY_DELEGATED_AUTHORITY")
    bridge = CommittedProjectionBridge(
        ProjectionSigner(key),
        ProjectionReceiptLedger(ledger_path),
    )
    return bridge.project(
        projection,
        build_connector_adapter(service=service, execute=execute, readback=readback),
    )
