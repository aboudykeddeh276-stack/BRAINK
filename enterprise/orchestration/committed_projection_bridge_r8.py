from __future__ import annotations

"""Committed DomainState projection boundary for MCP, plugins, adapters and connectors.

These surfaces are execution/projection carriers. They may consume an already
committed DomainState event, but they cannot create a new producer truth,
silently change authority class, or roll authoritative history back when their
own projection fails.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
import copy
import hashlib
import hmac
import json
import sqlite3
import time


SCHEMA = "braink.committed-projection-envelope.v1"
COMMITTED_PHASE = "AUTHORITATIVELY_COMMITTED"


class ProjectionError(RuntimeError):
    pass


class EnvelopeRejected(ProjectionError):
    pass


class AuthorityRejected(ProjectionError):
    pass


class ProjectionExecutionFailed(ProjectionError):
    pass


class AuthorityClass(str, Enum):
    INTERNAL = "INTERNAL"
    HOST_CONTROLLED = "HOST_CONTROLLED"
    EXTERNALLY_DELEGATED = "EXTERNALLY_DELEGATED"
    UNPROVEN = "UNPROVEN"


class Surface(str, Enum):
    MCP = "MCP"
    PLUGIN = "PLUGIN"
    ADAPTER = "ADAPTER"
    CONNECTOR = "CONNECTOR"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canonical(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _valid_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


@dataclass(frozen=True)
class ProjectionEnvelope:
    schema_version: str
    event_hash: str
    domain_root: str
    sequence: int
    phase: str
    projection_id: str
    surface: str
    target: str
    authority_class: str
    operation: str
    producer_truth_hash: str
    payload: Mapping[str, Any]
    authority_evidence: Mapping[str, Any]
    source_receipt_hash: str
    signature: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ProjectionEnvelope":
        required = {
            "schema_version", "event_hash", "domain_root", "sequence", "phase",
            "projection_id", "surface", "target", "authority_class", "operation",
            "producer_truth_hash", "payload", "authority_evidence",
            "source_receipt_hash", "signature",
        }
        missing = sorted(required - set(value))
        if missing:
            raise EnvelopeRejected(f"ENVELOPE_FIELDS_MISSING:{','.join(missing)}")
        return cls(**{key: copy.deepcopy(value[key]) for key in required})

    def unsigned(self) -> dict[str, Any]:
        body = asdict(self)
        body.pop("signature", None)
        return body

    def canonical_bytes(self) -> bytes:
        return canonical(self.unsigned()).encode("utf-8")

    @property
    def envelope_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


class ProjectionSigner:
    def __init__(self, key: bytes):
        if not isinstance(key, (bytes, bytearray)) or len(key) < 32:
            raise ValueError("projection signing key must be at least 32 bytes")
        self.key = bytes(key)

    def sign(self, body: Mapping[str, Any]) -> str:
        return hmac.new(self.key, canonical(body).encode("utf-8"), hashlib.sha256).hexdigest()

    def verify(self, envelope: ProjectionEnvelope) -> None:
        if envelope.schema_version != SCHEMA:
            raise EnvelopeRejected("SCHEMA_VERSION_UNSUPPORTED")
        if envelope.phase != COMMITTED_PHASE:
            raise EnvelopeRejected("SOURCE_NOT_AUTHORITATIVELY_COMMITTED")
        if not _valid_hash(envelope.event_hash):
            raise EnvelopeRejected("EVENT_HASH_INVALID")
        if envelope.domain_root != "GENESIS" and not _valid_hash(envelope.domain_root):
            raise EnvelopeRejected("DOMAIN_ROOT_INVALID")
        if not isinstance(envelope.sequence, int) or isinstance(envelope.sequence, bool) or envelope.sequence < 1:
            raise EnvelopeRejected("SEQUENCE_INVALID")
        if not envelope.projection_id or not envelope.target or not envelope.operation:
            raise EnvelopeRejected("PROJECTION_IDENTITY_INCOMPLETE")
        if digest(dict(envelope.payload)) != envelope.producer_truth_hash:
            raise EnvelopeRejected("PRODUCER_TRUTH_HASH_MISMATCH")
        expected = self.sign(envelope.unsigned())
        if not hmac.compare_digest(expected, envelope.signature):
            raise EnvelopeRejected("ENVELOPE_SIGNATURE_INVALID")
        try:
            AuthorityClass(envelope.authority_class)
            Surface(envelope.surface)
        except ValueError as exc:
            raise EnvelopeRejected("ENUM_VALUE_INVALID") from exc


class ProjectionAdapter(Protocol):
    adapter_id: str
    surface: Surface
    mutating: bool
    readback_required: bool

    def apply(self, envelope: ProjectionEnvelope) -> Mapping[str, Any]: ...
    def readback(self, envelope: ProjectionEnvelope, result: Mapping[str, Any]) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class CallableProjectionAdapter:
    adapter_id: str
    surface: Surface
    apply_fn: Callable[[ProjectionEnvelope], Mapping[str, Any]]
    readback_fn: Callable[[ProjectionEnvelope, Mapping[str, Any]], Mapping[str, Any]] | None = None
    mutating: bool = True
    readback_required: bool = True

    def apply(self, envelope: ProjectionEnvelope) -> Mapping[str, Any]:
        return self.apply_fn(envelope)

    def readback(self, envelope: ProjectionEnvelope, result: Mapping[str, Any]) -> Mapping[str, Any]:
        if self.readback_fn is None:
            return dict(result)
        return self.readback_fn(envelope, result)


class ProjectionReceiptLedger:
    """Durable projection receipts plus post-commit reconciliation debt."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("""CREATE TABLE IF NOT EXISTS receipts(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                projection_id TEXT NOT NULL,
                event_hash TEXT NOT NULL,
                envelope_hash TEXT NOT NULL,
                adapter_id TEXT NOT NULL,
                surface TEXT NOT NULL,
                authority_class TEXT NOT NULL,
                state TEXT NOT NULL,
                result_json TEXT,
                readback_json TEXT,
                prev_hash TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                created_ns INTEGER NOT NULL,
                UNIQUE(projection_id,event_hash)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS reconciliation(
                projection_id TEXT NOT NULL,
                event_hash TEXT NOT NULL,
                envelope_json TEXT NOT NULL,
                adapter_id TEXT NOT NULL,
                error_text TEXT NOT NULL,
                attempts INTEGER NOT NULL,
                state TEXT NOT NULL,
                updated_ns INTEGER NOT NULL,
                PRIMARY KEY(projection_id,event_hash)
            )""")
            db.commit()

    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def prior(self, projection_id: str, event_hash: str) -> dict[str, Any] | None:
        with self._db() as db:
            row = db.execute(
                "SELECT state,result_json,readback_json,receipt_hash,envelope_hash FROM receipts WHERE projection_id=? AND event_hash=?",
                (projection_id, event_hash),
            ).fetchone()
        if not row:
            return None
        return {
            "state": row[0],
            "result": json.loads(row[1]) if row[1] else None,
            "readback": json.loads(row[2]) if row[2] else None,
            "receipt_hash": row[3],
            "envelope_hash": row[4],
        }

    def append_success(self, envelope: ProjectionEnvelope, adapter: ProjectionAdapter, result: Mapping[str, Any], readback: Mapping[str, Any]) -> dict[str, Any]:
        with self._db() as db:
            prior = db.execute("SELECT receipt_hash FROM receipts ORDER BY seq DESC LIMIT 1").fetchone()
            prev = prior[0] if prior else "GENESIS"
            body = {
                "projection_id": envelope.projection_id,
                "event_hash": envelope.event_hash,
                "envelope_hash": envelope.envelope_hash,
                "adapter_id": adapter.adapter_id,
                "surface": adapter.surface.value,
                "authority_class": envelope.authority_class,
                "state": "RECONCILED",
                "result": dict(result),
                "readback": dict(readback),
                "prev_hash": prev,
            }
            receipt_hash = digest(body)
            db.execute(
                "INSERT INTO receipts(projection_id,event_hash,envelope_hash,adapter_id,surface,authority_class,state,result_json,readback_json,prev_hash,receipt_hash,created_ns) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    envelope.projection_id, envelope.event_hash, envelope.envelope_hash,
                    adapter.adapter_id, adapter.surface.value, envelope.authority_class,
                    "RECONCILED", canonical(dict(result)), canonical(dict(readback)),
                    prev, receipt_hash, time.time_ns(),
                ),
            )
            db.execute("DELETE FROM reconciliation WHERE projection_id=? AND event_hash=?", (envelope.projection_id, envelope.event_hash))
            db.commit()
        return {**body, "receipt_hash": receipt_hash}

    def queue_reconciliation(self, envelope: ProjectionEnvelope, adapter: ProjectionAdapter, error: Exception) -> None:
        with self._db() as db:
            row = db.execute(
                "SELECT attempts FROM reconciliation WHERE projection_id=? AND event_hash=?",
                (envelope.projection_id, envelope.event_hash),
            ).fetchone()
            attempts = (row[0] if row else 0) + 1
            db.execute(
                "INSERT INTO reconciliation VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(projection_id,event_hash) DO UPDATE SET error_text=excluded.error_text,attempts=excluded.attempts,state=excluded.state,updated_ns=excluded.updated_ns",
                (
                    envelope.projection_id, envelope.event_hash, canonical(asdict(envelope)),
                    adapter.adapter_id, f"{type(error).__name__}: {error}", attempts,
                    "PENDING", time.time_ns(),
                ),
            )
            db.commit()

    def debt(self) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute(
                "SELECT projection_id,event_hash,adapter_id,error_text,attempts,state FROM reconciliation ORDER BY projection_id,event_hash"
            ).fetchall()
        return [
            {"projection_id": r[0], "event_hash": r[1], "adapter_id": r[2], "error": r[3], "attempts": r[4], "state": r[5]}
            for r in rows
        ]

    def verify_chain(self) -> dict[str, Any]:
        prev = "GENESIS"
        count = 0
        with self._db() as db:
            rows = db.execute(
                "SELECT projection_id,event_hash,envelope_hash,adapter_id,surface,authority_class,state,result_json,readback_json,prev_hash,receipt_hash FROM receipts ORDER BY seq"
            ).fetchall()
        for row in rows:
            body = {
                "projection_id": row[0],
                "event_hash": row[1],
                "envelope_hash": row[2],
                "adapter_id": row[3],
                "surface": row[4],
                "authority_class": row[5],
                "state": row[6],
                "result": json.loads(row[7]) if row[7] else None,
                "readback": json.loads(row[8]) if row[8] else None,
                "prev_hash": row[9],
            }
            if row[9] != prev or digest(body) != row[10]:
                return {"ok": False, "count": count, "head": prev}
            prev = row[10]
            count += 1
        return {"ok": True, "count": count, "head": prev}


class CommittedProjectionBridge:
    def __init__(self, signer: ProjectionSigner, ledger: ProjectionReceiptLedger):
        self.signer = signer
        self.ledger = ledger

    @staticmethod
    def _authority_guard(envelope: ProjectionEnvelope, adapter: ProjectionAdapter) -> None:
        authority = AuthorityClass(envelope.authority_class)
        if envelope.surface != adapter.surface.value:
            raise AuthorityRejected("SURFACE_ADAPTER_MISMATCH")
        if authority is AuthorityClass.UNPROVEN and adapter.mutating:
            raise AuthorityRejected("UNPROVEN_AUTHORITY_CANNOT_MUTATE")
        if authority is AuthorityClass.EXTERNALLY_DELEGATED:
            evidence = dict(envelope.authority_evidence)
            if not evidence.get("delegation_id") or not evidence.get("observed"):
                raise AuthorityRejected("EXTERNAL_DELEGATION_EVIDENCE_REQUIRED")
            if not adapter.readback_required:
                raise AuthorityRejected("EXTERNAL_MUTATION_REQUIRES_READBACK")
        if authority is AuthorityClass.HOST_CONTROLLED and adapter.mutating and not adapter.readback_required:
            raise AuthorityRejected("HOST_MUTATION_REQUIRES_READBACK")

    @staticmethod
    def _assert_truth_preserved(envelope: ProjectionEnvelope, result: Mapping[str, Any], readback: Mapping[str, Any]) -> None:
        for value in (result, readback):
            claimed_truth = value.get("producer_truth_hash") if isinstance(value, Mapping) else None
            if claimed_truth is not None and claimed_truth != envelope.producer_truth_hash:
                raise ProjectionExecutionFailed("ADAPTER_REDEFINED_PRODUCER_TRUTH")
            claimed_event = value.get("source_event_hash") if isinstance(value, Mapping) else None
            if claimed_event is not None and claimed_event != envelope.event_hash:
                raise ProjectionExecutionFailed("ADAPTER_REDEFINED_EVENT_IDENTITY")

    def project(self, envelope: ProjectionEnvelope, adapter: ProjectionAdapter) -> dict[str, Any]:
        self.signer.verify(envelope)
        self._authority_guard(envelope, adapter)
        prior = self.ledger.prior(envelope.projection_id, envelope.event_hash)
        if prior:
            if prior["envelope_hash"] != envelope.envelope_hash:
                raise ProjectionError("IDEMPOTENCY_ENVELOPE_CONFLICT")
            return {"status": "REPLAYED_RECONCILED", **prior}

        before_truth = envelope.producer_truth_hash
        before_event = envelope.event_hash
        before_payload = canonical(dict(envelope.payload))
        try:
            result = dict(adapter.apply(envelope))
            readback = dict(adapter.readback(envelope, result)) if adapter.readback_required else dict(result)
            self._assert_truth_preserved(envelope, result, readback)
            if envelope.producer_truth_hash != before_truth or envelope.event_hash != before_event or canonical(dict(envelope.payload)) != before_payload:
                raise ProjectionExecutionFailed("ADAPTER_MUTATED_SOURCE_ENVELOPE")
            receipt = self.ledger.append_success(envelope, adapter, result, readback)
            return {"status": "RECONCILED", "receipt": receipt}
        except Exception as exc:
            self.ledger.queue_reconciliation(envelope, adapter, exc)
            return {
                "status": "RECONCILIATION_REQUIRED",
                "event_hash": envelope.event_hash,
                "domain_root": envelope.domain_root,
                "projection_id": envelope.projection_id,
                "error": f"{type(exc).__name__}: {exc}",
            }
