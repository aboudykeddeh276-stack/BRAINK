from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class Criticality(str, Enum):
    CORE_MANDATORY = "CORE_MANDATORY"
    CORE_DEGRADED = "CORE_DEGRADED"
    OPTIONAL = "OPTIONAL"
    EXTERNAL_GATE = "EXTERNAL_GATE"
    REPLACEABLE = "REPLACEABLE"
    DEFERRED_COMMIT = "DEFERRED_COMMIT"


class NodeHealth(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    AT_RISK = "AT_RISK"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    ISOLATED = "ISOLATED"


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass(frozen=True)
class IntegrityReadback:
    manifest_path: str
    expected_sha256: str
    observed_sha256: str
    parsed_application_id: str
    parsed_version: str
    valid: bool
    checked_at: float
    reason: str


def verify_manifest_integrity(manifest_path: Path, expected_sha256: str) -> IntegrityReadback:
    checked_at = time.time()
    try:
        raw = manifest_path.read_bytes()
        observed = hashlib.sha256(raw).hexdigest()
        parsed = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return IntegrityReadback(
            str(manifest_path), expected_sha256, "", "", "", False,
            checked_at, f"readback_error:{type(exc).__name__}",
        )

    application_id = parsed.get("applicationId")
    version = parsed.get("version")
    if not isinstance(application_id, str) or not application_id.strip():
        return IntegrityReadback(
            str(manifest_path), expected_sha256, observed, "",
            str(version or ""), False, checked_at, "missing_application_id",
        )
    if not isinstance(version, str) or not version.strip():
        return IntegrityReadback(
            str(manifest_path), expected_sha256, observed, application_id,
            "", False, checked_at, "missing_version",
        )
    if observed != expected_sha256:
        return IntegrityReadback(
            str(manifest_path), expected_sha256, observed, application_id,
            version, False, checked_at, "sha256_mismatch",
        )
    return IntegrityReadback(
        str(manifest_path), expected_sha256, observed, application_id,
        version, True, checked_at, "verified",
    )


@dataclass
class FailureRecord:
    failure_id: str
    dependency_id: str
    capability: str
    criticality: Criticality
    root_cause: str
    impact_radius: List[str]
    continuation_mode: str
    fallback_adapter: Optional[str]
    recovery_conditions: List[str]
    deferred_work: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "OPEN"
    opened_at: float = field(default_factory=time.time)
    recovered_at: Optional[float] = None


class FailureLedger:
    """Append-only failure ledger with recovery and deferred reconciliation."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, event: Dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

    def record_failure(self, record: FailureRecord) -> None:
        self._append({
            "event": "FAILURE_RECORDED",
            "record": asdict(record),
            "timestamp": time.time(),
        })

    def defer_work(self, failure_id: str, work: Dict[str, Any]) -> None:
        self._append({
            "event": "WORK_DEFERRED",
            "failure_id": failure_id,
            "work": work,
            "timestamp": time.time(),
        })

    def mark_recovered(self, failure_id: str, evidence: Dict[str, Any]) -> None:
        self._append({
            "event": "DEPENDENCY_RECOVERED",
            "failure_id": failure_id,
            "evidence": evidence,
            "timestamp": time.time(),
        })

    def events(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def open_failures(self) -> Dict[str, Dict[str, Any]]:
        open_records: Dict[str, Dict[str, Any]] = {}
        for event in self.events():
            if event["event"] == "FAILURE_RECORDED":
                open_records[event["record"]["failure_id"]] = event["record"]
            elif event["event"] == "DEPENDENCY_RECOVERED":
                open_records.pop(event["failure_id"], None)
        return open_records

    def reconcile_deferred(
        self,
        failure_id: str,
        executor: Callable[[Dict[str, Any]], Any],
    ) -> List[Any]:
        recovered = any(
            event["event"] == "DEPENDENCY_RECOVERED"
            and event["failure_id"] == failure_id
            for event in self.events()
        )
        if not recovered:
            raise RuntimeError("dependency_not_recovered")

        results: List[Any] = []
        for event in self.events():
            if event["event"] == "WORK_DEFERRED" and event["failure_id"] == failure_id:
                results.append(executor(event["work"]))
                self._append({
                    "event": "WORK_RECONCILED",
                    "failure_id": failure_id,
                    "work": event["work"],
                    "timestamp": time.time(),
                })
        return results


@dataclass(frozen=True)
class MeshNodeStatus:
    node_id: str
    health: NodeHealth
    dependencies: Dict[str, NodeHealth]
    core_semantic_validity: bool
    observed_at: float


class HealthState:
    """Central mesh monitor preserving per-domain health and UI degradation."""

    def __init__(self, stale_after_seconds: float = 60.0):
        self.stale_after_seconds = stale_after_seconds
        self._nodes: Dict[str, MeshNodeStatus] = {}

    def update(self, status: MeshNodeStatus) -> None:
        self._nodes[status.node_id] = status

    def snapshot(self, now: Optional[float] = None) -> Dict[str, Any]:
        now = time.time() if now is None else now
        nodes: Dict[str, Any] = {}
        degraded = False

        for node_id, status in self._nodes.items():
            effective = status.health
            if now - status.observed_at > self.stale_after_seconds:
                effective = NodeHealth.STALE
            dependency_failures = {
                dependency: health.value
                for dependency, health in status.dependencies.items()
                if health != NodeHealth.HEALTHY
            }
            if effective != NodeHealth.HEALTHY or dependency_failures:
                degraded = True
            nodes[node_id] = {
                "health": effective.value,
                "dependencies": {
                    dependency: health.value
                    for dependency, health in status.dependencies.items()
                },
                "failed_dependencies": dependency_failures,
                "core_semantic_validity": status.core_semantic_validity,
                "observed_at": status.observed_at,
            }

        return {
            "ui_state": "degraded" if degraded else "healthy",
            "overall_state": "OPERATIONAL_DEGRADED" if degraded else "HEALTHY",
            "nodes": nodes,
        }


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        if failure_threshold < 1:
            raise ValueError("failure_threshold_must_be_positive")
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.opened_at: Optional[float] = None

    def _refresh(self, now: float) -> None:
        if (
            self.state == CircuitState.OPEN
            and self.opened_at is not None
            and now - self.opened_at >= self.recovery_timeout
        ):
            self.state = CircuitState.HALF_OPEN

    def call(
        self,
        operation: Callable[[], Any],
        fallback: Callable[[], Any],
        now: Optional[float] = None,
    ) -> Any:
        now = time.time() if now is None else now
        self._refresh(now)
        if self.state == CircuitState.OPEN:
            return fallback()
        try:
            result = operation()
        except Exception:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.opened_at = now
            return fallback()
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.opened_at = None
        return result


class KCloudAdapter:
    def __init__(
        self,
        mesh_breaker: CircuitBreaker,
        telemetry_breaker: CircuitBreaker,
    ):
        self.mesh_breaker = mesh_breaker
        self.telemetry_breaker = telemetry_breaker

    def register_package(
        self,
        operation: Callable[[], Any],
        deferred: Callable[[], Any],
    ) -> Any:
        return self.mesh_breaker.call(operation, deferred)

    def publish_telemetry(
        self,
        operation: Callable[[], Any],
        local_outbox: Callable[[], Any],
    ) -> Any:
        return self.telemetry_breaker.call(operation, local_outbox)


def deployment_gate(manifest_path: Path, expected_sha256: str) -> IntegrityReadback:
    """Mandatory integrity readback immediately before node execution."""
    result = verify_manifest_integrity(manifest_path, expected_sha256)
    if not result.valid:
        raise RuntimeError(f"manifest_integrity_readback_failed:{result.reason}")
    return result
