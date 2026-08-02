#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List


@dataclass(frozen=True)
class AgentRegistryRow:
    agent_id: str
    agent_type: str
    owner_plane: str
    purpose: str
    service_bindings: str
    telemetry_signals: str
    deployment_target: str
    promotion_authority: bool
    valid: bool


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_ledger(path: Path, entry: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def read_ledger(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_csv(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def validate_agent(agent: Dict[str, Any], required_fields: List[str]) -> bool:
    if any(field not in agent for field in required_fields):
        return False
    if agent["agent_id"] != "acceptance_harness_agent" and agent.get("promotion_authority") is True:
        return False
    if agent["agent_id"] == "virtual_gpu_projection_agent" and agent.get("promotion_authority") is True:
        return False
    if not agent.get("allowed_actions") or not agent.get("denied_actions"):
        return False
    if "telemetry_signals" not in agent or not isinstance(agent["telemetry_signals"], list):
        return False
    return True


def load_registry(root: Path) -> Dict[str, Any]:
    return read_json(root / "config" / "agent_registry.json")


def evaluate_registry(root: Path) -> List[AgentRegistryRow]:
    registry = load_registry(root)
    required_fields = list(registry["required_agent_fields"])
    rows: List[AgentRegistryRow] = []
    for agent in registry["agent_types"]:
        rows.append(AgentRegistryRow(
            agent_id=agent["agent_id"],
            agent_type=agent["agent_type"],
            owner_plane=agent["owner_plane"],
            purpose=agent["purpose"],
            service_bindings=";".join(agent["service_bindings"]),
            telemetry_signals=";".join(agent["telemetry_signals"]),
            deployment_target=agent["deployment_target"],
            promotion_authority=bool(agent["promotion_authority"]),
            valid=validate_agent(agent, required_fields),
        ))
    return rows


def run_agent_registry(root: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    root = root.expanduser().resolve()
    started = time.time()
    evidence_dir = root / "evidence"
    exports_dir = root / "exports"
    ledger = root / "runtime_volume" / "proof_bundles.ledger"
    outbox_dir = root / "runtime_volume" / "outbox" / "agent_registry"
    outbox_dir.mkdir(parents=True, exist_ok=True)

    registry = load_registry(root)
    rows = evaluate_registry(root)
    all_valid = all(row.valid for row in rows)
    promotion_rules = registry["promotion_rules"]
    promotion_guard_passed = (
        promotion_rules["human_may_promote_pass"] is False
        and promotion_rules["agent_may_promote_pass"] is False
        and promotion_rules["acceptance_harness_may_promote_local_pass"] is True
        and promotion_rules["telemetry_may_observe_not_promote"] is True
        and promotion_rules["virtual_gpu_may_render_not_promote"] is True
    )

    matrix_rows = [asdict(row) for row in rows]
    write_csv(exports_dir / "agent_registry_matrix.csv", matrix_rows)

    pre_receipt = {
        "registry_id": registry["registry_id"],
        "agent_count": len(rows),
        "all_agents_valid": all_valid,
        "promotion_guard_passed": promotion_guard_passed,
        "real_world_abstractions": registry["real_world_abstractions"],
        "timestamp": started,
    }
    receipt_hash = canonical_hash(pre_receipt)
    handoff = {
        "handoff_id": receipt_hash,
        "source": "KEDDEH_V98_AGENT_REGISTRY",
        "payload_path": str(evidence_dir / "agent_registry_receipt.json"),
        "receipt_path": str(ledger),
        "next_target": "acceptance_harness_then_self_hosted_runner",
        "status": "READY_FOR_TARGET_HOST_EXECUTION" if all_valid and promotion_guard_passed else "FAILED_CLOSED",
        "created_at": started,
    }
    outbox_path = outbox_dir / f"{receipt_hash}.handoff.json"
    write_json(outbox_path, handoff)
    ledger_entry = {
        "type": "agent_registry_receipt",
        "entry_hash": receipt_hash,
        "payload": pre_receipt,
        "outbox_manifest": str(outbox_path),
    }
    append_ledger(ledger, ledger_entry)
    ledger_readback = any(entry.get("entry_hash") == receipt_hash for entry in read_ledger(ledger))

    final = {
        "version": registry["version"],
        "registry_id": registry["registry_id"],
        "status": "LOCAL_PASS" if all_valid and promotion_guard_passed and ledger_readback else "LOCAL_FAIL",
        "agent_count": len(rows),
        "all_agents_valid": all_valid,
        "promotion_guard_passed": promotion_guard_passed,
        "ledger_readback": ledger_readback,
        "outbox_manifest": str(outbox_path),
        "hash_used_as_functional_proof": False,
        "telemetry_promotes_correctness": False,
        "virtual_gpu_promotes_correctness": False,
        "timestamp": started,
    }
    if emit_receipt:
        write_json(evidence_dir / "agent_registry_receipt.json", final)
    return final


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    result = run_agent_registry(Path(args.root), emit_receipt=args.emit_receipt)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "LOCAL_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
