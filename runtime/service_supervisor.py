"""Pure BRAINK service discovery classification.

Slice 1A intentionally performs no host/process mutation and no process discovery.
It converts already-observed facts into deterministic identity, ownership, health,
and lifecycle classifications. Host observation belongs to Slice 1B.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Tuple


class EvidenceClassification(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    FAILED = "FAILED"
    UNOBSERVED = "UNOBSERVED"


class IdentityState(str, Enum):
    ABSENT = "ABSENT"
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    CONFLICT = "IDENTITY_CONFLICT"


class OwnershipState(str, Enum):
    BRAINK_OWNED = "BRAINK_OWNED"
    EXTERNAL = "EXTERNAL"
    UNKNOWN = "UNKNOWN"


class HealthState(str, Enum):
    HEALTHY = "HEALTHY"
    SYNCING = "SYNCING"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class LifecycleState(str, Enum):
    ABSENT = "ABSENT"
    DISCOVERED_EXTERNAL = "DISCOVERED_EXTERNAL"
    DISCOVERED_BRAINK_OWNED = "DISCOVERED_BRAINK_OWNED"
    RUNNING_HEALTHY = "RUNNING_HEALTHY"
    RUNNING_SYNCING = "RUNNING_SYNCING"
    RUNNING_UNHEALTHY = "RUNNING_UNHEALTHY"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    UNOBSERVED = "UNOBSERVED"


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    start_time: str
    executable_path: str

    def __post_init__(self) -> None:
        if self.pid <= 0:
            raise ValueError("pid must be positive")
        if not self.start_time:
            raise ValueError("start_time is required")
        if not self.executable_path:
            raise ValueError("executable_path is required")


@dataclass(frozen=True)
class ServiceObservation:
    service_id: str
    expected_identity: Optional[ProcessIdentity] = None
    observed_identity: Optional[ProcessIdentity] = None
    process_present: Optional[bool] = None
    started_by_braink: Optional[bool] = None
    health: HealthState = HealthState.UNKNOWN
    evidence: Mapping[str, str] = field(default_factory=dict)
    contradictions: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.service_id:
            raise ValueError("service_id is required")
        if self.process_present is False and self.observed_identity is not None:
            raise ValueError("absent process cannot carry an observed identity")


@dataclass(frozen=True)
class ServiceClassification:
    service_id: str
    identity: IdentityState
    ownership: OwnershipState
    health: HealthState
    lifecycle: LifecycleState
    evidence_classification: EvidenceClassification
    shutdown_authority: bool
    contradictions: Tuple[str, ...] = ()


def classify_identity(observation: ServiceObservation) -> IdentityState:
    """Classify process identity without treating PID equality as sufficient proof."""
    if observation.contradictions:
        return IdentityState.CONFLICT
    if observation.process_present is False:
        return IdentityState.ABSENT
    if observation.observed_identity is None:
        return IdentityState.UNVERIFIED
    if observation.expected_identity is None:
        return IdentityState.UNVERIFIED
    if observation.observed_identity == observation.expected_identity:
        return IdentityState.VERIFIED
    return IdentityState.CONFLICT


def classify_ownership(
    observation: ServiceObservation, identity: IdentityState
) -> OwnershipState:
    """Ownership requires verified identity plus explicit BRAINK-start evidence."""
    if identity in (IdentityState.ABSENT, IdentityState.CONFLICT):
        return OwnershipState.UNKNOWN
    if observation.started_by_braink is True and identity is IdentityState.VERIFIED:
        return OwnershipState.BRAINK_OWNED
    if observation.started_by_braink is False:
        return OwnershipState.EXTERNAL
    return OwnershipState.UNKNOWN


def classify_lifecycle(
    observation: ServiceObservation,
    identity: IdentityState,
    ownership: OwnershipState,
) -> LifecycleState:
    if identity is IdentityState.CONFLICT:
        return LifecycleState.IDENTITY_CONFLICT
    if identity is IdentityState.ABSENT:
        return LifecycleState.ABSENT
    if observation.process_present is None and observation.observed_identity is None:
        return LifecycleState.UNOBSERVED

    if observation.health is HealthState.HEALTHY:
        return LifecycleState.RUNNING_HEALTHY
    if observation.health is HealthState.SYNCING:
        return LifecycleState.RUNNING_SYNCING
    if observation.health is HealthState.UNHEALTHY:
        return LifecycleState.RUNNING_UNHEALTHY

    if ownership is OwnershipState.BRAINK_OWNED:
        return LifecycleState.DISCOVERED_BRAINK_OWNED
    if ownership is OwnershipState.EXTERNAL:
        return LifecycleState.DISCOVERED_EXTERNAL
    return LifecycleState.UNOBSERVED


def classify_service(observation: ServiceObservation) -> ServiceClassification:
    """Return a deterministic, fail-closed classification from supplied evidence."""
    identity = classify_identity(observation)
    ownership = classify_ownership(observation, identity)
    lifecycle = classify_lifecycle(observation, identity, ownership)

    if identity is IdentityState.CONFLICT:
        evidence_classification = EvidenceClassification.FAILED
    elif (
        observation.process_present is None
        and observation.observed_identity is None
        and observation.health is HealthState.UNKNOWN
    ):
        evidence_classification = EvidenceClassification.UNOBSERVED
    else:
        evidence_classification = EvidenceClassification.OBSERVED

    shutdown_authority = (
        identity is IdentityState.VERIFIED
        and ownership is OwnershipState.BRAINK_OWNED
    )

    return ServiceClassification(
        service_id=observation.service_id,
        identity=identity,
        ownership=ownership,
        health=observation.health,
        lifecycle=lifecycle,
        evidence_classification=evidence_classification,
        shutdown_authority=shutdown_authority,
        contradictions=observation.contradictions,
    )
