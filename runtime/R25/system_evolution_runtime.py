from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Iterable

CANONICAL_SEPARATORS = (",", ":")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=CANONICAL_SEPARATORS, ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Capability:
    capability_id: str
    owner: str
    runtime: str
    proof: str
    rollback: str
    projection: str | None = None
    status: str = "DISCOVERED"

    def validate(self) -> None:
        required = {
            "capability_id": self.capability_id,
            "owner": self.owner,
            "runtime": self.runtime,
            "proof": self.proof,
            "rollback": self.rollback,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Capability missing required fields: {missing}")


@dataclass(frozen=True)
class TransactionReceipt:
    event_id: str
    operation: str
    actor: str
    owner: str
    input_hash: str
    output_hash: str
    proof: dict[str, Any]
    rollback: dict[str, Any]
    lineage: list[str]


class AppendOnlyLedger:
    def __init__(self) -> None:
        self._events: list[TransactionReceipt] = []

    @property
    def events(self) -> tuple[TransactionReceipt, ...]:
        return tuple(self._events)

    def append(
        self,
        *,
        operation: str,
        actor: str,
        owner: str,
        input_state: Any,
        output_state: Any,
        proof: dict[str, Any],
        rollback: dict[str, Any],
        lineage: Iterable[str],
    ) -> TransactionReceipt:
        input_hash = sha256_json(input_state)
        output_hash = sha256_json(output_state)
        body = {
            "sequence": len(self._events) + 1,
            "operation": operation,
            "actor": actor,
            "owner": owner,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "proof": proof,
            "rollback": rollback,
            "lineage": list(lineage),
            "previous_event": self._events[-1].event_id if self._events else None,
        }
        receipt = TransactionReceipt(
            event_id=sha256_json(body),
            operation=operation,
            actor=actor,
            owner=owner,
            input_hash=input_hash,
            output_hash=output_hash,
            proof=proof,
            rollback=rollback,
            lineage=body["lineage"],
        )
        self._events.append(receipt)
        return receipt

    def verify(self) -> bool:
        previous_event: str | None = None
        seen: set[str] = set()
        for sequence, event in enumerate(self._events, start=1):
            if event.event_id in seen:
                return False
            body = {
                "sequence": sequence,
                "operation": event.operation,
                "actor": event.actor,
                "owner": event.owner,
                "input_hash": event.input_hash,
                "output_hash": event.output_hash,
                "proof": event.proof,
                "rollback": event.rollback,
                "lineage": list(event.lineage),
                "previous_event": previous_event,
            }
            if sha256_json(body) != event.event_id:
                return False
            seen.add(event.event_id)
            previous_event = event.event_id
        return True

    def export(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(event) for event in self._events]
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class EvolutionRuntime:
    def __init__(self, *, owner: str = "A.KEDDEH / KEDDEH_SYSTEMS") -> None:
        self.owner = owner
        self.capabilities: dict[str, Capability] = {}
        self.ledger = AppendOnlyLedger()
        self.checkpoints: dict[str, Any] = {}

    def discover(self, capabilities: Iterable[Capability]) -> list[str]:
        discovered = []
        for capability in capabilities:
            capability.validate()
            self.capabilities[capability.capability_id] = capability
            discovered.append(capability.capability_id)
        return sorted(discovered)

    def checkpoint(self, state: Any) -> str:
        checkpoint_id = sha256_json(state)
        self.checkpoints[checkpoint_id] = json.loads(canonical_json(state))
        return checkpoint_id

    def reconcile(
        self,
        *,
        actor: str,
        current_state: Any,
        desired_state: Any,
        repair: Callable[[Any, Any], Any],
        lineage: Iterable[str],
    ) -> TransactionReceipt:
        checkpoint_id = self.checkpoint(current_state)
        output_state = repair(current_state, desired_state)
        if output_state != desired_state:
            raise RuntimeError("Repair failed deterministic reconciliation: output != desired state")
        return self.ledger.append(
            operation="RECONCILE",
            actor=actor,
            owner=self.owner,
            input_state=current_state,
            output_state=output_state,
            proof={"desired_hash": sha256_json(desired_state), "readback_equal": True},
            rollback={"checkpoint_id": checkpoint_id},
            lineage=list(lineage),
        )

    def qualify_market_service(self, capability_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
        capability = self.capabilities[capability_id]
        capability.validate()
        required_metrics = ("customer_problem", "service_contract", "proof", "value_metric")
        missing = [key for key in required_metrics if not metrics.get(key)]
        if missing:
            return {"status": "BLOCKED", "missing": missing, "capability_id": capability_id}
        return {
            "status": "QUALIFIED",
            "capability_id": capability_id,
            "owner": capability.owner,
            "runtime": capability.runtime,
            "projection": capability.projection,
            "metrics_hash": sha256_json(metrics),
        }


def exact_repair(_: Any, desired: Any) -> Any:
    return json.loads(canonical_json(desired))
