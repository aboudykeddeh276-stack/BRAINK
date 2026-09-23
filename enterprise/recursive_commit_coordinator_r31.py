from __future__ import annotations

"""Crash-recoverable coordinator for the native R26 computer.json + ledger.json ABI.

Why this module exists
----------------------
R26 already has the correct *domain* formats:
  - computer.json is the native recursive-computer snapshot.
  - ledger.json is a list of TransactionReceipt dictionaries.

R31 proved a different property: a state replacement and its audit receipt need one
recoverable logical transaction.  Replacing R26's formats with R31's generic
{commit_id,payload} wrapper would break the persisted ABI, warm boot and descendant
readback.  This coordinator therefore imports the R31 transaction discipline while
preserving the R26 representations byte-for-byte at the public persistence boundary.

Protocol
--------
PREPARE journal -> durable native state -> durable native ledger -> correspondence
verification -> journal retirement.

If a process dies in the middle, recover() uses the journal's previous/next hashes to
classify the exact phase.  Unknown divergence fails closed; it is never guessed away.
"""

from dataclasses import asdict
from pathlib import Path
from typing import Any
import fcntl
import hashlib
import json
import os
import time
import uuid

from runtime.R25.system_evolution_runtime import (
    AppendOnlyLedger,
    TransactionReceipt,
    canonical_json,
    sha256_json,
)


def _copy(value: Any) -> Any:
    return json.loads(canonical_json(value))


def _hash(value: Any) -> str:
    return sha256_json(value)


def _durable_replace(path: Path, value: Any) -> str:
    """Durably replace one JSON object and its directory entry."""
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_json(value).encode("utf-8")
    tmp = path.with_name(path.name + ".r31.tmp")
    try:
        with tmp.open("wb") as fh:
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if tmp.exists():
            tmp.unlink()
    return hashlib.sha256(raw).hexdigest()


def _read(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text("utf-8"))


class RecursiveCommitCoordinatorR31:
    """Recoverable logical commit for one RecursiveComputer state root."""

    SCHEMA = "kex.braink.recursive-native-commit.r31.v1"

    def __init__(self, state_root: str | Path):
        self.root = Path(state_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "computer.json"
        self.ledger_path = self.root / "ledger.json"
        self.journal_path = self.root / "recursive-transition-journal-r31.json"
        self.lock_path = self.root / ".recursive-transition-r31.lock"
        self.lock_path.touch(exist_ok=True)

    def _lock(self):
        return self.lock_path.open("r+")

    @staticmethod
    def verify_native_ledger(events: list[dict[str, Any]]) -> bool:
        try:
            ledger = AppendOnlyLedger()
            ledger._events = [TransactionReceipt(**event) for event in events]
            return ledger.verify()
        except Exception:
            return False

    def _classify_locked(self, tx: dict[str, Any] | None = None) -> dict[str, Any]:
        state = _read(self.state_path)
        ledger = _read(self.ledger_path, [])
        if state is None:
            return {"status": "STATE_MISSING"}
        if not self.verify_native_ledger(ledger):
            return {"status": "LEDGER_CORRUPTED"}
        if tx is None:
            tx = _read(self.journal_path)
        if tx is None:
            return {
                "status": "CONSISTENT",
                "state_hash": _hash(state),
                "ledger_hash": _hash(ledger),
                "ledger_events": len(ledger),
            }

        sh = _hash(state)
        lh = _hash(ledger)
        old_s, new_s = tx["previous_state_hash"], tx["next_state_hash"]
        old_l, new_l = tx["previous_ledger_hash"], tx["next_ledger_hash"]

        if sh == old_s and lh == old_l:
            status = "PREPARED_ONLY"
        elif sh == new_s and lh == old_l:
            status = "STATE_AHEAD_OF_LEDGER"
        elif sh == old_s and lh == new_l:
            status = "LEDGER_AHEAD_OF_STATE"
        elif sh == new_s and lh == new_l:
            status = "COMMITTED_WITH_JOURNAL"
        else:
            status = "UNRESOLVED_DIVERGENCE"
        return {
            "status": status,
            "transition_id": tx.get("transition_id"),
            "state_hash": sh,
            "ledger_hash": lh,
        }

    def classify(self) -> dict[str, Any]:
        with self._lock() as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                return self._classify_locked()
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _retire_journal_locked(self) -> None:
        if self.journal_path.exists():
            self.journal_path.unlink()
            dfd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)

    def _recover_locked(self) -> dict[str, Any]:
        tx = _read(self.journal_path)
        if tx is None:
            return self._classify_locked(None)
        if tx.get("schema") != self.SCHEMA:
            return {"status": "BLOCKED_UNKNOWN_JOURNAL_SCHEMA"}

        classification = self._classify_locked(tx)
        status = classification["status"]
        if status == "PREPARED_ONLY":
            # No target mutated. Retire the unexecuted intent.
            self._retire_journal_locked()
            return {"status": "RECOVERED_ROLLBACK", "from": status}
        if status == "STATE_AHEAD_OF_LEDGER":
            _durable_replace(self.ledger_path, tx["next_ledger"])
        elif status == "LEDGER_AHEAD_OF_STATE":
            _durable_replace(self.state_path, tx["next_state"])
        elif status == "COMMITTED_WITH_JOURNAL":
            pass
        else:
            return {"status": "BLOCKED_UNRESOLVED_DIVERGENCE", "classification": classification}

        final = self._classify_locked(tx)
        if final["status"] != "COMMITTED_WITH_JOURNAL":
            return {"status": "BLOCKED_RECOVERY_CORRESPONDENCE_FAILED", "classification": final}
        self._retire_journal_locked()
        return {
            "status": "RECOVERED_COMMIT",
            "from": status,
            "transition_id": tx["transition_id"],
            "state_hash": tx["next_state_hash"],
            "ledger_hash": tx["next_ledger_hash"],
        }

    def recover(self) -> dict[str, Any]:
        with self._lock() as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                return self._recover_locked()
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def commit(
        self,
        *,
        operation: str,
        actor: str,
        owner: str,
        lineage: tuple[str, ...] | list[str],
        previous_state: dict[str, Any] | None,
        next_state: dict[str, Any],
        proof: dict[str, Any],
        rollback: dict[str, Any],
        crash_phase: str | None = None,
    ) -> dict[str, Any]:
        """Commit native R26 state and its exact next TransactionReceipt together logically."""
        with self._lock() as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                if self.journal_path.exists():
                    recovered = self._recover_locked()
                    if recovered["status"] not in {"CONSISTENT", "RECOVERED_COMMIT", "RECOVERED_ROLLBACK"}:
                        raise RuntimeError(f"UNRESOLVED_PRIOR_TRANSACTION:{recovered}")

                disk_state = _read(self.state_path)
                disk_ledger = _read(self.ledger_path, [])
                if disk_state != previous_state:
                    raise RuntimeError("STALE_STATE_CONFLICT")
                if not self.verify_native_ledger(disk_ledger):
                    raise RuntimeError("COMMITTED_LEDGER_INVALID")

                ledger = AppendOnlyLedger()
                ledger._events = [TransactionReceipt(**event) for event in disk_ledger]
                ledger.append(
                    operation=operation,
                    actor=actor,
                    owner=owner,
                    input_state=previous_state if previous_state is not None else next_state,
                    output_state=next_state,
                    proof=proof,
                    rollback=rollback,
                    lineage=lineage,
                )
                next_ledger = [asdict(event) for event in ledger.events]

                tx = {
                    "schema": self.SCHEMA,
                    "transition_id": "RTX-" + uuid.uuid4().hex,
                    "operation": operation,
                    "phase": "PREPARED",
                    "previous_state": _copy(previous_state),
                    "previous_state_hash": _hash(previous_state),
                    "previous_ledger": _copy(disk_ledger),
                    "previous_ledger_hash": _hash(disk_ledger),
                    "next_state": _copy(next_state),
                    "next_state_hash": _hash(next_state),
                    "next_ledger": _copy(next_ledger),
                    "next_ledger_hash": _hash(next_ledger),
                    "prepared_ns": time.time_ns(),
                }
                _durable_replace(self.journal_path, tx)
                if crash_phase == "AFTER_PREPARE":
                    os._exit(91)

                _durable_replace(self.state_path, tx["next_state"])
                tx["phase"] = "STATE_COMMITTED"
                _durable_replace(self.journal_path, tx)
                if crash_phase == "AFTER_STATE":
                    os._exit(92)

                _durable_replace(self.ledger_path, tx["next_ledger"])
                tx["phase"] = "LEDGER_COMMITTED"
                _durable_replace(self.journal_path, tx)
                if crash_phase == "AFTER_LEDGER":
                    os._exit(93)

                classification = self._classify_locked(tx)
                if classification["status"] != "COMMITTED_WITH_JOURNAL":
                    raise RuntimeError(f"POST_COMMIT_CORRESPONDENCE_FAILED:{classification}")
                self._retire_journal_locked()
                return {
                    "status": "COMMITTED",
                    "transition_id": tx["transition_id"],
                    "state_hash": tx["next_state_hash"],
                    "ledger_hash": tx["next_ledger_hash"],
                    "ledger_events": len(next_ledger),
                    "state": _copy(next_state),
                    "ledger": _copy(next_ledger),
                }
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
