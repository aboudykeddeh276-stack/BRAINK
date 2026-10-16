from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.publish.src.braink_runtime.v101_auth import (
    AuthenticationError,
    ExpiredRequest,
    ReplayError,
    SignedRequestGate,
)
from runtime.publish.src.braink_runtime.v101_seed_registry import (
    SeedConflict,
    SourceMismatch,
    TruthBackedVFSSeedRegistry,
)


class V101PersistenceAuthTests(unittest.TestCase):
    def test_vfs_seed_round_trip_and_wal(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "state.sqlite3"
            registry = TruthBackedVFSSeedRegistry(db)
            source = b"authoritative source bytes"
            seed = {"kex": "KEX://X1", "vfs": "vfs://x1", "version": 1}

            first = registry.record(
                logical="vfs://x1",
                source_kind="source_file",
                source_uri="file:///authoritative/source",
                source=source,
                seed=seed,
                regeneration_contract="rehydrate(seed, exact_source_sha256)",
                dependencies=("KEX://X1", "IL-LLM://global-index"),
            )
            second = registry.record(
                logical="vfs://x1",
                source_kind="source_file",
                source_uri="file:///authoritative/source",
                source=source,
                seed=seed,
                regeneration_contract="rehydrate(seed, exact_source_sha256)",
                dependencies=("IL-LLM://global-index", "KEX://X1"),
            )

            self.assertEqual(first.seed_sha256, second.seed_sha256)
            self.assertEqual(registry.read("vfs://x1", current_source=source).seed, seed)
            self.assertEqual(registry.export_jsonl(Path(td) / "seeds.jsonl"), 1)

            with registry._connect() as conn:
                self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
                self.assertEqual(conn.execute("PRAGMA synchronous").fetchone()[0], 2)

    def test_source_tamper_and_seed_conflict_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            registry = TruthBackedVFSSeedRegistry(Path(td) / "state.sqlite3")
            registry.record(
                logical="vfs://x",
                source_kind="source",
                source_uri="file:///x",
                source=b"source-a",
                seed={"state": "A"},
                regeneration_contract="exact-source",
            )
            with self.assertRaises(SourceMismatch):
                registry.read("vfs://x", current_source=b"source-b")
            with self.assertRaises(SeedConflict):
                registry.record(
                    logical="vfs://x",
                    source_kind="source",
                    source_uri="file:///x",
                    source=b"source-a",
                    seed={"state": "B"},
                    regeneration_contract="exact-source",
                )

    def test_auth_requires_key_timestamp_signature_and_replay_fencing(self):
        with tempfile.TemporaryDirectory() as td:
            gate = SignedRequestGate(
                Path(td) / "auth.sqlite3",
                {"k1": b"x" * 32, "k2": b"y" * 32},
                max_age_seconds=60,
            )
            envelope = gate.sign(key_id="k1", payload={"operation": "seed.write"}, timestamp=100)
            accepted = gate.verify_and_consume(envelope, now=100)
            self.assertEqual(accepted["state"], "ACCEPTED")

            with self.assertRaises(ReplayError):
                gate.verify_and_consume(envelope, now=100)

            expired = gate.sign(key_id="k1", payload={"operation": "seed.write"}, timestamp=1)
            with self.assertRaises(ExpiredRequest):
                gate.verify_and_consume(expired, now=100)

            tampered = gate.sign(key_id="k1", payload={"operation": "seed.write"}, timestamp=100)
            tampered["payload"]["operation"] = "seed.read"
            with self.assertRaises(AuthenticationError):
                gate.verify_and_consume(tampered, now=100)


if __name__ == "__main__":
    unittest.main()
