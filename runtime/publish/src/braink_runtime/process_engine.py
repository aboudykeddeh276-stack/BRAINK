from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class ExecutionContract:
    contract_id: str
    state: str
    authority: str
    target: str
    capability: str
    payload: dict[str, Any] = field(default_factory=dict)
    expected_receipt: str = "CAPABILITY_RECEIPT"


@dataclass(frozen=True)
class CapabilityReceipt:
    contract_id: str
    target: str
    capability: str
    status: str
    observed: dict[str, Any]
    started_ns: int
    completed_ns: int
    receipt_type: str = "CAPABILITY_RECEIPT"

    @property
    def digest(self) -> str:
        body = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(body).hexdigest()


class ProcessViolation(RuntimeError):
    pass


class ProcessEngine:
    """BRAINK core process authority.

    Governing law:
        STATE -> AUTHORITY -> TARGET -> BOUNDED CAPABILITY -> EXECUTION
        -> OBSERVED RECEIPT -> VALIDATION -> NEXT STATE

    Capabilities are registered executors. They do not own policy, authority,
    state promotion, retry policy, or validation semantics. Those remain here.
    """

    def __init__(self) -> None:
        self._capabilities: dict[str, Callable[[ExecutionContract], CapabilityReceipt]] = {}

    def register_capability(
        self,
        capability: str,
        executor: Callable[[ExecutionContract], CapabilityReceipt],
    ) -> None:
        key = capability.strip().upper()
        if not key:
            raise ValueError("CAPABILITY_NAME_REQUIRED")
        self._capabilities[key] = executor

    def execute(self, contract: ExecutionContract) -> dict[str, Any]:
        if not contract.authority:
            raise ProcessViolation("AUTHORITY_REQUIRED")
        if not contract.target:
            raise ProcessViolation("TARGET_REQUIRED")
        key = contract.capability.strip().upper()
        executor = self._capabilities.get(key)
        if executor is None:
            raise ProcessViolation(f"CAPABILITY_UNBOUND:{key}")

        receipt = executor(contract)
        self._validate(contract, receipt)
        next_state = self._next_state(contract.state, receipt.status)
        return {
            "schema": "braink.process.transition.v1",
            "law": "STATE>AUTHORITY>TARGET>CAPABILITY>EXECUTION>RECEIPT>VALIDATION>NEXT_STATE",
            "contract": asdict(contract),
            "receipt": {**asdict(receipt), "digest": receipt.digest},
            "validation": "PASS",
            "next_state": next_state,
        }

    @staticmethod
    def _validate(contract: ExecutionContract, receipt: CapabilityReceipt) -> None:
        if receipt.contract_id != contract.contract_id:
            raise ProcessViolation("RECEIPT_CONTRACT_MISMATCH")
        if receipt.target != contract.target:
            raise ProcessViolation("RECEIPT_TARGET_MISMATCH")
        if receipt.capability.strip().upper() != contract.capability.strip().upper():
            raise ProcessViolation("RECEIPT_CAPABILITY_MISMATCH")
        if receipt.receipt_type != contract.expected_receipt:
            raise ProcessViolation("RECEIPT_TYPE_MISMATCH")
        if receipt.status not in {"PASS", "FAIL", "BLOCKED"}:
            raise ProcessViolation("INVALID_RECEIPT_STATUS")
        if receipt.completed_ns < receipt.started_ns:
            raise ProcessViolation("INVALID_RECEIPT_TIME_ORDER")

    @staticmethod
    def _next_state(state: str, status: str) -> str:
        if status == "PASS":
            return f"{state}:QUALIFIED"
        if status == "BLOCKED":
            return f"{state}:BLOCKED"
        return f"{state}:FAILED"


def make_receipt(
    contract: ExecutionContract,
    *,
    status: str,
    observed: dict[str, Any],
    started_ns: int | None = None,
) -> CapabilityReceipt:
    started = started_ns or time.time_ns()
    return CapabilityReceipt(
        contract_id=contract.contract_id,
        target=contract.target,
        capability=contract.capability,
        status=status,
        observed=observed,
        started_ns=started,
        completed_ns=time.time_ns(),
    )
