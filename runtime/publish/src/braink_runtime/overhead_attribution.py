from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping


@dataclass(frozen=True)
class MeasurementReceipt:
    receipt_id: str
    metric: str
    baseline_value: float
    active_value: float
    unit: str
    execution_contract: str
    target_node: str
    capability: str

    @property
    def delta(self) -> float:
        return self.active_value - self.baseline_value


@dataclass(frozen=True)
class ExecutionEvidence:
    contract_id: str
    target_node: str
    capability: str
    parent_contract: str | None
    cause_receipt: str | None = None
    accountable_cause: str | None = None


@dataclass(frozen=True)
class AttributionResult:
    measurement_receipt: str
    observed_metric: str
    observed_delta: float
    unit: str
    trace: tuple[str, ...]
    first_accountable_cause: str | None
    cause_receipt: str | None
    status: str


def trace_backwards(
    measurement: MeasurementReceipt,
    evidence_by_contract: Mapping[str, ExecutionEvidence],
    *,
    max_depth: int = 64,
) -> AttributionResult:
    """Attribute only an observed delta with explicit causal evidence.

    No metric is labelled overhead merely because it changed. The trace walks
    backward from the measurement's execution contract. Attribution succeeds
    only when an execution evidence record explicitly names an accountable
    cause AND provides a receipt for that cause. Missing links remain
    UNATTRIBUTED rather than being filled with assumptions.
    """
    trace: list[str] = []
    contract_id: str | None = measurement.execution_contract
    seen: set[str] = set()

    for _ in range(max_depth):
        if contract_id is None:
            break
        if contract_id in seen:
            return AttributionResult(
                measurement.receipt_id, measurement.metric, measurement.delta,
                measurement.unit, tuple(trace), None, None, "TRACE_CYCLE_REJECTED"
            )
        seen.add(contract_id)
        ev = evidence_by_contract.get(contract_id)
        if ev is None:
            break
        if ev.target_node != measurement.target_node and not trace:
            return AttributionResult(
                measurement.receipt_id, measurement.metric, measurement.delta,
                measurement.unit, tuple(trace), None, None, "TARGET_MISMATCH_REJECTED"
            )
        trace.append(ev.contract_id)
        if ev.accountable_cause and ev.cause_receipt:
            return AttributionResult(
                measurement.receipt_id, measurement.metric, measurement.delta,
                measurement.unit, tuple(trace), ev.accountable_cause,
                ev.cause_receipt, "ATTRIBUTED"
            )
        contract_id = ev.parent_contract

    return AttributionResult(
        measurement.receipt_id, measurement.metric, measurement.delta,
        measurement.unit, tuple(trace), None, None, "UNATTRIBUTED"
    )


def to_row(result: AttributionResult) -> dict[str, Any]:
    return asdict(result)
