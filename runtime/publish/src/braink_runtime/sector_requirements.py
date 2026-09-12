from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class SectorRequirement:
    requirement_id: str
    sector: str
    layer: str
    requirement: str
    mandatory: bool
    evidence_required: str


NETWORK_FABRIC_REQUIREMENTS: tuple[SectorRequirement, ...] = (
    SectorRequirement("REQ-NET-001", "NETWORK_FABRIC", "U44", "Deterministic router / shared carrier", True, "ROUTE_READBACK"),
    SectorRequirement("REQ-NET-002", "NETWORK_FABRIC", "U46", "Cryptographic fabric transport", True, "AUTHENTICATED_FRAME_READBACK"),
    SectorRequirement("REQ-NET-003", "NETWORK_FABRIC", "U47", "Dynamic key rotation", True, "ROTATION_READBACK"),
    SectorRequirement("REQ-NET-004", "NETWORK_FABRIC", "U47", "Authenticated frame tags / tamper evidence", True, "TAG_VERIFY_READBACK"),
    SectorRequirement("REQ-NET-005", "NETWORK_FABRIC", "U47", "Replay / sequence window protection", True, "REPLAY_REJECTION_TEST"),
    SectorRequirement("REQ-NET-006", "NETWORK_FABRIC", "U47", "Admission contract", True, "ADMISSION_PASS"),
    SectorRequirement("REQ-NET-007", "NETWORK_FABRIC", "U47", "Upgrade path", True, "UPGRADE_READBACK"),
    SectorRequirement("REQ-NET-008", "NETWORK_FABRIC", "U47", "Rollback path", True, "ROLLBACK_READBACK"),
    SectorRequirement("REQ-NET-009", "NETWORK_FABRIC", "U47", "Deterministic structured logging", True, "LOG_READBACK"),
)

SECTORS: dict[str, tuple[SectorRequirement, ...]] = {
    "NETWORK_FABRIC": NETWORK_FABRIC_REQUIREMENTS,
}


def requirements_for_sector(sector: str, *, through_layer: str | None = None) -> tuple[SectorRequirement, ...]:
    """Return the complete mandatory requirement set for a sector.

    A caller may scope the terminal layer (for example U47), but cannot select
    individual mandatory requirements from inside that scope.
    """
    key = sector.strip().upper()
    requirements = SECTORS.get(key)
    if requirements is None:
        raise KeyError(f"UNKNOWN_SECTOR:{key}")
    if through_layer is None:
        return requirements

    layer = through_layer.strip().upper()
    order: list[str] = []
    for req in requirements:
        if req.layer not in order:
            order.append(req.layer)
    if layer not in order:
        raise KeyError(f"UNKNOWN_LAYER:{key}:{layer}")
    terminal = order.index(layer)
    allowed = set(order[: terminal + 1])
    return tuple(req for req in requirements if req.layer in allowed)


def qualify_sector(
    sector: str,
    receipts: Mapping[str, str | None],
    *,
    through_layer: str | None = None,
) -> dict:
    required = requirements_for_sector(sector, through_layer=through_layer)
    missing: list[dict[str, str]] = []
    satisfied: list[dict[str, str]] = []

    for req in required:
        if not req.mandatory:
            continue
        receipt = str(receipts.get(req.requirement_id) or "").strip()
        row = {
            "requirement_id": req.requirement_id,
            "layer": req.layer,
            "requirement": req.requirement,
            "evidence_required": req.evidence_required,
        }
        if receipt:
            satisfied.append({**row, "receipt": receipt})
        else:
            missing.append(row)

    return {
        "schema": "braink.kex.sector-qualification.v1",
        "sector": sector.strip().upper(),
        "through_layer": through_layer.strip().upper() if through_layer else None,
        "mandatory_total": len([r for r in required if r.mandatory]),
        "mandatory_satisfied": len(satisfied),
        "mandatory_missing": len(missing),
        "status": "QUALIFIED" if not missing else "BLOCKED_MANDATORY_REQUIREMENTS",
        "satisfied": satisfied,
        "missing": missing,
        "selection_policy": "ALL_MANDATORY_REQUIREMENTS_IN_SELECTED_SECTOR_SCOPE",
    }
