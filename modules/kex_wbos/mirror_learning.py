#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from hardening import append_jsonl_fsync, atomic_write_text, canonical_json_bytes, sha256_bytes


class MirrorLearningLane:
    """Observer-relative learning lane over canonical state transitions.

    Canonical identity is never overwritten by the mirror. The lane records
    transition evidence and materializes the latest observer projection plus the
    delta from its predecessor so IL-LLM can traverse learned state explicitly.
    """

    def __init__(self, root: Path):
        self.root = root
        self.events = root / "learning-events.jsonl"
        self.projections = root / "projections"

    @staticmethod
    def _projection_id(observer: str, subject: str) -> str:
        return sha256_bytes(canonical_json_bytes({"observer": observer, "subject": subject}))

    def record_transition(
        self,
        *,
        observer: str,
        subject: str,
        canonical_generation: str,
        event_class: str,
        before: dict[str, Any] | None,
        after: dict[str, Any],
        evidence: list[str] | None = None,
        confidence: float | None = None,
        now: float | None = None,
    ) -> dict[str, Any]:
        ts = time.time() if now is None else float(now)
        before_state = before or {}
        delta = self._delta(before_state, after)
        event = {
            "schema": "kex.mirror.learning-event.v1",
            "observer": observer,
            "subject": subject,
            "canonicalGeneration": canonical_generation,
            "eventClass": event_class,
            "beforeHash": sha256_bytes(canonical_json_bytes(before_state)),
            "afterHash": sha256_bytes(canonical_json_bytes(after)),
            "delta": delta,
            "evidence": evidence or [],
            "confidence": confidence,
            "observedAt": ts,
        }
        _, persisted = append_jsonl_fsync(
            self.events,
            event,
            row_field="learningRow",
            hash_field="learningHash",
            parent_hash_field="parentLearningHash",
        )
        projection = {
            "schema": "kex.mirror.projection.v1",
            "observer": observer,
            "subject": subject,
            "canonicalGeneration": canonical_generation,
            "projection": after,
            "lastDelta": delta,
            "lastLearningHash": persisted["learningHash"],
            "updatedAt": ts,
        }
        projection["projectionHash"] = sha256_bytes(canonical_json_bytes(projection))
        path = self._projection_path(observer, subject)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(projection, indent=2, sort_keys=True) + "\n")
        return {"state": "LEARNED", "event": persisted, "projection": projection}

    def read_projection(self, observer: str, subject: str) -> dict[str, Any] | None:
        path = self._projection_path(observer, subject)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        observed = payload.get("projectionHash")
        unsigned = dict(payload)
        unsigned.pop("projectionHash", None)
        expected = sha256_bytes(canonical_json_bytes(unsigned))
        if observed != expected:
            raise RuntimeError("mirror projection integrity failure")
        return payload

    def rehydrate_projection(
        self,
        *,
        observer: str,
        subject: str,
        canonical_generation: str,
        canonical_state: dict[str, Any],
    ) -> dict[str, Any]:
        current = self.read_projection(observer, subject)
        if current is None:
            return {
                "state": "REBUILD_REQUIRED",
                "reason": "NO_PRIOR_PROJECTION",
                "projection": canonical_state,
            }
        if current.get("canonicalGeneration") == canonical_generation:
            return {"state": "REHYDRATED", "projection": current}
        return {
            "state": "REHYDRATED_WITH_VERSION_TRANSITION",
            "priorGeneration": current.get("canonicalGeneration"),
            "canonicalGeneration": canonical_generation,
            "projection": canonical_state,
            "priorProjection": current,
        }

    def _projection_path(self, observer: str, subject: str) -> Path:
        return self.projections / f"{self._projection_id(observer, subject)}.json"

    @staticmethod
    def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        added: dict[str, Any] = {}
        changed: dict[str, dict[str, Any]] = {}
        removed: list[str] = []
        for key, value in after.items():
            if key not in before:
                added[key] = value
            elif before[key] != value:
                changed[key] = {"before": before[key], "after": value}
        for key in before:
            if key not in after:
                removed.append(key)
        return {"added": added, "changed": changed, "removed": sorted(removed)}
