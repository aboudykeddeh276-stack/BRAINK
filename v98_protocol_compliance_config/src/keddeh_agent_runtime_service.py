#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class AuthorizationDecision:
    agent_id: str
    action: str
    service_id: str
    authorized: bool
    reason: str


@dataclass(frozen=True)
class WorkOrderReceipt:
    work_order_id: str
    agent_id: str
    action: str
    service_id: str
    authorized: bool
    reason: str
    executed: bool
    result: Dict[str, Any]
    receipt_path: str
    ledger_path: str
    outbox_manifest: str
    timestamp: float


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


class AgentRuntimeService:
    """Executable service router for the V98 Agent Registry.

    This is deliberately not a manifest reader only. It accepts a concrete work order,
    authorizes it against the registry, performs a bounded local operation, writes a
    receipt, reads the ledger back, and emits an outbox handoff. It never executes
    arbitrary shell commands and it never allows an agent to self-promote.
    """

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.registry = read_json(self.root / "config" / "agent_registry.json")
        self.services = read_json(self.root / "config" / "service_protocols.json")["services"]
        self.evidence_dir = self.root / "evidence"
        self.ledger_path = self.root / "runtime_volume" / "proof_bundles.ledger"
        self.outbox_dir = self.root / "runtime_volume" / "outbox" / "agent_runtime"

    def agents(self) -> List[Dict[str, Any]]:
        return list(self.registry["agent_types"])

    def service_ids(self) -> List[str]:
        return [service["service_id"] for service in self.services]

    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        for agent in self.agents():
            if agent["agent_id"] == agent_id:
                return agent
        raise KeyError(f"unknown agent_id: {agent_id}")

    def get_service(self, service_id: str) -> Dict[str, Any]:
        for service in self.services:
            if service["service_id"] == service_id:
                return service
        raise KeyError(f"unknown service_id: {service_id}")

    def authorize(self, agent_id: str, action: str, service_id: str) -> AuthorizationDecision:
        try:
            agent = self.get_agent(agent_id)
        except KeyError as exc:
            return AuthorizationDecision(agent_id, action, service_id, False, str(exc))

        denied_actions = set(agent.get("denied_actions", []))
        allowed_actions = set(agent.get("allowed_actions", []))
        service_bindings = set(agent.get("service_bindings", []))

        if action in denied_actions:
            return AuthorizationDecision(agent_id, action, service_id, False, "action_explicitly_denied")
        if action not in allowed_actions:
            return AuthorizationDecision(agent_id, action, service_id, False, "action_not_allowed")
        if action == "promote_local_pass" and agent_id != "acceptance_harness_agent":
            return AuthorizationDecision(agent_id, action, service_id, False, "promotion_reserved_for_acceptance_harness")
        if service_id not in service_bindings and service_id not in {"agent_runtime_service", "agent_registry_service"}:
            return AuthorizationDecision(agent_id, action, service_id, False, "service_not_bound_to_agent")
        return AuthorizationDecision(agent_id, action, service_id, True, "authorized")

    def bounded_operation(self, action: str, service_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Perform bounded local work without arbitrary command execution."""
        if action in {"review_receipts", "execute_tests", "readback_ledger", "emit_handoff", "write_receipt", "execute_service_contract", "run_state_transition"}:
            service_known = service_id in self.service_ids() or service_id in {"agent_runtime_service", "agent_registry_service"}
            return {
                "operation": action,
                "service_id": service_id,
                "service_known": service_known,
                "known_services": len(self.service_ids()),
                "known_agents": len(self.agents()),
                "payload_keys": sorted(payload.keys()),
            }
        if action in {"edit_source", "write_tests", "create_pr", "repair_defects", "run_local_commands_when_available"}:
            return {
                "operation": action,
                "service_id": service_id,
                "bounded": True,
                "note": "implementation action recorded as a work order; repository mutation remains Git/PR controlled",
                "payload_keys": sorted(payload.keys()),
            }
        return {
            "operation": action,
            "service_id": service_id,
            "bounded": True,
            "payload_keys": sorted(payload.keys()),
        }

    def execute_work_order(self, agent_id: str, action: str, service_id: str, payload: Optional[Dict[str, Any]] = None) -> WorkOrderReceipt:
        payload = payload or {}
        started = time.time()
        decision = self.authorize(agent_id, action, service_id)
        work_order_seed = {
            "agent_id": agent_id,
            "action": action,
            "service_id": service_id,
            "payload": payload,
            "timestamp": started,
        }
        work_order_id = canonical_hash(work_order_seed)
        receipt_path = self.evidence_dir / f"agent_runtime_work_order_{work_order_id}.json"
        outbox_path = self.outbox_dir / f"{work_order_id}.handoff.json"

        if decision.authorized:
            result = self.bounded_operation(action, service_id, payload)
            executed = True
        else:
            result = {"failed_closed": True, "reason": decision.reason}
            executed = False

        handoff = {
            "handoff_id": work_order_id,
            "source": "KEDDEH_V98_AGENT_RUNTIME_SERVICE",
            "payload_path": str(receipt_path),
            "receipt_path": str(self.ledger_path),
            "next_target": "acceptance_harness_then_self_hosted_m3_runner",
            "status": "READY_FOR_TARGET_HOST_EXECUTION" if decision.authorized else "FAILED_CLOSED",
            "created_at": started,
        }
        write_json(outbox_path, handoff)

        receipt = WorkOrderReceipt(
            work_order_id=work_order_id,
            agent_id=agent_id,
            action=action,
            service_id=service_id,
            authorized=decision.authorized,
            reason=decision.reason,
            executed=executed,
            result=result,
            receipt_path=str(receipt_path),
            ledger_path=str(self.ledger_path),
            outbox_manifest=str(outbox_path),
            timestamp=started,
        )
        write_json(receipt_path, asdict(receipt))
        append_ledger(self.ledger_path, {
            "type": "agent_runtime_work_order",
            "entry_hash": work_order_id,
            "receipt": asdict(receipt),
        })

        readback = any(entry.get("entry_hash") == work_order_id for entry in read_ledger(self.ledger_path))
        if not readback:
            raise RuntimeError("agent runtime ledger readback failed")
        return receipt


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--agent-id", default="acceptance_harness_agent")
    parser.add_argument("--action", default="write_receipt")
    parser.add_argument("--service-id", default="agent_registry_service")
    parser.add_argument("--payload-json", default="{}")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)

    payload = json.loads(args.payload_json)
    service = AgentRuntimeService(Path(args.root))
    receipt = service.execute_work_order(args.agent_id, args.action, args.service_id, payload)
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    return 0 if receipt.authorized and receipt.executed else 2


if __name__ == "__main__":
    raise SystemExit(main())
