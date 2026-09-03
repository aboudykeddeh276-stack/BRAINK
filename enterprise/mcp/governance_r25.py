from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import hashlib
import json
import sqlite3
import time
import uuid

from enterprise.mcp.r23_adapter import R23ClosureToolAdapter


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class GovernanceError(RuntimeError):
    pass


class ScopeDenied(GovernanceError):
    pass


class ApprovalRequired(GovernanceError):
    pass


class IdempotencyConflict(GovernanceError):
    pass


@dataclass(frozen=True)
class ActionContract:
    action: str
    sector: str
    owner: str
    risk: str
    required_scopes: tuple[str, ...]
    idempotent: bool
    approval_required: bool = False


ACTION_CONTRACTS: dict[str, ActionContract] = {
    "hr.lease.acquire": ActionContract("hr.lease.acquire", "AGENTS_ORCHESTRATION", "BRAINK", "MUTATE", ("hr:lease",), True),
    "hr.lease.replace_rehydrate": ActionContract("hr.lease.replace_rehydrate", "AGENTS_ORCHESTRATION", "BRAINK", "MUTATE", ("hr:lease",), True),
    "customer.lifecycle.create": ActionContract("customer.lifecycle.create", "CUSTOMER_FILE_BASE", "BRAINK", "MUTATE", ("customer:write",), True),
    "customer.lifecycle.transition": ActionContract("customer.lifecycle.transition", "CUSTOMER_FILE_BASE", "BRAINK", "MUTATE", ("customer:write",), True),
    "customer.lifecycle.event": ActionContract("customer.lifecycle.event", "CUSTOMER_FILE_BASE", "BRAINK", "MUTATE", ("customer:event",), True),
    "research.promotion.evaluate": ActionContract("research.promotion.evaluate", "RESEARCH", "BRAINK", "CONTROL", ("research:evaluate",), True, True),
    "publishing.stage": ActionContract("publishing.stage", "PUBLISHING", "BRAINK", "MUTATE", ("publishing:stage",), True),
    "publishing.project_internal": ActionContract("publishing.project_internal", "PUBLISHING", "BRAINK", "MUTATE", ("publishing:project",), True),
    "frontage.release_internal": ActionContract("frontage.release_internal", "WEB_FABRIC", "BRAINK", "MUTATE", ("frontage:release",), True, True),
    "domain.public_activation.request": ActionContract("domain.public_activation.request", "DOMAIN_AUTHORITY", "BRAINK", "EXTERNAL_MUTATION_INTENT", ("domain:activate",), True, True),
}


class InvocationLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS invocations(
                invocation_id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                work_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                lease_epoch INTEGER NOT NULL,
                idempotency_key TEXT,
                request_hash TEXT NOT NULL,
                state TEXT NOT NULL,
                operation_json TEXT,
                created_ns INTEGER NOT NULL,
                completed_ns INTEGER
            )""")
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS ux_action_idempotency
                ON invocations(action,idempotency_key)
                WHERE idempotency_key IS NOT NULL""")

    def prior(self, action: str, key: str | None) -> dict[str, Any] | None:
        if not key:
            return None
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT invocation_id,request_hash,state,operation_json FROM invocations WHERE action=? AND idempotency_key=?",
                (action, key),
            ).fetchone()
        if not row:
            return None
        return {"invocation_id": row[0], "request_hash": row[1], "state": row[2], "operation": json.loads(row[3]) if row[3] else None}

    def begin(self, invocation_id: str, contract: ActionContract, context: dict[str, Any], key: str | None, request_hash: str) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT INTO invocations VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (invocation_id, contract.action, context["work_id"], context["actor_id"], int(context["lease_epoch"]), key, request_hash, "EXECUTING", None, time.time_ns(), None),
            )
            db.commit()

    def finish(self, invocation_id: str, state: str, operation: dict[str, Any] | None = None) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute(
                "UPDATE invocations SET state=?,operation_json=?,completed_ns=? WHERE invocation_id=?",
                (state, canonical(operation) if operation is not None else None, time.time_ns(), invocation_id),
            )
            db.commit()


class GovernedR23Adapter:
    """Enterprise policy membrane over the resident R23 mechanics.

    R23 remains the execution implementation. This layer supplies actor/work identity,
    scope checks, approval gates, idempotency, and a durable invocation ledger.
    """

    def __init__(self, state_path: str | Path, ledger_path: str | Path | None = None):
        self.inner = R23ClosureToolAdapter(state_path)
        state_path = Path(state_path)
        self.ledger = InvocationLedger(ledger_path or state_path.with_suffix(state_path.suffix + ".invocations.sqlite"))

    @staticmethod
    def contracts() -> list[dict[str, Any]]:
        return [asdict(ACTION_CONTRACTS[key]) for key in sorted(ACTION_CONTRACTS)]

    @staticmethod
    def _authorize(contract: ActionContract, context: dict[str, Any]) -> None:
        for field in ("work_id", "actor_id", "lease_epoch", "scopes"):
            if field not in context:
                raise GovernanceError(f"CONTEXT_FIELD_REQUIRED:{field}")
        missing = sorted(set(contract.required_scopes) - set(context.get("scopes") or []))
        if missing:
            raise ScopeDenied("MISSING_SCOPES:" + ",".join(missing))
        if contract.approval_required and not context.get("approval_token"):
            raise ApprovalRequired(f"APPROVAL_REQUIRED:{contract.action}")

    def operate(self, action: str, payload: dict[str, Any], context: dict[str, Any], idempotency_key: str | None) -> dict[str, Any]:
        contract = ACTION_CONTRACTS.get(action)
        if not contract:
            raise GovernanceError(f"ACTION_NOT_CONTRACTED:{action}")
        self._authorize(contract, context)
        request_hash = sha256({"action": action, "payload": payload, "work_id": context["work_id"], "actor_id": context["actor_id"], "lease_epoch": int(context["lease_epoch"])})
        key = idempotency_key if contract.idempotent else None
        prior = self.ledger.prior(action, key)
        if prior:
            if prior["request_hash"] != request_hash:
                raise IdempotencyConflict(f"IDEMPOTENCY_CONFLICT:{action}:{key}")
            if prior["state"] == "SUCCEEDED":
                return {"status": "REPLAYED_SUCCESS", "invocation_id": prior["invocation_id"], "contract": asdict(contract), "operation": prior["operation"]}
            raise GovernanceError(f"IDEMPOTENT_INVOCATION_STATE:{prior['state']}")
        invocation_id = str(uuid.uuid4())
        self.ledger.begin(invocation_id, contract, context, key, request_hash)
        try:
            operation = self.inner.operate(action, payload)
            self.ledger.finish(invocation_id, "SUCCEEDED", operation)
            return {"status": "SUCCEEDED", "invocation_id": invocation_id, "contract": asdict(contract), "operation": operation, "invocation_root": sha256({"invocation_id": invocation_id, "request_hash": request_hash, "receipt_root": operation["receipt_root"]})}
        except Exception:
            self.ledger.finish(invocation_id, "FAILED")
            raise

    def state(self) -> dict[str, Any]:
        return self.inner.state()

    def receipt(self, receipt_root: str) -> dict[str, Any]:
        return self.inner.receipt(receipt_root)

    def list_descendants(self) -> dict[str, Any]:
        return self.inner.list_descendants()
