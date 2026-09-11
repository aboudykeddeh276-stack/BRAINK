from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Mapping, Optional


class SignalKind(str, Enum):
    POWER = "POWER"
    SUB_POWER = "SUB_POWER"
    TRIGGER = "TRIGGER"
    RETRIGGER = "RETRIGGER"
    POWER_RESET = "POWER_RESET"


@dataclass(frozen=True)
class Signal:
    kind: SignalKind
    target: str
    opcode: str = "ACTIVATE"
    payload: Mapping[str, Any] | None = None
    authority: str = ""
    correlation_id: str = ""

    def canonical(self) -> bytes:
        return json.dumps(
            {
                "authority": self.authority,
                "correlation_id": self.correlation_id,
                "kind": self.kind.value,
                "opcode": self.opcode,
                "payload": self.payload or {},
                "target": self.target,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    @property
    def signal_id(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()


@dataclass(frozen=True)
class Receipt:
    signal_id: str
    target: str
    kind: str
    opcode: str
    status: str
    observed: Mapping[str, Any]
    previous_receipt_hash: str
    timestamp_ns: int
    receipt_hash: str


Actuator = Callable[[Signal], Mapping[str, Any]]
AuthorityCheck = Callable[[Signal], bool]


class SignalNode:
    """Minimal activation membrane for BRAINK/KEX resident mechanics.

    It owns no target semantics. It validates authority, resolves an actuator,
    invokes it once, and returns cryptographically chained observed evidence.
    """

    def __init__(self, authority_check: Optional[AuthorityCheck] = None) -> None:
        self._actuators: Dict[str, Actuator] = {}
        self._authority_check = authority_check or (lambda signal: bool(signal.authority))
        self._last_receipt_hash = "GENESIS"
        self._seen: Dict[str, Receipt] = {}
        self._power_state: Dict[str, str] = {}

    def register(self, target: str, actuator: Actuator) -> None:
        if not target or target in self._actuators:
            raise ValueError(f"invalid or duplicate target: {target!r}")
        self._actuators[target] = actuator

    def dispatch(self, signal: Signal) -> Receipt:
        if not self._authority_check(signal):
            return self._receipt(signal, "DENIED", {"reason": "authority"})

        if signal.target not in self._actuators:
            return self._receipt(signal, "UNRESOLVED", {"reason": "target"})

        if signal.signal_id in self._seen:
            return self._seen[signal.signal_id]

        if signal.kind is SignalKind.POWER_RESET:
            self._power_state[signal.target] = "RESETTING"
            observed = dict(self._actuators[signal.target](signal))
            self._power_state[signal.target] = "ON"
        elif signal.kind in (SignalKind.POWER, SignalKind.SUB_POWER):
            self._power_state[signal.target] = "ON"
            observed = dict(self._actuators[signal.target](signal))
        else:
            observed = dict(self._actuators[signal.target](signal))

        observed.setdefault("power_state", self._power_state.get(signal.target, "UNKNOWN"))
        receipt = self._receipt(signal, "EXECUTED", observed)
        self._seen[signal.signal_id] = receipt
        return receipt

    def _receipt(self, signal: Signal, status: str, observed: Mapping[str, Any]) -> Receipt:
        timestamp_ns = time.time_ns()
        body = {
            "kind": signal.kind.value,
            "observed": observed,
            "opcode": signal.opcode,
            "previous_receipt_hash": self._last_receipt_hash,
            "signal_id": signal.signal_id,
            "status": status,
            "target": signal.target,
            "timestamp_ns": timestamp_ns,
        }
        receipt_hash = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()
        receipt = Receipt(receipt_hash=receipt_hash, **body)
        self._last_receipt_hash = receipt_hash
        return receipt
