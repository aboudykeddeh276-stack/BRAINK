#!/usr/bin/env python3
"""Native IL-LLM immutable learning ledger with interprocess atomic admission.

Preserves the existing event schema, canonical SHA-256 format, public API,
source/lexical roots and the A. Keddeh KS-BRAINK-IL-LLM identity.
Native append-only files are evidence only when the whole chain verifies.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "illlm.immutable-ledger.v1"
GENESIS = "GENESIS"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def root(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class LedgerEvent:
    schema: str
    event_id: str
    timestamp_ns: int
    source_uri: str
    source_level: str
    semantic_type: str
    correlation_id: str
    payload: Mapping[str, Any]
    lexical_root: str
    illlm_root: str
    previous_event_root: str
    event_root: str


class ILLLMImmutableLedger:
    """Hash-chained, process-serialized IL-LLM candidate and learning ledger.

    All cooperating readers/writers acquire the same dedicated OS-backed lock.
    This guarantees a single predecessor observation per append across distinct
    host workers, without altering the historical event schema or event hashes.
    It does not protect the ledger from privileged out-of-band filesystem edits.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        default = Path(os.environ.get("BRAINK_DATA_DIR", ".kex/state")) / "illlm-immutable-ledger.jsonl"
        self.path = Path(path or os.environ.get("ILLLM_IMMUTABLE_LEDGER", default)).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path = self.path.with_name(self.path.name + ".lock")

    @contextmanager
    def _locked(self, *, shared: bool = False):
        # A distinct stable lock inode remains in place; never unlink the lock
        # file when releasing it, since queued processes retain that inode.
        with self._lock_path.open("a+b") as gate:
            if os.name == "posix":
                import fcntl
                fcntl.flock(gate.fileno(), fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(gate.fileno(), fcntl.LOCK_UN)
            elif os.name == "nt":
                import msvcrt
                # Windows byte-range locks are exclusive, including reads.
                gate.seek(0, os.SEEK_END)
                if gate.tell() == 0:
                    gate.write(b'!')
                    gate.flush()
                gate.seek(0)
                msvcrt.locking(gate.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    gate.seek(0)
                    msvcrt.locking(gate.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                raise OSError("UNSUPPORTED_PLATFORM_NO_SAFE_LEDGER_LOCK")

    def _events_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        # Strict decode: corrupt, truncated, or unparseable rows fail closed.
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    events.append(json.loads(line))
        return events

    def _events(self) -> list[dict[str, Any]]:
        with self._locked(shared=True):
            return self._events_unlocked()

    def _verify_unlocked(self) -> dict[str, Any]:
        previous = GENESIS
        count = 0
        try:
            events = self._events_unlocked()
        except (ValueError, UnicodeError) as exc:
            return {"status": "FAILED", "reason": "UNPARSEABLE_LEDGER", "index": count, "detail": type(exc).__name__}
        for event in events:
            if not isinstance(event, dict):
                return {"status": "FAILED", "reason": "NON_OBJECT_EVENT", "index": count}
            if event.get("schema") != SCHEMA:
                return {"status": "FAILED", "reason": "SCHEMA", "index": count}
            if event.get("previous_event_root") != previous:
                return {"status": "FAILED", "reason": "CHAIN", "index": count}
            body = {k: v for k, v in event.items() if k != "event_root"}
            expected = root(body)
            if event.get("event_root") != expected:
                return {"status": "FAILED", "reason": "ROOT", "index": count}
            previous = expected
            count += 1
        return {"status": "PASS", "events": count, "head": previous}

    def head(self) -> str:
        verified = self.verify()
        if verified["status"] != "PASS":
            raise RuntimeError("ILLLM_LEDGER_UNVERIFIED")
        return verified["head"]

    def append(self, *, source_uri: str, source_level: str, semantic_type: str,
               correlation_id: str, payload: Mapping[str, Any],
               lexical_state: Mapping[str, Any], illlm_state: Mapping[str, Any],
               idempotency_payload_field: str | None = None) -> LedgerEvent:
        if not source_uri or not source_level or not semantic_type or not correlation_id:
            raise ValueError("ledger identity fields are required")
        with self._locked():
            before = self._verify_unlocked()
            if before["status"] != "PASS":
                raise RuntimeError("ILLLM_LEDGER_UNVERIFIED_BEFORE_APPEND")
            # Exactly-once admission for callers with a stable correlation ID.
            # This check MUST share the exclusive predecessor/append lock; a
            # preflight read alone cannot exclude simultaneous host workers.
            if idempotency_payload_field is not None:
                if (not isinstance(idempotency_payload_field, str)
                        or idempotency_payload_field not in payload):
                    raise ValueError("INVALID_IDEMPOTENCY_FIELD")
                matches = [event for event in self._events_unlocked()
                           if event.get("correlation_id") == correlation_id]
                if matches:
                    if (len(matches) != 1
                            or matches[0].get("source_uri") != source_uri
                            or matches[0].get("source_level") != source_level
                            or matches[0].get("semantic_type") != semantic_type
                            or matches[0].get("payload", {}).get(idempotency_payload_field)
                            != payload[idempotency_payload_field]
                            or matches[0].get("lexical_root") != root(lexical_state)
                            or matches[0].get("illlm_root") != root(illlm_state)):
                        raise ValueError("CORRELATION_REPLAY_CONFLICT")
                    return LedgerEvent(**matches[0])
            body = {
                "schema": SCHEMA,
                "timestamp_ns": time.time_ns(),
                "source_uri": source_uri,
                "source_level": source_level,
                "semantic_type": semantic_type,
                "correlation_id": correlation_id,
                "payload": dict(payload),
                "lexical_root": root(lexical_state),
                "illlm_root": root(illlm_state),
                "previous_event_root": before["head"],
            }
            body["event_id"] = root({"correlation_id": correlation_id,
                                     "source_uri": source_uri,
                                     "semantic_type": semantic_type,
                                     "illlm_root": body["illlm_root"]})
            body["event_root"] = root(body)
            record = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                written = os.write(fd, record)
                if written != len(record):
                    raise OSError("PARTIAL_LEDGER_APPEND")
                os.fsync(fd)
            finally:
                os.close(fd)
            after = self._verify_unlocked()
            if after.get("status") != "PASS" or after.get("events") != before["events"] + 1 or after.get("head") != body["event_root"]:
                raise RuntimeError("ILLLM_LEDGER_READBACK_FAILED")
        return LedgerEvent(**body)

    def verify(self) -> dict[str, Any]:
        with self._locked(shared=True):
            return self._verify_unlocked()

    def verify_head(self, expected: str) -> None:
        # Preserve the pre-existing strict API: callers requiring a fixed head
        # must fail if a different writer advanced the ledger.
        with self._locked(shared=True):
            result = self._verify_unlocked()
            if result.get("status") != "PASS" or result.get("head") != expected:
                raise RuntimeError("ILLLM_LEDGER_READBACK_FAILED")

    def read_by_correlation(self, correlation_id: str) -> list[dict[str, Any]]:
        with self._locked(shared=True):
            status = self._verify_unlocked()
            if status.get("status") != "PASS":
                raise RuntimeError("ILLLM_LEDGER_UNVERIFIED")
            return [event for event in self._events_unlocked() if event.get("correlation_id") == correlation_id]
