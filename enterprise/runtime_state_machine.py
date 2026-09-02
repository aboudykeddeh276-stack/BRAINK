from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Iterable, Mapping, Optional
import hashlib
import json


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def root(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


class ProcessState(str, Enum):
    UNDEFINED = "PROCESS_UNDEFINED"
    DEFINED = "PROCESS_DEFINED"
    BOUND = "PROCESS_BOUND"
    INVOKED = "PROCESS_INVOKED"
    EXECUTED = "PROCESS_EXECUTED"
    SIGNALED = "PROCESS_SIGNALED"
    REJECTED = "PROCESS_REJECTED"


class ObserverState(str, Enum):
    UNREAD = "OBSERVER_UNREAD"
    PARTIAL = "OBSERVER_PARTIAL"
    OBSERVED = "OBSERVER_OBSERVED"
    CONTRADICTORY = "OBSERVER_CONTRADICTORY"


class ReconciliationState(str, Enum):
    PENDING = "RECONCILIATION_PENDING"
    ACCEPTED = "RECONCILIATION_ACCEPTED"
    REPAIR_REQUIRED = "RECONCILIATION_REPAIR_REQUIRED"
    SUPERSEDED = "RECONCILIATION_SUPERSEDED"


class AuthorityState(str, Enum):
    UNKNOWN = "AUTHORITY_UNKNOWN"
    AVAILABLE = "AUTHORITY_AVAILABLE"
    ACQUIRED = "AUTHORITY_ACQUIRED"
    REVOKED = "AUTHORITY_REVOKED"
    FENCED = "AUTHORITY_FENCED"


@dataclass(frozen=True)
class Observation:
    kind: str
    source: str
    status: str
    evidence_id: str
    payload_root: Optional[str] = None


@dataclass(frozen=True)
class RuntimeState:
    process: ProcessState
    observer: ObserverState
    reconciliation: ReconciliationState
    authority: AuthorityState
    subject: str
    execution_receipt_root: Optional[str] = None
    observer_root: Optional[str] = None
    conflict_root: Optional[str] = None

    @property
    def state_root(self) -> str:
        payload = asdict(self)
        payload["process"] = self.process.value
        payload["observer"] = self.observer.value
        payload["reconciliation"] = self.reconciliation.value
        payload["authority"] = self.authority.value
        return root(payload)


def classify_process(*, mechanism_defined: bool, target_bound: bool, operation_invoked: bool,
                     state_effect: bool, signal_emitted: bool, rejected: bool = False) -> ProcessState:
    if rejected:
        return ProcessState.REJECTED
    if signal_emitted:
        return ProcessState.SIGNALED
    if state_effect:
        return ProcessState.EXECUTED
    if operation_invoked:
        return ProcessState.INVOKED
    if target_bound:
        return ProcessState.BOUND
    if mechanism_defined:
        return ProcessState.DEFINED
    return ProcessState.UNDEFINED


def classify_observer(observations: Iterable[Observation]) -> tuple[ObserverState, str]:
    obs = list(observations)
    if not obs:
        return ObserverState.UNREAD, root([])
    statuses = {o.status.upper() for o in obs}
    observer_root = root([asdict(o) for o in obs])
    if "CONTRADICTION" in statuses or "FAIL_CONTRADICTION" in statuses:
        return ObserverState.CONTRADICTORY, observer_root
    if statuses <= {"PASS", "OBSERVED", "OK"}:
        return ObserverState.OBSERVED, observer_root
    return ObserverState.PARTIAL, observer_root


def reconcile(*, subject: str, process: ProcessState, authority: AuthorityState,
              observations: Iterable[Observation] = (), conflicts: Iterable[Mapping[str, Any]] = (),
              execution_receipt_root: Optional[str] = None) -> RuntimeState:
    observations = list(observations)
    conflicts = list(conflicts)
    observer, observer_root = classify_observer(observations)
    conflict_root = root(conflicts) if conflicts else None

    if process == ProcessState.REJECTED or authority in {AuthorityState.REVOKED, AuthorityState.FENCED}:
        rec = ReconciliationState.REPAIR_REQUIRED
    elif conflicts or observer == ObserverState.CONTRADICTORY:
        rec = ReconciliationState.REPAIR_REQUIRED
    elif process in {ProcessState.EXECUTED, ProcessState.SIGNALED}:
        rec = ReconciliationState.ACCEPTED
    else:
        rec = ReconciliationState.PENDING

    return RuntimeState(
        process=process,
        observer=observer,
        reconciliation=rec,
        authority=authority,
        subject=subject,
        execution_receipt_root=execution_receipt_root,
        observer_root=observer_root,
        conflict_root=conflict_root,
    )


def execution_eligible(*, mechanism_present: bool, binding_present: bool, state_target_present: bool,
                       actuator_present: bool, receipt_path_present: bool,
                       authority: AuthorityState) -> tuple[bool, str]:
    if authority in {AuthorityState.REVOKED, AuthorityState.FENCED}:
        return False, authority.value
    missing = [name for name, present in (
        ("MECHANISM_ABSENT", mechanism_present),
        ("BINDING_ABSENT", binding_present),
        ("STATE_TARGET_ABSENT", state_target_present),
        ("ACTUATOR_ABSENT", actuator_present),
        ("RECEIPT_PATH_ABSENT", receipt_path_present),
    ) if not present]
    if missing:
        return False, missing[0]
    return True, "EXECUTION_ELIGIBLE"
