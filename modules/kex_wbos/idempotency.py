#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from hardening import atomic_write_text, canonical_json_bytes, path_mutex, sha256_bytes

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


class IdempotencyRegistry:
    """Persistent duplicate-suppression registry for action commands.

    One registry owns one logical action namespace. NEW commands are durably
    reserved as INFLIGHT before mutation; completed commands replay their prior
    receipt; key reuse with different payload is rejected. Completed history is
    bounded by TTL/count while INFLIGHT entries are never silently evicted.
    """

    def __init__(self, path: Path):
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self._mutex = path_mutex(path)

    def _locked(self):
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
            return {"version": 1, "commands": {}}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("version") != 1 or not isinstance(payload.get("commands"), dict):
            raise RuntimeError("idempotency registry format invalid")
        return payload

    def _compact(self, payload: dict[str, Any], now: float) -> None:
        ttl = max(60, int(os.getenv("KEX_IDEMPOTENCY_COMPLETED_TTL_SEC", "86400")))
        max_completed = max(100, int(os.getenv("KEX_IDEMPOTENCY_MAX_COMPLETED", "10000")))
        commands = payload["commands"]
        completed: list[tuple[str, dict[str, Any]]] = []
        for key, record in list(commands.items()):
            if record.get("state") != "COMPLETED":
                continue
            completed_at = float(record.get("completedAt", record.get("reservedAt", 0)) or 0)
            if completed_at and now - completed_at > ttl:
                commands.pop(key, None)
                continue
            completed.append((key, record))
        if len(completed) > max_completed:
            completed.sort(key=lambda item: float(item[1].get("completedAt", 0) or 0))
            for key, _ in completed[: len(completed) - max_completed]:
                commands.pop(key, None)

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
            now = time.time()
            self._compact(state, now)
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
                "reservedAt": now,
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
            now = time.time()
            record.update({
                "state": "COMPLETED",
                "completedAt": now,
                "receipt": receipt,
                "receiptHash": receipt.get("receiptHash"),
            })
            self._compact(state, now)
            self._write(state)
        finally:
            self._unlock(fd)
