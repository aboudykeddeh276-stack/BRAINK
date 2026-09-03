from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable
import hashlib, json, sqlite3, time, uuid


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canonical(value).encode()
    return hashlib.sha256(raw).hexdigest()


class CapabilityError(RuntimeError): pass
class AuthorizationError(CapabilityError): pass
class IdempotencyConflict(CapabilityError): pass
class CapabilityUnavailable(CapabilityError): pass
class ApprovalRequired(CapabilityError): pass
class CircuitOpen(CapabilityError): pass
class CapabilityExecutionRejected(CapabilityError): pass


class Risk(str, Enum):
    READ = "READ"
    MUTATE = "MUTATE"
    DESTRUCTIVE = "DESTRUCTIVE"


@dataclass(frozen=True)
class CapabilityContract:
    capability_id: str
    sector: str
    owner_repo: str
    operation: str
    risk: Risk
    required_scopes: tuple[str, ...]
    idempotent: bool
    requires_approval: bool = False
    max_failures: int = 3
    cooldown_seconds: int = 30


@dataclass(frozen=True)
class InvocationContext:
    work_id: str
    actor_id: str
    lease_epoch: int
    scopes: tuple[str, ...]
    approval_token: str | None = None


@dataclass
class RegisteredCapability:
    contract: CapabilityContract
    handler: Callable[[dict[str, Any]], dict[str, Any]]


class ReceiptLedger:
    """Durable source of truth for invocation lifecycle, idempotency, and circuit state."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS invocations(
                invocation_id TEXT PRIMARY KEY,
                capability_id TEXT NOT NULL,
                work_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                lease_epoch INTEGER NOT NULL,
                request_hash TEXT NOT NULL,
                idempotency_key TEXT,
                state TEXT NOT NULL,
                result_json TEXT,
                error_text TEXT,
                created_ns INTEGER NOT NULL,
                completed_ns INTEGER
            )""")
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS ux_idempotency
                ON invocations(capability_id,idempotency_key)
                WHERE idempotency_key IS NOT NULL""")
            db.execute("""CREATE TABLE IF NOT EXISTS circuit(
                capability_id TEXT PRIMARY KEY,
                failure_count INTEGER NOT NULL,
                opened_ns INTEGER
            )""")

    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def prior(self, capability_id: str, idempotency_key: str | None):
        if not idempotency_key:
            return None
        with self.db() as db:
            row = db.execute(
                "SELECT request_hash,state,result_json,error_text,invocation_id FROM invocations "
                "WHERE capability_id=? AND idempotency_key=?",
                (capability_id, idempotency_key),
            ).fetchone()
        if not row:
            return None
        return {
            "request_hash": row[0], "state": row[1],
            "result": json.loads(row[2]) if row[2] else None,
            "error": row[3], "invocation_id": row[4]
        }

    def begin(self, *, invocation_id, contract, ctx, request_hash, idempotency_key):
        with self.db() as db:
            db.execute(
                "INSERT INTO invocations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (invocation_id, contract.capability_id, ctx.work_id, ctx.actor_id,
                 ctx.lease_epoch, request_hash, idempotency_key, "EXECUTING",
                 None, None, time.time_ns(), None)
            )
            db.commit()

    def finish(self, invocation_id: str, state: str, result=None, error=None):
        with self.db() as db:
            db.execute(
                "UPDATE invocations SET state=?,result_json=?,error_text=?,completed_ns=? WHERE invocation_id=?",
                (state, canonical(result) if result is not None else None, error, time.time_ns(), invocation_id)
            )
            db.commit()

    def circuit_state(self, capability_id: str):
        with self.db() as db:
            row = db.execute("SELECT failure_count,opened_ns FROM circuit WHERE capability_id=?", (capability_id,)).fetchone()
        return row or (0, None)

    def record_success(self, capability_id: str):
        with self.db() as db:
            db.execute(
                "INSERT INTO circuit VALUES(?,0,NULL) ON CONFLICT(capability_id) DO UPDATE SET failure_count=0,opened_ns=NULL",
                (capability_id,)
            )
            db.commit()

    def record_failure(self, contract: CapabilityContract):
        failures, opened = self.circuit_state(contract.capability_id)
        failures += 1
        opened_ns = time.time_ns() if failures >= contract.max_failures else opened
        with self.db() as db:
            db.execute(
                "INSERT INTO circuit VALUES(?,?,?) ON CONFLICT(capability_id) "
                "DO UPDATE SET failure_count=excluded.failure_count,opened_ns=excluded.opened_ns",
                (contract.capability_id, failures, opened_ns)
            )
            db.commit()
        return failures, opened_ns


class CapabilityRegistry:
    def __init__(self):
        self._caps: dict[str, RegisteredCapability] = {}

    def register(self, contract: CapabilityContract, handler):
        if contract.capability_id in self._caps:
            raise ValueError(f"duplicate capability: {contract.capability_id}")
        self._caps[contract.capability_id] = RegisteredCapability(contract, handler)

    def resolve(self, capability_id: str) -> RegisteredCapability:
        cap = self._caps.get(capability_id)
        if not cap:
            raise CapabilityUnavailable(capability_id)
        return cap

    def manifest(self):
        return [asdict(v.contract) for v in self._caps.values()]


class CapabilityRuntime:
    FAILURE_STATUSES = {
        "FAILED", "REJECTED", "NOT_EXECUTED", "UNSUPPORTED_OPERATION",
        "UNBOUND_RUNTIME_PATH", "UNBOUND_ACTUATOR", "LOAD_FAILED", "ERROR",
    }

    def __init__(
        self,
        ledger: ReceiptLedger,
        registry: CapabilityRegistry,
        context_validator: Callable[[InvocationContext], None] | None = None,
    ):
        self.ledger = ledger
        self.registry = registry
        self.context_validator = context_validator

    @staticmethod
    def _authorize(contract: CapabilityContract, ctx: InvocationContext):
        missing = sorted(set(contract.required_scopes) - set(ctx.scopes))
        if missing:
            raise AuthorizationError(f"missing scopes: {missing}")
        if contract.requires_approval and not ctx.approval_token:
            raise ApprovalRequired(contract.capability_id)

    def _check_circuit(self, contract: CapabilityContract):
        failures, opened_ns = self.ledger.circuit_state(contract.capability_id)
        if opened_ns:
            elapsed = (time.time_ns() - opened_ns) / 1e9
            if elapsed < contract.cooldown_seconds:
                raise CircuitOpen(contract.capability_id)
            self.ledger.record_success(contract.capability_id)

    @classmethod
    def _semantic_failure(cls, value: Any, path: str = "result") -> str | None:
        if isinstance(value, dict):
            status = value.get("status")
            if isinstance(status, str):
                normalized = status.upper()
                if normalized in cls.FAILURE_STATUSES or normalized.startswith(("FAILED_", "REJECTED_", "UNBOUND_", "ERROR_")):
                    return f"{path}.status={status}"
            for key, nested in value.items():
                failure = cls._semantic_failure(nested, f"{path}.{key}")
                if failure:
                    return failure
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                failure = cls._semantic_failure(nested, f"{path}[{index}]")
                if failure:
                    return failure
        return None

    def invoke(self, capability_id: str, ctx: InvocationContext, payload: dict[str, Any],
               idempotency_key: str | None = None) -> dict[str, Any]:
        reg = self.registry.resolve(capability_id)
        contract = reg.contract
        self._authorize(contract, ctx)
        if self.context_validator is not None:
            self.context_validator(ctx)
        self._check_circuit(contract)

        request = {
            "capability_id": capability_id,
            "work_id": ctx.work_id,
            "actor_id": ctx.actor_id,
            "lease_epoch": ctx.lease_epoch,
            "payload": payload,
        }
        request_hash = sha256(request)

        if idempotency_key:
            prior = self.ledger.prior(capability_id, idempotency_key)
            if prior:
                if prior["request_hash"] != request_hash:
                    raise IdempotencyConflict(idempotency_key)
                if prior["state"] == "SUCCEEDED":
                    return {
                        "status": "REPLAYED_SUCCESS",
                        "invocation_id": prior["invocation_id"],
                        "result": prior["result"],
                    }
                raise CapabilityError(f"idempotent invocation already exists in state {prior['state']}")

        invocation_id = str(uuid.uuid4())
        self.ledger.begin(
            invocation_id=invocation_id, contract=contract, ctx=ctx,
            request_hash=request_hash,
            idempotency_key=idempotency_key if contract.idempotent else None,
        )

        try:
            result = reg.handler(payload)
            if not isinstance(result, dict):
                raise TypeError("capability handler must return dict")
            semantic_failure = self._semantic_failure(result)
            if semantic_failure:
                raise CapabilityExecutionRejected(semantic_failure)
            self.ledger.finish(invocation_id, "SUCCEEDED", result=result)
            self.ledger.record_success(capability_id)
            return {
                "status": "SUCCEEDED",
                "invocation_id": invocation_id,
                "capability": asdict(contract),
                "result": result,
                "receipt_root": sha256({
                    "invocation_id": invocation_id,
                    "request_hash": request_hash,
                    "result": result,
                }),
            }
        except Exception as exc:
            self.ledger.finish(invocation_id, "FAILED", error=f"{type(exc).__name__}: {exc}")
            failures, opened = self.ledger.record_failure(contract)
            return {
                "status": "FAILED",
                "invocation_id": invocation_id,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "failure_count": failures,
                "circuit_opened": bool(opened),
            }
