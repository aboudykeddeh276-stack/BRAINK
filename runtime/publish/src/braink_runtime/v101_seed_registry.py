from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping, Sequence


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")


def digest(value: Any) -> str:
    return sha256(canonical(value)).hexdigest()


class SeedRegistryError(RuntimeError):
    pass


class SourceMismatch(SeedRegistryError):
    pass


class SeedConflict(SeedRegistryError):
    pass


@dataclass(frozen=True)
class VFSSeed:
    logical: str
    source_kind: str
    source_uri: str
    source_sha256: str
    seed_sha256: str
    seed: Mapping[str, Any]
    regeneration_contract: str
    dependencies: tuple[str, ...]


class TruthBackedVFSSeedRegistry:
    """
    Durable registry for compact VFS seeds.

    The registry records provenance and regeneration rules. It does not declare
    arbitrary content to be globally true. A seed is admissible only against
    the exact source digest for which it was recorded.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS vfs_seeds (
                    logical TEXT PRIMARY KEY,
                    source_kind TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    seed_sha256 TEXT NOT NULL,
                    seed_json TEXT NOT NULL,
                    regeneration_contract TEXT NOT NULL,
                    created_ns INTEGER NOT NULL DEFAULT (unixepoch('subsec') * 1000000000)
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS vfs_seed_dependencies (
                    logical TEXT NOT NULL,
                    dependency TEXT NOT NULL,
                    PRIMARY KEY (logical, dependency),
                    FOREIGN KEY (logical) REFERENCES vfs_seeds(logical) ON DELETE CASCADE
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def source_digest(source: bytes) -> str:
        return sha256(source).hexdigest()

    def record(
        self,
        *,
        logical: str,
        source_kind: str,
        source_uri: str,
        source: bytes,
        seed: Mapping[str, Any],
        regeneration_contract: str,
        dependencies: Sequence[str] = (),
    ) -> VFSSeed:
        if not logical.strip():
            raise ValueError("logical is required")
        if not source_kind.strip():
            raise ValueError("source_kind is required")
        if not source_uri.strip():
            raise ValueError("source_uri is required")
        if not regeneration_contract.strip():
            raise ValueError("regeneration_contract is required")

        source_sha256 = self.source_digest(source)
        seed_sha256 = digest(seed)
        seed_json = canonical(seed).decode("utf-8")
        deps = tuple(sorted(set(str(x) for x in dependencies if str(x).strip())))

        result = VFSSeed(
            logical=logical,
            source_kind=source_kind,
            source_uri=source_uri,
            source_sha256=source_sha256,
            seed_sha256=seed_sha256,
            seed=dict(seed),
            regeneration_contract=regeneration_contract,
            dependencies=deps,
        )

        with self._connect() as db:
            existing = db.execute(
                "SELECT source_sha256, seed_sha256, seed_json FROM vfs_seeds WHERE logical=?",
                (logical,),
            ).fetchone()
            if existing:
                if existing[0] != source_sha256 or existing[1] != seed_sha256:
                    raise SeedConflict(logical)
                return result

            db.execute(
                """
                INSERT INTO vfs_seeds
                (logical, source_kind, source_uri, source_sha256, seed_sha256, seed_json,
                 regeneration_contract)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    logical,
                    source_kind,
                    source_uri,
                    source_sha256,
                    seed_sha256,
                    seed_json,
                    regeneration_contract,
                ),
            )
            db.executemany(
                "INSERT INTO vfs_seed_dependencies(logical, dependency) VALUES (?, ?)",
                [(logical, dep) for dep in deps],
            )
            db.commit()
        return result

    def read(
        self,
        logical: str,
        *,
        current_source: bytes | None = None,
    ) -> VFSSeed:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT logical, source_kind, source_uri, source_sha256, seed_sha256,
                       seed_json, regeneration_contract
                FROM vfs_seeds WHERE logical=?
                """,
                (logical,),
            ).fetchone()
            if row is None:
                raise SeedRegistryError(f"SEED_NOT_FOUND:{logical}")

            deps = tuple(
                r[0]
                for r in db.execute(
                    "SELECT dependency FROM vfs_seed_dependencies WHERE logical=? ORDER BY dependency",
                    (logical,),
                ).fetchall()
            )

        if current_source is not None:
            observed = self.source_digest(current_source)
            if observed != row[3]:
                raise SourceMismatch(
                    f"SOURCE_SHA256_MISMATCH:{logical}:{row[3]}:{observed}"
                )

        seed = json.loads(row[5])
        if digest(seed) != row[4]:
            raise SeedRegistryError(f"SEED_DIGEST_MISMATCH:{logical}")

        return VFSSeed(
            logical=row[0],
            source_kind=row[1],
            source_uri=row[2],
            source_sha256=row[3],
            seed_sha256=row[4],
            seed=seed,
            regeneration_contract=row[6],
            dependencies=deps,
        )

    def export_jsonl(self, output: str | Path) -> int:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with self._connect() as db, output.open("w", encoding="utf-8") as fh:
            rows = db.execute(
                """
                SELECT logical, source_kind, source_uri, source_sha256, seed_sha256,
                       seed_json, regeneration_contract
                FROM vfs_seeds ORDER BY logical
                """
            ).fetchall()
            for row in rows:
                deps = [
                    r[0]
                    for r in db.execute(
                        "SELECT dependency FROM vfs_seed_dependencies WHERE logical=? ORDER BY dependency",
                        (row[0],),
                    ).fetchall()
                ]
                fh.write(
                    json.dumps(
                        {
                            "logical": row[0],
                            "source_kind": row[1],
                            "source_uri": row[2],
                            "source_sha256": row[3],
                            "seed_sha256": row[4],
                            "seed": json.loads(row[5]),
                            "regeneration_contract": row[6],
                            "dependencies": deps,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                count += 1
        return count
