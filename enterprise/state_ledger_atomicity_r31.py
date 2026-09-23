from __future__ import annotations
from pathlib import Path
from typing import Any
import fcntl, hashlib, json, os, time, uuid


def canonical(v: Any) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha(v: Any) -> str:
    return hashlib.sha256(v if isinstance(v, (bytes, bytearray)) else canonical(v)).hexdigest()


def durable_replace(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical(value)
    tmp = path.with_name(path.name + ".tmp")
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
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text("utf-8"))


class StateLedgerAtomicityR31:
    """Recoverable logical transaction over R26-style state + append-only ledger files.

    This does not pretend two filesystem replacements are physically atomic. It makes the
    logical transition recoverable by persisting a PREPARED intent before either target,
    embedding commit_id in state and ledger, and resolving incomplete phases on restart.
    """
    SCHEMA = "kex.braink.state-ledger-atomicity.r31.v1"

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "computer.json"
        self.ledger_path = self.root / "ledger.json"
        self.journal_path = self.root / "transition-journal.json"
        self.lock_path = self.root / ".transition.lock"
        self.lock_path.touch(exist_ok=True)

    def _lock(self):
        return self.lock_path.open("r+")

    def initialize(self, state: dict[str, Any]) -> dict[str, Any]:
        with self._lock() as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                if self.state_path.exists() or self.ledger_path.exists() or self.journal_path.exists():
                    raise RuntimeError("ALREADY_INITIALIZED")
                genesis_id = "GENESIS-" + uuid.uuid4().hex
                wrapped = {"commit_id": genesis_id, "payload": state}
                state_hash = durable_replace(self.state_path, wrapped)
                event = self._event(1, genesis_id, "GENESIS", None, state_hash, state)
                durable_replace(self.ledger_path, [event])
                classified = self._classify_locked()
                return {**classified, "state": wrapped, "ledger": [event], "journal": None}
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _event(seq: int, commit_id: str, operation: str, prior_event: str | None,
               state_hash: str, payload: Any) -> dict[str, Any]:
        body = {
            "sequence": seq,
            "commit_id": commit_id,
            "operation": operation,
            "previous_event": prior_event,
            "state_hash": state_hash,
            "payload_hash": sha(payload),
        }
        return {**body, "event_id": sha(body)}

    @staticmethod
    def verify_ledger(events: list[dict[str, Any]]) -> bool:
        previous = None
        seen: set[str] = set()
        for seq, event in enumerate(events, 1):
            body = {
                "sequence": seq,
                "commit_id": event.get("commit_id"),
                "operation": event.get("operation"),
                "previous_event": previous,
                "state_hash": event.get("state_hash"),
                "payload_hash": event.get("payload_hash"),
            }
            eid = sha(body)
            if event.get("sequence") != seq or event.get("previous_event") != previous:
                return False
            if event.get("event_id") != eid or eid in seen:
                return False
            seen.add(eid)
            previous = eid
        return True

    def _prepared(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        current = read_json(self.state_path)
        ledger = read_json(self.ledger_path, [])
        if current is None or not self.verify_ledger(ledger):
            raise RuntimeError("PRECONDITION_INVALID")
        commit_id = "TX-" + uuid.uuid4().hex
        next_state = {"commit_id": commit_id, "payload": payload}
        next_state_hash = sha(next_state)
        prior = ledger[-1]["event_id"] if ledger else None
        event = self._event(len(ledger) + 1, commit_id, operation, prior, next_state_hash, payload)
        return {
            "schema": self.SCHEMA,
            "phase": "PREPARED",
            "commit_id": commit_id,
            "operation": operation,
            "previous_state": current,
            "previous_state_hash": sha(current),
            "previous_ledger": ledger,
            "previous_ledger_hash": sha(ledger),
            "next_state": next_state,
            "next_state_hash": next_state_hash,
            "next_event": event,
            "prepared_ns": time.time_ns(),
        }

    def commit(self, operation: str, payload: dict[str, Any], crash_phase: str | None = None) -> dict[str, Any]:
        with self._lock() as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                if self.journal_path.exists():
                    rec = self._recover_locked()
                    if rec["status"] not in {"CONSISTENT", "RECOVERED_COMMIT", "RECOVERED_ROLLBACK"}:
                        raise RuntimeError("UNRESOLVED_PRIOR_TRANSACTION")
                tx = self._prepared(operation, payload)
                durable_replace(self.journal_path, tx)
                if crash_phase == "AFTER_PREPARE": os._exit(91)

                state_hash = durable_replace(self.state_path, tx["next_state"])
                if state_hash != tx["next_state_hash"]:
                    raise RuntimeError("STATE_HASH_MISMATCH")
                tx["phase"] = "STATE_COMMITTED"
                durable_replace(self.journal_path, tx)
                if crash_phase == "AFTER_STATE": os._exit(92)

                ledger = list(tx["previous_ledger"]) + [tx["next_event"]]
                durable_replace(self.ledger_path, ledger)
                tx["phase"] = "LEDGER_COMMITTED"
                durable_replace(self.journal_path, tx)
                if crash_phase == "AFTER_LEDGER": os._exit(93)

                check = self._classify_locked()
                if check["status"] != "CONSISTENT" or check["commit_id"] != tx["commit_id"]:
                    raise RuntimeError("POST_COMMIT_CORRESPONDENCE_FAILED")
                self.journal_path.unlink()
                dfd = os.open(self.root, os.O_RDONLY)
                try: os.fsync(dfd)
                finally: os.close(dfd)
                return {"status": "COMMITTED", "commit_id": tx["commit_id"], "state_hash": tx["next_state_hash"]}
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _classify_locked(self) -> dict[str, Any]:
        state = read_json(self.state_path)
        ledger = read_json(self.ledger_path, [])
        if state is None:
            return {"status": "STATE_MISSING"}
        if not self.verify_ledger(ledger):
            return {"status": "LEDGER_CORRUPTED"}
        if not ledger:
            return {"status": "LEDGER_MISSING"}
        state_commit = state.get("commit_id")
        head = ledger[-1]
        state_hash = sha(state)
        if head.get("commit_id") == state_commit and head.get("state_hash") == state_hash:
            return {"status": "CONSISTENT", "commit_id": state_commit, "state_hash": state_hash, "ledger_events": len(ledger)}
        commits = {e.get("commit_id"): e for e in ledger}
        if state_commit not in commits:
            return {"status": "STATE_AHEAD_OF_LEDGER", "commit_id": state_commit, "ledger_head_commit": head.get("commit_id")}
        if head.get("commit_id") != state_commit:
            return {"status": "LEDGER_AHEAD_OF_STATE", "commit_id": state_commit, "ledger_head_commit": head.get("commit_id")}
        return {"status": "STATE_LEDGER_HASH_MISMATCH", "commit_id": state_commit}

    def classify(self) -> dict[str, Any]:
        with self._lock() as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_SH)
            try: return self._classify_locked()
            finally: fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _recover_locked(self) -> dict[str, Any]:
        tx = read_json(self.journal_path)
        if not tx:
            return self._classify_locked()
        state = read_json(self.state_path)
        ledger = read_json(self.ledger_path, [])
        if not self.verify_ledger(ledger):
            return {"status": "BLOCKED_LEDGER_CORRUPTED", "commit_id": tx.get("commit_id")}

        state_is_next = state == tx["next_state"]
        state_is_prev = state == tx["previous_state"]
        ledger_is_prev = ledger == tx["previous_ledger"]
        ledger_is_next = ledger == tx["previous_ledger"] + [tx["next_event"]]

        if state_is_prev and ledger_is_prev:
            self.journal_path.unlink()
            return {"status": "RECOVERED_ROLLBACK", "commit_id": tx["commit_id"], "from_phase": tx.get("phase")}

        if state_is_next and ledger_is_prev:
            durable_replace(self.ledger_path, tx["previous_ledger"] + [tx["next_event"]])
            self.journal_path.unlink()
            check = self._classify_locked()
            if check["status"] != "CONSISTENT": raise RuntimeError("RECOVERY_FORWARD_FAILED")
            return {"status": "RECOVERED_COMMIT", "commit_id": tx["commit_id"], "repair": "APPEND_PREPARED_LEDGER_EVENT"}

        if state_is_prev and ledger_is_next:
            durable_replace(self.state_path, tx["next_state"])
            self.journal_path.unlink()
            check = self._classify_locked()
            if check["status"] != "CONSISTENT": raise RuntimeError("RECOVERY_STATE_REPLAY_FAILED")
            return {"status": "RECOVERED_COMMIT", "commit_id": tx["commit_id"], "repair": "REPLAY_PREPARED_STATE"}

        if state_is_next and ledger_is_next:
            self.journal_path.unlink()
            check = self._classify_locked()
            if check["status"] != "CONSISTENT": raise RuntimeError("RECOVERY_FINALIZE_FAILED")
            return {"status": "RECOVERED_COMMIT", "commit_id": tx["commit_id"], "repair": "FINALIZE_COMMITTED_TRANSACTION"}

        return {
            "status": "BLOCKED_UNRESOLVED_DIVERGENCE",
            "commit_id": tx["commit_id"],
            "state_hash": sha(state) if state is not None else None,
            "ledger_hash": sha(ledger),
        }

    def recover(self) -> dict[str, Any]:
        with self._lock() as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try: return self._recover_locked()
            finally: fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def inspect(self) -> dict[str, Any]:
        c = self.classify()
        return {
            **c,
            "state": read_json(self.state_path),
            "ledger": read_json(self.ledger_path, []),
            "journal": read_json(self.journal_path),
        }
