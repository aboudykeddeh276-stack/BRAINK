"""Append-only, hash-chained ledger backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .canonical import canonical_hash

__all__ = ["LedgerEntry", "Ledger", "GENESIS_HASH"]

GENESIS_HASH = "GENESIS"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger (
    entry_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    payload    TEXT NOT NULL,
    prev_hash  TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    timestamp  TEXT NOT NULL
);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LedgerEntry:
    entry_id: int
    event_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    prev_hash: str = GENESIS_HASH
    entry_hash: str = ""
    timestamp: str = ""

    def hash_input(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "timestamp": self.timestamp,
        }

    def compute_hash(self) -> str:
        return canonical_hash(self.hash_input())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
            "timestamp": self.timestamp,
        }


class Ledger:
    """Durable append-only event log with a verifiable hash chain."""

    def __init__(self, db_path: str) -> None:
        if not db_path:
            raise ValueError("db_path must be provided")
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- internals ------------------------------------------------------
    def _last_row(self) -> Optional[sqlite3.Row]:
        cur = self._conn.execute(
            "SELECT * FROM ledger ORDER BY entry_id DESC LIMIT 1"
        )
        return cur.fetchone()

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> LedgerEntry:
        return LedgerEntry(
            entry_id=int(row["entry_id"]),
            event_type=row["event_type"],
            payload=json.loads(row["payload"]),
            prev_hash=row["prev_hash"],
            entry_hash=row["entry_hash"],
            timestamp=row["timestamp"],
        )

    # -- public API -----------------------------------------------------
    def head_hash(self) -> str:
        row = self._last_row()
        return row["entry_hash"] if row is not None else GENESIS_HASH

    def head_id(self) -> int:
        row = self._last_row()
        return int(row["entry_id"]) if row is not None else 0

    def append(self, event_type: str, payload: Dict[str, Any]) -> LedgerEntry:
        if not event_type or not isinstance(event_type, str):
            raise ValueError("event_type must be a non-empty string")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        prev_hash = self.head_hash()
        entry_id = self.head_id() + 1
        entry = LedgerEntry(
            entry_id=entry_id,
            event_type=event_type,
            payload=payload,
            prev_hash=prev_hash,
            timestamp=_utc_now(),
        )
        entry.entry_hash = entry.compute_hash()
        self._conn.execute(
            "INSERT INTO ledger (entry_id, event_type, payload, prev_hash, entry_hash,"
            " timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (
                entry.entry_id,
                entry.event_type,
                json.dumps(entry.payload, sort_keys=True, separators=(",", ":")),
                entry.prev_hash,
                entry.entry_hash,
                entry.timestamp,
            ),
        )
        self._conn.commit()
        return entry

    def get_all(self) -> List[LedgerEntry]:
        cur = self._conn.execute("SELECT * FROM ledger ORDER BY entry_id ASC")
        return [self._row_to_entry(row) for row in cur.fetchall()]

    def get(self, entry_id: int) -> Optional[LedgerEntry]:
        cur = self._conn.execute(
            "SELECT * FROM ledger WHERE entry_id = ?", (entry_id,)
        )
        row = cur.fetchone()
        return self._row_to_entry(row) if row is not None else None

    def count(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) AS n FROM ledger")
        return int(cur.fetchone()["n"])

    def verify_chain(self) -> bool:
        """True when every stored hash recomputes and every link matches."""
        expected_prev = GENESIS_HASH
        expected_id = 1
        for entry in self.get_all():
            if entry.entry_id != expected_id:
                return False
            if entry.prev_hash != expected_prev:
                return False
            if entry.compute_hash() != entry.entry_hash:
                return False
            expected_prev = entry.entry_hash
            expected_id += 1
        return True

    def detect_tamper(self) -> List[int]:
        """Return entry_ids whose stored hash or link no longer holds."""
        bad: List[int] = []
        expected_prev = GENESIS_HASH
        for entry in self.get_all():
            if entry.compute_hash() != entry.entry_hash:
                bad.append(entry.entry_id)
            elif entry.prev_hash != expected_prev:
                bad.append(entry.entry_id)
            expected_prev = entry.entry_hash
        return bad

    def export_receipt(self) -> Dict[str, Any]:
        entries = self.get_all()
        return {
            "receipt_type": "LEDGER_INTEGRITY",
            "ledger_path": self.db_path,
            "entry_count": len(entries),
            "genesis_hash": GENESIS_HASH,
            "root_hash": entries[-1].entry_hash if entries else GENESIS_HASH,
            "hashes": [e.entry_hash for e in entries],
            "event_types": [e.event_type for e in entries],
            "chain_valid": self.verify_chain(),
            "tampered_entries": self.detect_tamper(),
            "generated_at": _utc_now(),
            "status": "LOCALLY_PROVEN",
        }

    def close(self) -> None:
        try:
            self._conn.commit()
        finally:
            self._conn.close()

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
