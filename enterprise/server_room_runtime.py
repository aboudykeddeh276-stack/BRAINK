from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, Iterable, Mapping
import hashlib
import json
import time

from enterprise.service_genome import AIServerRoom, ServiceGenome, GenomeComposer, default_server_classes


def root(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ServerProcessReceipt:
    room_id: str
    server_instance: str
    function_id: str
    status: str
    effect: Mapping[str, Any]
    produced_at_ns: int

    @property
    def receipt_root(self) -> str:
        return root(asdict(self))


class AIServerRoomRuntime:
    """Runs a composed server room while keeping sector implementation behind adapters."""

    def __init__(self, room: AIServerRoom):
        self.room = room
        self.function_handlers: Dict[str, Callable[[Mapping[str, Any]], Mapping[str, Any]]] = {}
        self.receipts: list[ServerProcessReceipt] = []

    def bind_function(self, function_id: str, handler: Callable[[Mapping[str, Any]], Mapping[str, Any]]) -> None:
        assigned = {f for instance in self.room.server_instances for f in instance.assigned_functions}
        if function_id not in assigned:
            raise KeyError(f"FUNCTION_NOT_IN_ROOM:{function_id}")
        self.function_handlers[function_id] = handler

    def invoke(self, function_id: str, payload: Mapping[str, Any]) -> ServerProcessReceipt:
        instances = [i for i in self.room.server_instances if function_id in i.assigned_functions]
        if not instances:
            raise KeyError(f"FUNCTION_NOT_ASSIGNED:{function_id}")
        chosen = sorted(instances, key=lambda i: (i.ordinal, i.instance_id))[0]
        handler = self.function_handlers.get(function_id)
        if handler is None:
            status = "DEFERRED_FUNCTION_HOLE"
            effect = {"reason": "FUNCTION_HANDLER_UNBOUND"}
        else:
            try:
                effect = dict(handler(dict(payload)))
                status = str(effect.pop("_status", "EXECUTED"))
            except Exception as exc:
                status = "REJECTED"
                effect = {"reason": str(exc), "exception_type": type(exc).__name__}
        receipt = ServerProcessReceipt(
            self.room.room_id,
            chosen.instance_id,
            function_id,
            status,
            effect,
            time.time_ns(),
        )
        self.receipts.append(receipt)
        return receipt

    @property
    def state_root(self) -> str:
        return root({
            "room_root": self.room.room_root,
            "bindings": sorted(self.function_handlers.keys()),
            "receipts": [r.receipt_root for r in self.receipts],
        })
