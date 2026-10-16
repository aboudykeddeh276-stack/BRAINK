from __future__ import annotations

from hashlib import sha256
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
import time
from typing import Any, Mapping


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")


class AuthenticationError(RuntimeError):
    pass


class ReplayError(AuthenticationError):
    pass


class ExpiredRequest(AuthenticationError):
    pass


class UnknownKey(AuthenticationError):
    pass


class SignedRequestGate:
    """HMAC request gate with key IDs, expiry and durable nonce replay protection."""

    def __init__(
        self,
        db_path: str | Path,
        keys: Mapping[str, bytes],
        *,
        max_age_seconds: int = 300,
    ):
        if not keys:
            raise ValueError("at least one key is required")
        if any(len(key) < 32 for key in keys.values()):
            raise ValueError("all keys must be at least 32 bytes")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.keys = dict(keys)
        self.max_age_seconds = max_age_seconds
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS consumed_nonces (
                    nonce TEXT PRIMARY KEY,
                    key_id TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    request_sha256 TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def sign(
        self,
        *,
        key_id: str,
        payload: Mapping[str, Any],
        timestamp: int | None = None,
        nonce: str | None = None,
    ) -> dict[str, Any]:
        if key_id not in self.keys:
            raise UnknownKey(key_id)
        envelope = {
            "key_id": key_id,
            "nonce": nonce or secrets.token_hex(16),
            "timestamp": int(time.time()) if timestamp is None else int(timestamp),
            "payload": dict(payload),
            "signature_alg": "HMAC-SHA256",
        }
        envelope["signature"] = hmac.new(
            self.keys[key_id], canonical(envelope), sha256
        ).hexdigest()
        return envelope

    def verify_and_consume(
        self,
        envelope: Mapping[str, Any],
        *,
        now: int | None = None,
    ) -> dict[str, Any]:
        key_id = str(envelope.get("key_id", ""))
        nonce = str(envelope.get("nonce", ""))
        timestamp = int(envelope.get("timestamp", 0))
        signature = str(envelope.get("signature", ""))
        if key_id not in self.keys:
            raise UnknownKey(key_id)
        if not nonce:
            raise AuthenticationError("NONCE_REQUIRED")
        if timestamp <= 0:
            raise AuthenticationError("TIMESTAMP_REQUIRED")

        current = int(time.time()) if now is None else int(now)
        if abs(current - timestamp) > self.max_age_seconds:
            raise ExpiredRequest("REQUEST_EXPIRED")

        unsigned = dict(envelope)
        unsigned.pop("signature", None)
        expected = hmac.new(self.keys[key_id], canonical(unsigned), sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise AuthenticationError("SIGNATURE_MISMATCH")

        request_sha256 = sha256(canonical(envelope)).hexdigest()
        with self._connect() as db:
            try:
                db.execute(
                    "INSERT INTO consumed_nonces(nonce,key_id,timestamp,request_sha256) VALUES (?,?,?,?)",
                    (nonce, key_id, timestamp, request_sha256),
                )
                db.commit()
            except sqlite3.IntegrityError as exc:
                raise ReplayError("NONCE_REPLAY") from exc

        return {
            "state": "ACCEPTED",
            "key_id": key_id,
            "nonce": nonce,
            "timestamp": timestamp,
            "request_sha256": request_sha256,
        }
