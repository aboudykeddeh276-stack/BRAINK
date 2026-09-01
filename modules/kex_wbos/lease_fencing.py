#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from hardening import atomic_write_text, path_mutex

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


class LeaseFenceRegistry:
    """Persistent local lease/fence registry for governed resources.

    The registry separates ownership recovery from effect truth. A stale lease may
    be replaced by a newer owner, but that does not imply an external side effect
    is safe to replay. Every takeover increments a monotonically increasing fence.
    Local mutation paths can call validate_fence() immediately before publishing
    state and reject a resumed predecessor carrying an older fence.
    """

    VERSION = 1
    EFFECT_STATES = {
        "EFFECT_NOT_STARTED",
        "EFFECT_PENDING",
        "EFFECT_CONFIRMED",
        "EFFECT_AMBIGUOUS",
        "COMPLETED",
        "COMPENSATED",
        "MANUAL_RECONCILIATION",
    }

    def __init__(self, path: Path):
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self._mutex = path_mutex(path)

    def _locked(self) -> int:
        self._mutex.acquire()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
            if fcntl is not None:
                fcntl.flock(fd, fcntl.LOCK_EX)
            return fd
        except Exception:
            self._mutex.release()
            raise

    def _unlock(self, fd: int) -> None:
        try:
            if fcntl is not None:
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        finally:
            self._mutex.release()

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": self.VERSION, "resources": {}}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("version") != self.VERSION or not isinstance(payload.get("resources"), dict):
            raise RuntimeError("lease fence registry format invalid")
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        atomic_write_text(self.path, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    @staticmethod
    def _valid_id(value: str) -> bool:
        return bool(value) and len(value) <= 300

    def acquire(self, resource: str, owner: str, lease_seconds: float, *, now: float | None = None) -> dict[str, Any]:
        if not self._valid_id(resource) or not self._valid_id(owner):
            return {"state": "INVALID_ID"}
        if lease_seconds <= 0:
            return {"state": "INVALID_LEASE"}
        current = time.time() if now is None else float(now)
        fd = self._locked()
        try:
            payload = self._read()
            existing = payload["resources"].get(resource)
            if existing is not None:
                expires_at = float(existing.get("expiresAt", 0) or 0)
                if expires_at > current:
                    return {
                        "state": "HELD",
                        "resource": resource,
                        "owner": existing.get("owner"),
                        "fence": existing.get("fence"),
                        "expiresAt": expires_at,
                        "effectState": existing.get("effectState", "EFFECT_NOT_STARTED"),
                    }
                prior_fence = int(existing.get("fence", 0) or 0)
                prior_owner = existing.get("owner")
                prior_effect = existing.get("effectState", "EFFECT_NOT_STARTED")
            else:
                prior_fence = 0
                prior_owner = None
                prior_effect = "EFFECT_NOT_STARTED"

            fence = prior_fence + 1
            generation = int(existing.get("generation", 0) or 0) + 1 if existing else 1
            record = {
                "resource": resource,
                "owner": owner,
                "fence": fence,
                "generation": generation,
                "acquiredAt": current,
                "heartbeatAt": current,
                "expiresAt": current + float(lease_seconds),
                "leaseSeconds": float(lease_seconds),
                "effectState": prior_effect if prior_effect in {"EFFECT_AMBIGUOUS", "MANUAL_RECONCILIATION"} else "EFFECT_NOT_STARTED",
                "takeover": existing is not None,
                "priorOwner": prior_owner,
                "priorFence": prior_fence if existing is not None else None,
            }
            payload["resources"][resource] = record
            self._write(payload)
            return {"state": "ACQUIRED", **record}
        finally:
            self._unlock(fd)

    def heartbeat(self, resource: str, owner: str, fence: int, *, now: float | None = None) -> dict[str, Any]:
        current = time.time() if now is None else float(now)
        fd = self._locked()
        try:
            payload = self._read()
            record = payload["resources"].get(resource)
            verdict = self._validate_record(record, owner, fence, current, require_unexpired=True)
            if verdict != "VALID":
                return {"state": verdict}
            lease_seconds = float(record["leaseSeconds"])
            record["heartbeatAt"] = current
            record["expiresAt"] = current + lease_seconds
            self._write(payload)
            return {"state": "RENEWED", "fence": fence, "expiresAt": record["expiresAt"]}
        finally:
            self._unlock(fd)

    def validate_fence(self, resource: str, owner: str, fence: int, *, now: float | None = None, require_unexpired: bool = True) -> dict[str, Any]:
        current = time.time() if now is None else float(now)
        fd = self._locked()
        try:
            record = self._read()["resources"].get(resource)
            return {"state": self._validate_record(record, owner, fence, current, require_unexpired=require_unexpired)}
        finally:
            self._unlock(fd)

    @staticmethod
    def _validate_record(record: dict[str, Any] | None, owner: str, fence: int, now: float, *, require_unexpired: bool) -> str:
        if record is None:
            return "NO_LEASE"
        current_fence = int(record.get("fence", 0) or 0)
        if int(fence) < current_fence:
            return "FENCED"
        if int(fence) > current_fence:
            return "UNKNOWN_FENCE"
        if record.get("owner") != owner:
            return "OWNER_MISMATCH"
        if require_unexpired and float(record.get("expiresAt", 0) or 0) <= now:
            return "EXPIRED"
        return "VALID"

    def mark_effect(self, resource: str, owner: str, fence: int, effect_state: str, *, now: float | None = None) -> dict[str, Any]:
        if effect_state not in self.EFFECT_STATES:
            return {"state": "INVALID_EFFECT_STATE"}
        current = time.time() if now is None else float(now)
        fd = self._locked()
        try:
            payload = self._read()
            record = payload["resources"].get(resource)
            verdict = self._validate_record(record, owner, fence, current, require_unexpired=False)
            if verdict != "VALID":
                return {"state": verdict}
            record["effectState"] = effect_state
            record["effectUpdatedAt"] = current
            self._write(payload)
            return {"state": "RECORDED", "effectState": effect_state, "fence": fence}
        finally:
            self._unlock(fd)

    def release(self, resource: str, owner: str, fence: int, *, now: float | None = None) -> dict[str, Any]:
        current = time.time() if now is None else float(now)
        fd = self._locked()
        try:
            payload = self._read()
            record = payload["resources"].get(resource)
            verdict = self._validate_record(record, owner, fence, current, require_unexpired=False)
            if verdict != "VALID":
                return {"state": verdict}
            record["releasedAt"] = current
            record["expiresAt"] = current
            self._write(payload)
            return {"state": "RELEASED", "fence": fence}
        finally:
            self._unlock(fd)
