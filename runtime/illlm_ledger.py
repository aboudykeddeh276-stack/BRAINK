#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
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
    """Canonical append-only learning ledger.

    Any BRAINK, VFS, tool, peer, node, domain runtime or other local learner may
    emit a candidate at its own level. The event becomes canonical only after
    IL-LLM-normalized semantics are appended here and the hash-chain readback
    verifies. Local mirrors may project this ledger; they do not supersede it.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        default = Path(os.environ.get("BRAINK_DATA_DIR", ".kex/state")) / "illlm-immutable-ledger.jsonl"
        self.path = Path(path or os.environ.get("ILLLM_IMMUTABLE_LEDGER", default)).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def head(self) -> str:
        events = self._events()
        return str(events[-1]["event_root"]) if events else GENESIS

    def append(
        self,
        *,
        source_uri: str,
        source_level: str,
        semantic_type: str,
        correlation_id: str,
        payload: Mapping[str, Any],
        lexical_state: Mapping[str, Any],
        illlm_state: Mapping[str, Any],
    ) -> LedgerEvent:
        if not source_uri or not source_level or not semantic_type or not correlation_id:
            raise ValueError("ledger identity fields are required")
        previous = self.head()
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
            "previous_event_root": previous,
        }
        event_id = root({"correlation_id": correlation_id, "source_uri": source_uri, "semantic_type": semantic_type, "illlm_root": body["illlm_root"]})
        body["event_id"] = event_id
        body["event_root"] = root(body)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        event = LedgerEvent(**body)
        self.verify_head(event.event_root)
        return event

    def verify(self) -> dict[str, Any]:
        previous = GENESIS
        count = 0
        for event in self._events():
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

    def verify_head(self, expected: str) -> None:
        result = self.verify()
        if result.get("status") != "PASS" or result.get("head") != expected:
            raise RuntimeError("ILLLM_LEDGER_READBACK_FAILED")

    def read_by_correlation(self, correlation_id: str) -> list[dict[str, Any]]:
        return [event for event in self._events() if event.get("correlation_id") == correlation_id]
