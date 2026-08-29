from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional


class GuardError(RuntimeError):
    def __init__(self, status: int, code: str, retry_after: Optional[int] = None):
        super().__init__(code)
        self.status = status
        self.code = code
        self.retry_after = retry_after


@dataclass(frozen=True)
class GuardDecision:
    agent_id: str
    request_id: str
    accepted: bool
    status: int
    code: str
    checked_at: float
    retry_after: Optional[int] = None


class PersistentRequestGuard:
    """Persistent replay prevention and per-agent mutation rate limiting.

    The guard stores single-consumption request identifiers and mutation windows
    atomically. Corrupt state fails closed. It is designed as a reusable K-APP
    applet for Legal Process and every authenticated mutation-capable runtime.
    """

    def __init__(
        self,
        state_path: Path,
        freshness_seconds: int = 300,
        window_seconds: int = 60,
        max_mutations_per_window: int = 30,
    ):
        self.state_path = Path(state_path)
        self.freshness_seconds = freshness_seconds
        self.window_seconds = window_seconds
        self.max_mutations_per_window = max_mutations_per_window
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load_fail_closed()

    def _default_state(self) -> Dict[str, Any]:
        return {"schema": 1, "seen": {}, "agents": {}}

    def _load_fail_closed(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            state = self._default_state()
            self._atomic_write(state)
            return state
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"guard_state_corrupt:{type(exc).__name__}") from exc
        if (
            state.get("schema") != 1
            or not isinstance(state.get("seen"), dict)
            or not isinstance(state.get("agents"), dict)
        ):
            raise RuntimeError("guard_state_corrupt:invalid_schema")
        return state

    def _atomic_write(self, state: Dict[str, Any]) -> None:
        encoded = json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            prefix=self.state_path.name + ".", dir=str(self.state_path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.state_path)
            dir_fd = os.open(self.state_path.parent, os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def _prune(self, now: float) -> None:
        seen_cutoff = now - max(self.freshness_seconds, self.window_seconds) * 2
        self._state["seen"] = {
            request_id: timestamp
            for request_id, timestamp in self._state["seen"].items()
            if float(timestamp) >= seen_cutoff
        }
        for agent_id, events in list(self._state["agents"].items()):
            kept = [
                float(timestamp)
                for timestamp in events
                if float(timestamp) >= now - self.window_seconds
            ]
            if kept:
                self._state["agents"][agent_id] = kept
            else:
                self._state["agents"].pop(agent_id, None)

    def check_and_consume(
        self,
        agent_id: str,
        request_id: str,
        request_timestamp: float,
        now: Optional[float] = None,
    ) -> GuardDecision:
        now = time.time() if now is None else float(now)
        if not request_id:
            raise GuardError(428, "missing_request_id")
        if request_timestamp is None:
            raise GuardError(428, "missing_request_timestamp")
        if abs(now - float(request_timestamp)) > self.freshness_seconds:
            raise GuardError(408, "stale_request")

        self._prune(now)
        if request_id in self._state["seen"]:
            raise GuardError(409, "replayed_request")

        events = list(self._state["agents"].get(agent_id, []))
        if len(events) >= self.max_mutations_per_window:
            oldest = min(events)
            retry_after = max(1, int(self.window_seconds - (now - oldest)))
            raise GuardError(429, "mutation_rate_exceeded", retry_after=retry_after)

        self._state["seen"][request_id] = now
        events.append(now)
        self._state["agents"][agent_id] = events
        self._atomic_write(self._state)
        return GuardDecision(agent_id, request_id, True, 200, "accepted", now)

    def status(self, now: Optional[float] = None) -> Dict[str, Any]:
        now = time.time() if now is None else float(now)
        self._prune(now)
        return {
            "state": "HEALTHY",
            "schema": self._state["schema"],
            "persistent": True,
            "freshness_seconds": self.freshness_seconds,
            "window_seconds": self.window_seconds,
            "max_mutations_per_window": self.max_mutations_per_window,
            "tracked_request_ids": len(self._state["seen"]),
            "tracked_agents": len(self._state["agents"]),
            "observed_at": now,
        }


def guard_headers(headers: Dict[str, str]) -> tuple[str, float]:
    request_id = headers.get("x-kex-request-id", "")
    timestamp_raw = headers.get("x-kex-request-timestamp")
    if timestamp_raw is None:
        raise GuardError(428, "missing_request_timestamp")
    try:
        timestamp = float(timestamp_raw)
    except ValueError as exc:
        raise GuardError(408, "invalid_request_timestamp") from exc
    return request_id, timestamp


def decision_payload(decision: GuardDecision) -> Dict[str, Any]:
    return asdict(decision)
