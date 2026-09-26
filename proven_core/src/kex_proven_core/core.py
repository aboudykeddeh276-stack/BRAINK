from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import time
from typing import Mapping


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: object) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


class Surface(str, Enum):
    SOFTWARE_ROOT = "SOFTWARE_ROOT"
    EXECUTABLE_VOLUME = "EXECUTABLE_VOLUME"
    OS_APPLIANCE = "OS_APPLIANCE"
    RUNTIME_SUBSTRATE = "RUNTIME_SUBSTRATE"
    SPECIALIZATION = "SPECIALIZATION"
    PROJECTION_HCI = "PROJECTION_HCI"
    CARRIER = "CARRIER"
    MANIFEST_EVIDENCE = "MANIFEST_EVIDENCE"


class EvidenceState(str, Enum):
    NOT_OBSERVED = "NOT_OBSERVED"
    OBSERVED = "OBSERVED"
    EXECUTED_LOCAL = "EXECUTED_LOCAL"
    VERIFIED_LOCAL = "VERIFIED_LOCAL"
    EXTERNALLY_APPLIED = "EXTERNALLY_APPLIED"
    PUBLIC_READBACK = "PUBLIC_READBACK"


@dataclass(frozen=True)
class LogicalObject:
    identity: str
    surface: Surface
    parent: str | None = None
    canonical_key: str | None = None

    def __post_init__(self) -> None:
        if not self.identity or "://" not in self.identity:
            raise ValueError("identity must be a logical URI")
        object.__setattr__(self, "canonical_key", self.canonical_key or self.identity)


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    subject: str
    event: str
    state: EvidenceState
    payload_hash: str
    previous_hash: str
    created_ns: int
    receipt_hash: str

    @classmethod
    def create(cls, *, receipt_id: str, subject: str, event: str, state: EvidenceState,
               payload: Mapping[str, object], previous_hash: str,
               created_ns: int | None = None) -> "Receipt":
        ts = time.time_ns() if created_ns is None else created_ns
        payload_hash = digest(payload)
        body = {
            "receipt_id": receipt_id,
            "subject": subject,
            "event": event,
            "state": state.value,
            "payload_hash": payload_hash,
            "previous_hash": previous_hash,
            "created_ns": ts,
        }
        return cls(receipt_id, subject, event, state, payload_hash, previous_hash, ts, digest(body))


class ProofLedger:
    def __init__(self) -> None:
        self._receipts: list[Receipt] = []

    @property
    def root(self) -> str:
        return self._receipts[-1].receipt_hash if self._receipts else digest({"ledger": "empty"})

    @property
    def receipts(self) -> tuple[Receipt, ...]:
        return tuple(self._receipts)

    def append(self, *, subject: str, event: str, state: EvidenceState,
               payload: Mapping[str, object], created_ns: int | None = None) -> Receipt:
        receipt = Receipt.create(
            receipt_id=f"receipt://kex/{len(self._receipts) + 1}",
            subject=subject,
            event=event,
            state=state,
            payload=payload,
            previous_hash=self.root,
            created_ns=created_ns,
        )
        self._receipts.append(receipt)
        return receipt

    def verify(self) -> bool:
        previous = digest({"ledger": "empty"})
        for receipt in self._receipts:
            body = {
                "receipt_id": receipt.receipt_id,
                "subject": receipt.subject,
                "event": receipt.event,
                "state": receipt.state.value,
                "payload_hash": receipt.payload_hash,
                "previous_hash": receipt.previous_hash,
                "created_ns": receipt.created_ns,
            }
            if receipt.previous_hash != previous or digest(body) != receipt.receipt_hash:
                return False
            previous = receipt.receipt_hash
        return True


class Registry:
    def __init__(self) -> None:
        self._objects: dict[str, LogicalObject] = {}

    def register(self, obj: LogicalObject) -> None:
        prior = self._objects.get(obj.identity)
        if prior and prior != obj:
            raise ValueError("logical identity is immutable")
        if obj.parent and obj.parent not in self._objects:
            raise ValueError("parent must be registered before child")
        self._objects[obj.identity] = obj

    def get(self, identity: str) -> LogicalObject:
        return self._objects[identity]

    def snapshot(self) -> tuple[LogicalObject, ...]:
        return tuple(sorted(self._objects.values(), key=lambda item: item.identity))


@dataclass(frozen=True)
class Mutation:
    actor: str
    subject: str
    operation: str
    expected_canonical_key: str
    payload: Mapping[str, object]
    base_state_hash: str


class KEXAdmission:
    def __init__(self, registry: Registry, ledger: ProofLedger) -> None:
        self.registry = registry
        self.ledger = ledger
        self._state_hashes: dict[str, str] = {}

    def seed(self, identity: str, state: Mapping[str, object]) -> str:
        self.registry.get(identity)
        state_hash = digest(state)
        self._state_hashes.setdefault(identity, state_hash)
        return self._state_hashes[identity]

    def admit(self, mutation: Mutation) -> Receipt:
        obj = self.registry.get(mutation.subject)
        if mutation.expected_canonical_key != obj.canonical_key:
            raise PermissionError("canonical key must remain stable")
        current = self._state_hashes.get(mutation.subject)
        if current is None:
            raise RuntimeError("subject state not seeded")
        if mutation.base_state_hash != current:
            raise RuntimeError("parallel delta overwrite forbidden")
        if mutation.operation == "RENAME_IDENTITY":
            raise PermissionError("worker cannot rename task into new identity")
        new_hash = digest({
            "prior": current,
            "operation": mutation.operation,
            "payload": mutation.payload,
            "actor": mutation.actor,
        })
        self._state_hashes[mutation.subject] = new_hash
        return self.ledger.append(
            subject=mutation.subject,
            event=f"KEX_ADMIT:{mutation.operation}",
            state=EvidenceState.EXECUTED_LOCAL,
            payload={"actor": mutation.actor, "new_state_hash": new_hash},
        )


class PromotionGate:
    REQUIRED_PUBLIC = ("REGISTRAR", "DNS", "INGRESS", "TLS", "HTTP_READBACK")

    def __init__(self, ledger: ProofLedger) -> None:
        self.ledger = ledger

    def evaluate(self, subject: str, receipts: Mapping[str, bool]) -> Receipt:
        missing = [name for name in self.REQUIRED_PUBLIC if not receipts.get(name, False)]
        if missing:
            return self.ledger.append(
                subject=subject,
                event="PROMOTION_EVALUATED",
                state=EvidenceState.VERIFIED_LOCAL,
                payload={"promotion_state": "STAGED_NOT_PUBLIC_LIVE", "missing": missing},
            )
        return self.ledger.append(
            subject=subject,
            event="PROMOTION_EVALUATED",
            state=EvidenceState.PUBLIC_READBACK,
            payload={"promotion_state": "PUBLIC_LIVE", "missing": []},
        )


def build_minframe() -> tuple[Registry, ProofLedger, KEXAdmission]:
    registry = Registry()
    ledger = ProofLedger()
    registry.register(LogicalObject("volume://keddeh/braink/root", Surface.SOFTWARE_ROOT))
    registry.register(LogicalObject("runtime://kex/core", Surface.RUNTIME_SUBSTRATE, "volume://keddeh/braink/root"))
    registry.register(LogicalObject("app://kex/computer", Surface.SPECIALIZATION, "runtime://kex/core"))
    registry.register(LogicalObject("app://kex/active-state", Surface.SPECIALIZATION, "runtime://kex/core"))
    registry.register(LogicalObject("projection://braink/local", Surface.PROJECTION_HCI, "volume://keddeh/braink/root"))
    return registry, ledger, KEXAdmission(registry, ledger)
