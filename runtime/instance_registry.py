"""BRAINK resident instance registry extracted from the MINING carrier.

Provenance source:
  repo: aboudykeddeh276-stack/MINING
  path: backend/braink_core.py
  source_blob_sha: a0d72fb189efb34ea68c96d338bd13c140607fa8

This module intentionally excludes the source carrier's placeholder chat fallback,
KEX-L placeholder, biological-sync placeholder, and unsubstantiated capability
flags. It keeps only deterministic instance registration, directive handling,
restart accounting, and canonical state export.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict

DEFAULT_HEARTBEAT_INTERVAL = 5.0
DEFAULT_MAX_RESTART_ATTEMPTS = 2


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass
class InstanceRecord:
    instance_id: str
    instance_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    heartbeat_interval: float = DEFAULT_HEARTBEAT_INTERVAL
    max_restart_attempts: int = DEFAULT_MAX_RESTART_ATTEMPTS
    restart_attempts: int = 0
    force_restart: bool = False

    def snapshot(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "instance_type": self.instance_type,
            "metadata": copy.deepcopy(self.metadata),
            "heartbeat_interval": self.heartbeat_interval,
            "max_restart_attempts": self.max_restart_attempts,
            "restart_attempts": self.restart_attempts,
            "force_restart": self.force_restart,
        }


class InstanceRegistry:
    """Deterministic in-process BRAINK instance/directive state."""

    def __init__(self) -> None:
        self._instances: Dict[str, InstanceRecord] = {}
        self._directives: Dict[str, Dict[str, Any]] = {}

    def register(self, instance_id: str, instance_type: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if not instance_id or not instance_type:
            return {"status": "rejected", "reason": "missing_identity"}
        if instance_id in self._instances:
            return {"status": "already_registered", "instance_id": instance_id}
        self._instances[instance_id] = InstanceRecord(
            instance_id=instance_id,
            instance_type=instance_type,
            metadata=copy.deepcopy(metadata or {}),
        )
        return {"status": "registered", "instance_id": instance_id}

    def apply_directive(self, instance_id: str, directive: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        record = self._instances.get(instance_id)
        if record is None:
            return {"status": "rejected", "reason": "unknown_instance", "instance_id": instance_id}
        params = copy.deepcopy(params or {})
        try:
            if directive == "set_heartbeat_interval":
                interval = float(params.get("interval", DEFAULT_HEARTBEAT_INTERVAL))
                if interval <= 0:
                    raise ValueError("interval must be positive")
                record.heartbeat_interval = interval
            elif directive == "set_max_restart_attempts":
                attempts = int(params.get("attempts", DEFAULT_MAX_RESTART_ATTEMPTS))
                if attempts < 0:
                    raise ValueError("attempts must be non-negative")
                record.max_restart_attempts = attempts
            elif directive == "force_restart":
                record.force_restart = True
            else:
                return {"status": "rejected", "reason": "unsupported_directive", "directive": directive}
        except (TypeError, ValueError) as exc:
            return {"status": "rejected", "reason": "invalid_parameters", "detail": str(exc)}

        self._directives[instance_id] = {"directive": directive, "params": params}
        return {"status": "directive_applied", "instance_id": instance_id, "directive": directive}

    def record_restart_attempt(self, instance_id: str) -> Dict[str, Any]:
        record = self._instances.get(instance_id)
        if record is None:
            return {"status": "rejected", "reason": "unknown_instance", "instance_id": instance_id}
        record.restart_attempts += 1
        return {
            "status": "restart_recorded",
            "instance_id": instance_id,
            "restart_attempts": record.restart_attempts,
            "limit_reached": record.restart_attempts >= record.max_restart_attempts,
        }

    def state(self) -> Dict[str, Any]:
        return {
            "instances": {key: self._instances[key].snapshot() for key in sorted(self._instances)},
            "directives": copy.deepcopy({key: self._directives[key] for key in sorted(self._directives)}),
        }

    def state_hash(self) -> str:
        return hashlib.sha256(_canonical_bytes(self.state())).hexdigest()
