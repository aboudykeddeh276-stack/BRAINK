#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from hardening import append_jsonl_fsync, atomic_write_bytes, contained_path

SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _load_ledger(base: Path) -> dict[str, Any]:
    path = contained_path(base, base / "casepath" / "CASEPATH_DYNAMIC_MANAGEMENT_PROCESS_LEDGER_R1.json")
    if not path.exists():
        raise FileNotFoundError(f"Casepath management ledger missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _process_index(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["process_id"]): item for item in ledger.get("processes", []) if item.get("process_id")}


def managed_dispatch(
    *,
    base: Path,
    dispatch_root: Path,
    request: dict[str, Any],
    receipt: Callable[..., dict[str, Any]],
    now: Callable[[], str],
    sha: Callable[[bytes], str],
    action_id: str,
) -> dict[str, Any]:
    target = str(request.get("activeTarget", ""))
    try:
        ledger = _load_ledger(base)
    except Exception as exc:
        return receipt(action_id, "FAIL", False, target, details={"error": "casepath_management_ledger_unavailable", "exception": type(exc).__name__})

    process_id = str(request.get("processId") or "CASEPATH-PROC-001")
    process = _process_index(ledger).get(process_id)
    if process is None:
        return receipt(action_id, "FAIL", False, target, details={"error": "unknown_casepath_process", "processId": process_id})

    authority = str(request.get("authority") or process.get("authority") or "")
    packet_id = str(request.get("packetId") or "")
    queue = request.get("actionQueue", [])
    if not authority or not packet_id or not target or not isinstance(queue, list):
        return receipt(action_id, "FAIL", False, target, details={"error": "authority_packetId_activeTarget_actionQueue_required", "processId": process_id})
    if not SAFE_ID.fullmatch(packet_id):
        return receipt(action_id, "FAIL", False, target, details={"error": "invalid_packet_id", "packetId": packet_id})

    resolved_actions: list[dict[str, Any]] = []
    for index, item in enumerate(queue, start=1):
        if not isinstance(item, dict):
            return receipt(action_id, "FAIL", False, target, details={"error": "actionQueue_items_must_be_objects", "index": index})
        item_process_id = str(item.get("processId") or process_id)
        item_process = _process_index(ledger).get(item_process_id)
        if item_process is None:
            return receipt(action_id, "FAIL", False, target, details={"error": "unknown_casepath_process", "index": index, "processId": item_process_id})
        resolved_actions.append({
            **item,
            "processId": item_process_id,
            "ownerTeam": item_process.get("owner_team"),
            "managementScope": item_process.get("management_scope"),
            "runtimeScope": item_process.get("runtime_scope"),
            "serviceDeliveryScope": item_process.get("service_delivery_scope"),
            "evolutionScope": item_process.get("evolution_scope"),
            "promotionCriterion": item_process.get("promotion_criterion"),
        })

    packet = {
        "packetId": packet_id,
        "activeTarget": target,
        "authority": authority,
        "umbrella": process.get("umbrella"),
        "processId": process_id,
        "processName": process.get("process_name"),
        "ownerTeam": process.get("owner_team"),
        "actionQueue": resolved_actions,
        "proofTarget": request.get("proofTarget"),
        "receivedAt": now(),
        "accountability": {
            "adminScope": process.get("admin_scope"),
            "managementScope": process.get("management_scope"),
            "runtimeScope": process.get("runtime_scope"),
            "serviceDeliveryScope": process.get("service_delivery_scope"),
            "evolutionScope": process.get("evolution_scope"),
            "sectorScienceScope": process.get("sector_science_scope"),
            "readback": process.get("readback", []),
            "failureModes": process.get("failure_modes", []),
            "recovery": process.get("recovery"),
            "promotionCriterion": process.get("promotion_criterion"),
        },
    }

    dispatch_root.mkdir(parents=True, exist_ok=True)
    path = contained_path(dispatch_root, dispatch_root / f"{packet_id}.json")
    before = sha(path.read_bytes()) if path.exists() else None
    raw = json.dumps(packet, indent=2, sort_keys=True).encode("utf-8")
    atomic_write_bytes(path, raw)
    after = sha(path.read_bytes())

    proof_path = contained_path(dispatch_root, dispatch_root / "CASEPATH_MANAGEMENT_PROOF.jsonl")
    proof_before = sha(proof_path.read_bytes()) if proof_path.exists() else None
    proof_event = {
        "event": "CASEPATH_MANAGED_DISPATCH",
        "timestamp": now(),
        "packetId": packet_id,
        "processId": process_id,
        "ownerTeam": process.get("owner_team"),
        "target": target,
        "dispatchHash": after,
        "queueLength": len(resolved_actions),
    }
    proof_row = append_jsonl_fsync(proof_path, proof_event)
    proof_after = sha(proof_path.read_bytes())

    return receipt(
        action_id,
        "MUTATED",
        True,
        target,
        before=before,
        after=after,
        details={
            "path": path.relative_to(base).as_posix(),
            "queueLength": len(resolved_actions),
            "processId": process_id,
            "processName": process.get("process_name"),
            "ownerTeam": process.get("owner_team"),
            "proofPath": proof_path.relative_to(base).as_posix(),
            "proofBeforeHash": proof_before,
            "proofAfterHash": proof_after,
            "proofRow": proof_row,
            "claimBoundary": "Managed dispatch persisted and proved; downstream service actions remain separately executable and separately provable.",
        },
    )
