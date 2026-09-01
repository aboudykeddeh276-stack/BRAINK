#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from hardening import atomic_write_text, canonical_json_bytes, sha256_bytes

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


class IdempotencyRegistry:
    """Persistent duplicate-suppression registry for action commands.

    NEW commands are durably reserved as INFLIGHT before mutation. A retry of a
    completed command returns its prior receipt. Reusing a key for a different
    request is a conflict. An interrupted process leaves INFLIGHT state, causing
    retries to stop rather than silently execute the mutation twice.

    This is deliberately not described as distributed exactly-once execution.
    """

    def __init__(self, path: Path):
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")

    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        return fd

    def _unlock(self, fd: int) -> None:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "commands": {}}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("version") != 1 or not isinstance(payload.get("commands"), dict):
            raise RuntimeError("idempotency registry format invalid")
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        atomic_write_text(self.path, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    @staticmethod
    def request_hash(request: dict[str, Any]) -> str:
        normalized = dict(request)
        normalized.pop("idempotencyKey", None)
        return sha256_bytes(canonical_json_bytes(normalized))

    def begin(self, key: str, request: dict[str, Any]) -> dict[str, Any]:
        if not key or len(key) > 200:
            return {"state": "INVALID_KEY"}
        req_hash = self.request_hash(request)
        fd = self._locked()
        try:
            state = self._read()
            existing = state["commands"].get(key)
            if existing:
                if existing.get("requestHash") != req_hash:
                    return {"state": "CONFLICT", "requestHash": req_hash, "existingRequestHash": existing.get("requestHash")}
                if existing.get("state") == "COMPLETED":
                    return {"state": "REPLAY", "requestHash": req_hash, "receipt": existing.get("receipt")}
                return {"state": "INFLIGHT", "requestHash": req_hash, "record": existing}
            state["commands"][key] = {
                "state": "INFLIGHT",
                "requestHash": req_hash,
                "reservedAt": time.time(),
                "receipt": None,
            }
            self._write(state)
            return {"state": "NEW", "requestHash": req_hash}
        finally:
            self._unlock(fd)

    def complete(self, key: str, request_hash: str, receipt: dict[str, Any]) -> None:
        fd = self._locked()
        try:
            state = self._read()
            record = state["commands"].get(key)
            if not record or record.get("requestHash") != request_hash:
                raise RuntimeError("idempotency completion does not match reservation")
            record.update({
                "state": "COMPLETED",
                "completedAt": time.time(),
                "receipt": receipt,
                "receiptHash": receipt.get("receiptHash"),
            })
            self._write(state)
        finally:
            self._unlock(fd)
