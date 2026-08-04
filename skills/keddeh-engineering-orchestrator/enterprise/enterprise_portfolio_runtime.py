#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "runtime" / "enterprise-portfolio.sqlite3"
REGISTRY_FILES = (
    "portfolio-registry.json",
    "naming-lineage-registry.json",
    "bilateral-contracts.json",
    "enterprise-trajectory.json",
)


def load_json(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class PortfolioRuntime:
    def __init__(self, database: Path = DEFAULT_DB) -> None:
        self.database = database
        database.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS registry_snapshots (
                registry_name TEXT PRIMARY KEY,
                sha256 TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS identities (
                canonical_id TEXT PRIMARY KEY,
                identity_kind TEXT NOT NULL,
                display_name TEXT NOT NULL,
                owner_id TEXT,
                payload_json TEXT NOT NULL,
                source_registry TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS aliases (
                alias TEXT PRIMARY KEY,
                canonical_id TEXT NOT NULL REFERENCES identities(canonical_id)
            );
            CREATE TABLE IF NOT EXISTS bilateral_contracts (
                contract_id TEXT PRIMARY KEY,
                source_owner TEXT NOT NULL,
                target_owner TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS translation_receipts (
                receipt_id TEXT PRIMARY KEY,
                contract_id TEXT NOT NULL,
                source_identity TEXT NOT NULL,
                target_identity TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                target_sha256 TEXT NOT NULL,
                equivalence_state TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.connection.commit()

    def synchronise(self) -> dict[str, Any]:
        portfolio = load_json("portfolio-registry.json")
        naming = load_json("naming-lineage-registry.json")
        bilateral = load_json("bilateral-contracts.json")
        trajectory = load_json("enterprise-trajectory.json")

        for name, payload in (
            ("portfolio-registry.json", portfolio),
            ("naming-lineage-registry.json", naming),
            ("bilateral-contracts.json", bilateral),
            ("enterprise-trajectory.json", trajectory),
        ):
            self.connection.execute(
                "INSERT OR REPLACE INTO registry_snapshots(registry_name, sha256, payload_json) VALUES (?, ?, ?)",
                (name, digest(payload), canonical_json(payload)),
            )

        self.connection.execute("DELETE FROM aliases")
        self.connection.execute("DELETE FROM identities")
        self.connection.execute("DELETE FROM bilateral_contracts")

        umbrellas = portfolio.get("umbrellas", portfolio.get("portfolio", []))
        if isinstance(umbrellas, dict):
            umbrellas = umbrellas.values()
        for umbrella in umbrellas:
            canonical_id = umbrella.get("canonical_id") or umbrella.get("id")
            if not canonical_id:
                continue
            display_name = umbrella.get("display_name") or umbrella.get("name") or canonical_id
            owner = umbrella.get("canonical_owner") or umbrella.get("owner")
            self._insert_identity(canonical_id, "umbrella", display_name, owner, umbrella, "portfolio-registry.json")

        entries = naming.get("names", naming.get("entries", []))
        if isinstance(entries, dict):
            entries = entries.values()
        for entry in entries:
            canonical_id = entry.get("canonical_id") or entry.get("identity") or entry.get("name_id")
            if not canonical_id:
                continue
            display_name = entry.get("display_name") or entry.get("name") or canonical_id
            owner = entry.get("owner") or entry.get("origin_authority")
            self._insert_identity(canonical_id, "governed-name", display_name, owner, entry, "naming-lineage-registry.json")
            aliases = entry.get("aliases", [])
            for alias in aliases:
                self.connection.execute("INSERT OR REPLACE INTO aliases(alias, canonical_id) VALUES (?, ?)", (alias, canonical_id))
            self.connection.execute("INSERT OR REPLACE INTO aliases(alias, canonical_id) VALUES (?, ?)", (display_name, canonical_id))

        contracts = bilateral.get("contracts", [])
        for contract in contracts:
            contract_id = contract.get("contract_id") or contract.get("id")
            if not contract_id:
                continue
            source = contract.get("source_owner") or contract.get("source")
            target = contract.get("target_owner") or contract.get("target")
            self.connection.execute(
                "INSERT OR REPLACE INTO bilateral_contracts(contract_id, source_owner, target_owner, payload_json) VALUES (?, ?, ?, ?)",
                (contract_id, source, target, canonical_json(contract)),
            )

        self.connection.commit()
        return {
            "database": str(self.database),
            "registry_count": self.connection.execute("SELECT COUNT(*) FROM registry_snapshots").fetchone()[0],
            "identity_count": self.connection.execute("SELECT COUNT(*) FROM identities").fetchone()[0],
            "contract_count": self.connection.execute("SELECT COUNT(*) FROM bilateral_contracts").fetchone()[0],
            "global_stop": False,
        }

    def _insert_identity(self, canonical_id: str, kind: str, display_name: str, owner: str | None, payload: dict[str, Any], source: str) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO identities(canonical_id, identity_kind, display_name, owner_id, payload_json, source_registry) VALUES (?, ?, ?, ?, ?, ?)",
            (canonical_id, kind, display_name, owner, canonical_json(payload), source),
        )
        self.connection.execute("INSERT OR REPLACE INTO aliases(alias, canonical_id) VALUES (?, ?)", (canonical_id, canonical_id))

    def resolve(self, value: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT i.* FROM identities i LEFT JOIN aliases a ON a.canonical_id=i.canonical_id WHERE i.canonical_id=? OR a.alias=? LIMIT 1",
            (value, value),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    def list_identities(self, kind: str | None = None) -> list[dict[str, Any]]:
        if kind:
            rows = self.connection.execute("SELECT canonical_id, identity_kind, display_name, owner_id, source_registry FROM identities WHERE identity_kind=? ORDER BY canonical_id", (kind,))
        else:
            rows = self.connection.execute("SELECT canonical_id, identity_kind, display_name, owner_id, source_registry FROM identities ORDER BY canonical_id")
        return [dict(row) for row in rows]

    def translate(self, contract_id: str, source_identity: str, source_payload: dict[str, Any]) -> dict[str, Any]:
        row = self.connection.execute("SELECT payload_json FROM bilateral_contracts WHERE contract_id=?", (contract_id,)).fetchone()
        if row is None:
            raise ValueError(f"unknown_contract:{contract_id}")
        contract = json.loads(row["payload_json"])
        required = contract.get("preserved_invariants", [])
        missing = [field for field in required if field not in source_payload]
        if missing:
            raise ValueError("missing_preserved_invariants:" + ",".join(missing))
        projection = {
            "source_identity": source_identity,
            "source_owner": contract.get("source_owner") or contract.get("source"),
            "target_owner": contract.get("target_owner") or contract.get("target"),
            "target_projection": contract.get("target_projection"),
            "preserved": {field: source_payload[field] for field in required},
            "source_payload": source_payload,
            "contract_id": contract_id,
        }
        target_identity = f"projection://{contract_id.rsplit('/', 1)[-1]}/{digest(source_payload)[:16]}"
        receipt = {
            "receipt_id": f"receipt://bilateral/{digest(projection)[:24]}",
            "contract_id": contract_id,
            "source_identity": source_identity,
            "target_identity": target_identity,
            "source_sha256": digest(source_payload),
            "target_sha256": digest(projection),
            "equivalence_state": "SEMANTIC_EQUIVALENT_WITH_DECLARED_ADAPTERS",
            "global_stop": False,
        }
        self.connection.execute(
            "INSERT OR REPLACE INTO translation_receipts(receipt_id, contract_id, source_identity, target_identity, source_sha256, target_sha256, equivalence_state, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (receipt["receipt_id"], contract_id, source_identity, target_identity, receipt["source_sha256"], receipt["target_sha256"], receipt["equivalence_state"], canonical_json({"projection": projection, "receipt": receipt})),
        )
        self.connection.commit()
        return {"projection": projection, "receipt": receipt}

    def export_snapshot(self, destination: Path) -> dict[str, Any]:
        destination.mkdir(parents=True, exist_ok=True)
        payload = {
            "identities": self.list_identities(),
            "contracts": [json.loads(row[0]) for row in self.connection.execute("SELECT payload_json FROM bilateral_contracts ORDER BY contract_id")],
            "registry_hashes": {row[0]: row[1] for row in self.connection.execute("SELECT registry_name, sha256 FROM registry_snapshots ORDER BY registry_name")},
            "global_stop": False,
        }
        snapshot = destination / "enterprise-portfolio-snapshot.json"
        snapshot.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        sha = hashlib.sha256(snapshot.read_bytes()).hexdigest()
        manifest = destination / "SHA256-MANIFEST.json"
        manifest.write_text(json.dumps({"files": [{"name": snapshot.name, "sha256": sha, "size": snapshot.stat().st_size}]}, indent=2, sort_keys=True), encoding="utf-8")
        return {"snapshot": str(snapshot), "sha256": sha, "size": snapshot.stat().st_size, "manifest": str(manifest), "global_stop": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KEDDEH enterprise portfolio runtime")
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sync")
    listing = sub.add_parser("list")
    listing.add_argument("--kind")
    resolve = sub.add_parser("resolve")
    resolve.add_argument("identity")
    translate = sub.add_parser("translate")
    translate.add_argument("contract_id")
    translate.add_argument("source_identity")
    translate.add_argument("payload_json")
    export = sub.add_parser("export")
    export.add_argument("destination", type=Path)
    args = parser.parse_args(argv)

    runtime = PortfolioRuntime(args.database)
    try:
        if args.command == "sync":
            result = runtime.synchronise()
        elif args.command == "list":
            result = runtime.list_identities(args.kind)
        elif args.command == "resolve":
            result = runtime.resolve(args.identity)
            if result is None:
                print(json.dumps({"error": "identity_not_found", "identity": args.identity, "global_stop": False}, indent=2))
                return 2
        elif args.command == "translate":
            result = runtime.translate(args.contract_id, args.source_identity, json.loads(args.payload_json))
        else:
            result = runtime.export_snapshot(args.destination)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc), "global_stop": False}, indent=2), file=sys.stderr)
        return 2
    finally:
        runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())
