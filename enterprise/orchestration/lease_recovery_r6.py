from __future__ import annotations

from typing import Any
import time


class LeaseRecoveryError(RuntimeError):
    pass


class RecoverableLeaseAuthority:
    """Adds heartbeat, expiry, bounded retry and poison-failure recovery to an existing BRAINK lease authority."""

    DEFAULT_TTL_NS = 60_000_000_000
    DEFAULT_MAX_RETRIES = 3

    def __init__(self, authority):
        self.authority = authority
        self._ensure_schema()

    def _db(self):
        return self.authority._db()

    def _ensure_schema(self) -> None:
        with self._db() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS recoverable_leases(
                    work_id TEXT PRIMARY KEY,
                    epoch INTEGER NOT NULL,
                    holder TEXT NOT NULL,
                    lease_expires_ns INTEGER,
                    last_heartbeat_ns INTEGER,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    failure_status TEXT,
                    updated_ns INTEGER NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS lease_recovery_failures(
                    failure_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    work_id TEXT NOT NULL,
                    epoch INTEGER NOT NULL,
                    holder TEXT,
                    failure_type TEXT NOT NULL,
                    retry_count INTEGER NOT NULL,
                    disposition TEXT NOT NULL DEFAULT 'REMEDIATION_REQUIRED',
                    created_ns INTEGER NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_recoverable_lease_expiry
                ON recoverable_leases(lease_expires_ns,retry_count,max_retries)
                WHERE failure_status IS NULL
                """
            )
            db.commit()

    def acquire_lease(
        self,
        work_id: str,
        holder: str,
        requested_epoch: int | None = None,
        ttl_ns: int | None = None,
        max_retries: int | None = None,
        now_ns: int | None = None,
    ) -> dict[str, Any]:
        now = int(now_ns if now_ns is not None else time.time_ns())
        ttl = int(ttl_ns if ttl_ns is not None else self.DEFAULT_TTL_NS)
        if ttl <= 0:
            raise ValueError("ttl_ns must be positive")
        previous = self.current_lease(work_id)
        retry_count = int(previous.get("retry_count", 0))
        retry_budget = int(max_retries if max_retries is not None else previous.get("max_retries", self.DEFAULT_MAX_RETRIES))
        if retry_budget < 0:
            raise ValueError("max_retries must be non-negative")
        epoch = self.authority.acquire_lease(work_id, holder, requested_epoch=requested_epoch)
        with self._db() as db:
            db.execute(
                """
                INSERT INTO recoverable_leases(
                    work_id,epoch,holder,lease_expires_ns,last_heartbeat_ns,
                    retry_count,max_retries,failure_status,updated_ns
                ) VALUES(?,?,?,?,?,?,?,NULL,?)
                ON CONFLICT(work_id) DO UPDATE SET
                    epoch=excluded.epoch,
                    holder=excluded.holder,
                    lease_expires_ns=excluded.lease_expires_ns,
                    last_heartbeat_ns=excluded.last_heartbeat_ns,
                    retry_count=excluded.retry_count,
                    max_retries=excluded.max_retries,
                    failure_status=NULL,
                    updated_ns=excluded.updated_ns
                """,
                (work_id, epoch, holder, now + ttl, now, retry_count, retry_budget, now),
            )
            db.commit()
        return self.current_lease(work_id)

    def heartbeat(self, work_id: str, holder: str, epoch: int, ttl_ns: int | None = None, now_ns: int | None = None) -> dict[str, Any]:
        now = int(now_ns if now_ns is not None else time.time_ns())
        ttl = int(ttl_ns if ttl_ns is not None else self.DEFAULT_TTL_NS)
        if ttl <= 0:
            raise ValueError("ttl_ns must be positive")
        current = self.current_lease(work_id)
        if current.get("state") != "LEASED":
            raise LeaseRecoveryError(f"lease is not active: {work_id}")
        if current.get("holder") != holder or int(current.get("epoch", -1)) != int(epoch):
            raise LeaseRecoveryError(f"stale lease heartbeat: {work_id}")
        with self._db() as db:
            db.execute(
                "UPDATE recoverable_leases SET lease_expires_ns=?,last_heartbeat_ns=?,updated_ns=? WHERE work_id=?",
                (now + ttl, now, now, work_id),
            )
            db.commit()
        return self.current_lease(work_id)

    def reconcile_expired_leases(self, now_ns: int | None = None, grace_ns: int = 0) -> dict[str, Any]:
        now = int(now_ns if now_ns is not None else time.time_ns())
        cutoff = now - int(grace_ns)
        recovered: list[str] = []
        poisoned: list[str] = []
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                """
                SELECT work_id,epoch,holder,retry_count,max_retries
                FROM recoverable_leases
                WHERE failure_status IS NULL
                  AND lease_expires_ns IS NOT NULL
                  AND lease_expires_ns < ?
                ORDER BY work_id
                """,
                (cutoff,),
            ).fetchall()
            for work_id, epoch, holder, retry_count, max_retries in rows:
                if int(retry_count) >= int(max_retries):
                    db.execute(
                        """
                        UPDATE recoverable_leases
                        SET holder='',lease_expires_ns=NULL,last_heartbeat_ns=NULL,
                            failure_status='POISON_PILL_FAILED',updated_ns=?
                        WHERE work_id=?
                        """,
                        (now, work_id),
                    )
                    db.execute(
                        """
                        INSERT INTO lease_recovery_failures(
                            work_id,epoch,holder,failure_type,retry_count,disposition,created_ns
                        ) VALUES(?,?,?,?,?,'REMEDIATION_REQUIRED',?)
                        """,
                        (work_id, int(epoch), holder, "ZOMBIE_WORKER_TIMEOUT", int(retry_count), now),
                    )
                    poisoned.append(work_id)
                else:
                    db.execute(
                        """
                        UPDATE recoverable_leases
                        SET holder='',lease_expires_ns=NULL,last_heartbeat_ns=NULL,
                            retry_count=retry_count+1,updated_ns=?
                        WHERE work_id=?
                        """,
                        (now, work_id),
                    )
                    recovered.append(work_id)
            db.commit()
        return {
            "state": "RECONCILED",
            "recovered_count": len(recovered),
            "poisoned_count": len(poisoned),
            "recovered_work_ids": recovered,
            "poisoned_work_ids": poisoned,
        }

    def current_lease(self, work_id: str) -> dict[str, Any]:
        base = self.authority.current_lease(work_id)
        with self._db() as db:
            row = db.execute(
                """
                SELECT epoch,holder,lease_expires_ns,last_heartbeat_ns,
                       retry_count,max_retries,failure_status,updated_ns
                FROM recoverable_leases WHERE work_id=?
                """,
                (work_id,),
            ).fetchone()
        if not base and not row:
            return {"work_id": work_id, "state": "UNLEASED"}
        if row:
            epoch, holder, expires_ns, heartbeat_ns, retry_count, max_retries, failure_status, updated_ns = row
            state = failure_status or ("RECOVERABLE" if not holder else "LEASED")
            return {
                "work_id": work_id,
                "epoch": int(epoch),
                "holder": holder,
                "state": state,
                "lease_expires_ns": expires_ns,
                "last_heartbeat_ns": heartbeat_ns,
                "retry_count": int(retry_count),
                "max_retries": int(max_retries),
                "failure_status": failure_status,
                "updated_ns": updated_ns,
            }
        return {
            "work_id": work_id,
            "epoch": int(base[0]),
            "holder": base[1],
            "state": "LEASED",
            "lease_expires_ns": None,
            "last_heartbeat_ns": None,
            "retry_count": 0,
            "max_retries": self.DEFAULT_MAX_RETRIES,
            "failure_status": None,
        }

    def failure_records(self, work_id: str | None = None) -> list[dict[str, Any]]:
        with self._db() as db:
            if work_id is None:
                rows = db.execute(
                    "SELECT failure_id,work_id,epoch,holder,failure_type,retry_count,disposition,created_ns FROM lease_recovery_failures ORDER BY failure_id"
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT failure_id,work_id,epoch,holder,failure_type,retry_count,disposition,created_ns FROM lease_recovery_failures WHERE work_id=? ORDER BY failure_id",
                    (work_id,),
                ).fetchall()
        keys = ("failure_id","work_id","epoch","holder","failure_type","retry_count","disposition","created_ns")
        return [dict(zip(keys, row)) for row in rows]
