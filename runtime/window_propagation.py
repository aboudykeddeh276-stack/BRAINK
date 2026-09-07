from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable
import hashlib
import json
import sqlite3
import time
import uuid


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def digest(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canonical(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class WindowSignal:
    source: str
    sector: str
    kind: str
    payload: dict[str, Any]
    sequence: int


@dataclass(frozen=True)
class PropagationFrame:
    frame_id: str
    work_id: str
    sequence: int
    canonical_root: str
    signals: tuple[WindowSignal, ...]
    created_ns: int


class WindowPropagationLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS frames(
                frame_id TEXT PRIMARY KEY,
                work_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                canonical_root TEXT NOT NULL,
                frame_json TEXT NOT NULL,
                created_ns INTEGER NOT NULL,
                UNIQUE(work_id, sequence)
            )""")
            db.commit()

    def append(self, frame: PropagationFrame) -> None:
        encoded = canonical(asdict(frame))
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT INTO frames(frame_id,work_id,sequence,canonical_root,frame_json,created_ns) VALUES(?,?,?,?,?,?)",
                (frame.frame_id, frame.work_id, frame.sequence, frame.canonical_root, encoded, frame.created_ns),
            )
            db.commit()

    def latest(self, work_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT frame_json FROM frames WHERE work_id=? ORDER BY sequence DESC LIMIT 1",
                (work_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None


class WindowPropagationRuntime:
    """Compile many local signals into one deterministic frame before leaving a wrapper.

    The runtime does not steal semantic ownership from the originating sector. It only
    canonicalises transport, ordering, proof and replay boundaries.
    """

    def __init__(self, ledger: WindowPropagationLedger):
        self.ledger = ledger

    @staticmethod
    def _normalise(signals: Iterable[WindowSignal]) -> tuple[WindowSignal, ...]:
        ordered = tuple(sorted(signals, key=lambda s: (s.sequence, s.sector, s.source, s.kind)))
        if not ordered:
            raise ValueError("at least one signal is required")
        sequences = [s.sequence for s in ordered]
        if len(sequences) != len(set(sequences)):
            raise ValueError("signal sequence values must be unique within a frame")
        return ordered

    def compile(self, work_id: str, sequence: int, signals: Iterable[WindowSignal]) -> PropagationFrame:
        ordered = self._normalise(signals)
        body = {
            "work_id": work_id,
            "sequence": sequence,
            "signals": [asdict(s) for s in ordered],
        }
        root = digest(body)
        frame = PropagationFrame(
            frame_id=str(uuid.uuid4()),
            work_id=work_id,
            sequence=sequence,
            canonical_root=root,
            signals=ordered,
            created_ns=time.time_ns(),
        )
        self.ledger.append(frame)
        return frame

    def replay(self, work_id: str) -> dict[str, Any] | None:
        return self.ledger.latest(work_id)

    @staticmethod
    def verify(frame: dict[str, Any]) -> bool:
        expected = frame.get("canonical_root")
        body = {
            "work_id": frame.get("work_id"),
            "sequence": frame.get("sequence"),
            "signals": frame.get("signals", []),
        }
        return isinstance(expected, str) and digest(body) == expected
