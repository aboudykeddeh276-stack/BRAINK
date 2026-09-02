#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from hardening import append_jsonl_fsync, atomic_write_text, canonical_json_bytes, path_mutex, sha256_bytes

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


class DurableOutbox:
    """Durable intent queue for commands whose actuator is outside this process."""

    def __init__(self, path: Path):
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self.history_path = path.with_suffix(path.suffix + ".history.jsonl")
        self._mutex = path_mutex(path)

    def _lock(self) -> int:
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
            return {"version": 1, "items": {}}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("version") != 1 or not isinstance(payload.get("items"), dict):
            raise RuntimeError("outbox format invalid")
        return payload

    def _write(self, state: dict[str, Any]) -> None:
        atomic_write_text(self.path, json.dumps(state, indent=2, sort_keys=True) + "\n")

    def _history(self, event: str, item: dict[str, Any], **extra: Any) -> None:
        append_jsonl_fsync(self.history_path, {
            "ts": time.time(),
            "event": event,
            "outboxId": item.get("outboxId"),
            "idempotencyKey": item.get("idempotencyKey"),
            "commandHash": item.get("commandHash"),
            **extra,
        })

    def stage(self, *, action_class: str, target: str, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        command = {"actionClass": action_class, "target": target, "payload": payload, "idempotencyKey": idempotency_key}
        command_hash = sha256_bytes(canonical_json_bytes(command))
        fd = self._lock()
        try:
            state = self._read()
            existing = state["items"].get(idempotency_key)
            if existing:
                if existing.get("commandHash") != command_hash:
                    self._history("OUTBOX_CONFLICT", existing, incomingCommandHash=command_hash)
                    return {"state": "CONFLICT", "item": existing}
                return {"state": existing.get("state"), "item": existing, "replayed": True}
            item = {
                "outboxId": f"OUT-{uuid.uuid4().hex[:16]}",
                "state": "PENDING",
                "actionClass": action_class,
                "target": target,
                "payload": payload,
                "idempotencyKey": idempotency_key,
                "commandHash": command_hash,
                "attempts": 0,
                "createdAt": time.time(),
                "updatedAt": time.time(),
                "participantReceipt": None,
                "participantReceiptHash": None,
            }
            state["items"][idempotency_key] = item
            self._write(state)
            self._history("OUTBOX_STAGED", item)
            return {"state": "PENDING", "item": item, "replayed": False}
        finally:
            self._unlock(fd)

    def mark_delivered(self, idempotency_key: str, participant_receipt: dict[str, Any]) -> dict[str, Any]:
        incoming_hash = sha256_bytes(canonical_json_bytes(participant_receipt))
        fd = self._lock()
        try:
            state = self._read()
            item = state["items"].get(idempotency_key)
            if not item:
                raise KeyError(idempotency_key)
            if item.get("state") == "DELIVERED":
                existing_hash = item.get("participantReceiptHash")
                if existing_hash == incoming_hash:
                    self._history("OUTBOX_DELIVERY_REPLAY", item, participantReceiptHash=incoming_hash)
                    return item
                self._history("OUTBOX_DELIVERY_CONFLICT", item, existingReceiptHash=existing_hash, incomingReceiptHash=incoming_hash)
                raise RuntimeError("participant receipt conflicts with previously delivered evidence")
            item["state"] = "DELIVERED"
            item["attempts"] = int(item.get("attempts", 0)) + 1
            item["updatedAt"] = time.time()
            item["participantReceipt"] = participant_receipt
            item["participantReceiptHash"] = incoming_hash
            self._write(state)
            self._history("OUTBOX_DELIVERED", item, participantReceiptHash=incoming_hash)
            return item
        finally:
            self._unlock(fd)

    def mark_attempt(self, idempotency_key: str, error: str) -> dict[str, Any]:
        fd = self._lock()
        try:
            state = self._read()
            item = state["items"].get(idempotency_key)
            if not item:
                raise KeyError(idempotency_key)
            if item.get("state") == "DELIVERED":
                self._history("OUTBOX_ATTEMPT_AFTER_DELIVERY_REJECTED", item, error=error)
                return item
            item["attempts"] = int(item.get("attempts", 0)) + 1
            item["updatedAt"] = time.time()
            item["lastError"] = error
            self._write(state)
            self._history("OUTBOX_ATTEMPT_FAILED", item, error=error)
            return item
        finally:
            self._unlock(fd)

    def pending(self) -> list[dict[str, Any]]:
        return [item for item in self._read()["items"].values() if item.get("state") == "PENDING"]
