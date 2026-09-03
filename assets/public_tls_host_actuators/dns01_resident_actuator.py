from __future__ import annotations

"""Resident DNS-01 actuator for BRAINK/KEX public TLS.

This module mutates the same SQLite schema consumed by KEX authoritative DNS. It is
not a registrar replacement and does not infer public delegation. The public CA still
performs the authoritative challenge query; this actuator only owns the resident
zone mutation and readback boundary.
"""

from pathlib import Path
import argparse
import json
import os
import sqlite3
import time

DEFAULT_DB = Path(
    os.environ.get(
        "KEDDEH_REGISTRAR_DB",
        "/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5/substrate_ledger/keddeh_registrar.sqlite",
    )
)
DEFAULT_TTL = int(os.environ.get("KEDDEH_ACME_TXT_TTL", "60"))


def _connect(db: Path) -> sqlite3.Connection:
    if not db.is_file():
        raise RuntimeError(f"KEDDEH_REGISTRAR_DB_NOT_FOUND:{db}")
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _find_zone(conn: sqlite3.Connection, fqdn: str) -> str:
    name = fqdn.rstrip(".")
    labels = name.split(".")
    candidates = [".".join(labels[i:]) for i in range(len(labels))]
    placeholders = ",".join("?" for _ in candidates)
    row = conn.execute(
        f"SELECT zone FROM zones WHERE status='ACTIVE' AND zone IN ({placeholders}) ORDER BY length(zone) DESC LIMIT 1",
        candidates,
    ).fetchone()
    if not row:
        raise RuntimeError(f"DNS01_NO_RESIDENT_AUTHORITATIVE_ZONE:{fqdn}")
    return str(row[0])


def _challenge_name(domain: str) -> str:
    return "_acme-challenge." + domain.rstrip(".")


def _bump_serial(conn: sqlite3.Connection, zone: str) -> int:
    row = conn.execute("SELECT serial FROM zones WHERE zone=?", (zone,)).fetchone()
    if not row:
        raise RuntimeError(f"DNS01_ZONE_MISSING:{zone}")
    current = int(row[0])
    candidate = max(current + 1, int(time.strftime("%Y%m%d00")))
    conn.execute("UPDATE zones SET serial=? WHERE zone=?", (candidate, zone))
    return candidate


def auth(domain: str, validation: str, db: Path = DEFAULT_DB) -> dict:
    if not domain or not validation:
        raise RuntimeError("DNS01_INPUT_MISSING")
    name = _challenge_name(domain)
    with _connect(db) as conn:
        conn.execute("BEGIN IMMEDIATE")
        zone = _find_zone(conn, domain)
        conn.execute(
            "DELETE FROM zone_records WHERE zone=? AND name=? AND rrtype='TXT'",
            (zone, name),
        )
        conn.execute(
            "INSERT INTO zone_records(zone,name,rrtype,value,ttl,priority,status) VALUES(?,?,?,?,?,NULL,'ACTIVE')",
            (zone, name, "TXT", validation, DEFAULT_TTL),
        )
        serial = _bump_serial(conn, zone)
        row = conn.execute(
            "SELECT value,ttl,status FROM zone_records WHERE zone=? AND name=? AND rrtype='TXT'",
            (zone, name),
        ).fetchone()
        if not row or row[0] != validation or row[2] != "ACTIVE":
            raise RuntimeError("DNS01_READBACK_MISMATCH")
        conn.commit()
    return {
        "schema": "kex.braink.dns01-host-actuator.v1",
        "operation": "AUTH",
        "domain": domain,
        "zone": zone,
        "name": name,
        "ttl": int(row[1]),
        "serial": serial,
        "readback": "MATCH",
    }


def cleanup(domain: str, validation: str | None = None, db: Path = DEFAULT_DB) -> dict:
    if not domain:
        raise RuntimeError("DNS01_INPUT_MISSING")
    name = _challenge_name(domain)
    with _connect(db) as conn:
        conn.execute("BEGIN IMMEDIATE")
        zone = _find_zone(conn, domain)
        if validation:
            conn.execute(
                "DELETE FROM zone_records WHERE zone=? AND name=? AND rrtype='TXT' AND value=?",
                (zone, name, validation),
            )
        else:
            conn.execute(
                "DELETE FROM zone_records WHERE zone=? AND name=? AND rrtype='TXT'",
                (zone, name),
            )
        serial = _bump_serial(conn, zone)
        remaining = conn.execute(
            "SELECT COUNT(*) FROM zone_records WHERE zone=? AND name=? AND rrtype='TXT' AND status='ACTIVE'",
            (zone, name),
        ).fetchone()[0]
        conn.commit()
    return {
        "schema": "kex.braink.dns01-host-actuator.v1",
        "operation": "CLEANUP",
        "domain": domain,
        "zone": zone,
        "name": name,
        "serial": serial,
        "remaining_txt_records": int(remaining),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("auth", "cleanup"))
    parser.add_argument("--domain", default=os.environ.get("CERTBOT_DOMAIN", ""))
    parser.add_argument("--validation", default=os.environ.get("CERTBOT_VALIDATION", ""))
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    result = auth(args.domain, args.validation, args.db) if args.operation == "auth" else cleanup(args.domain, args.validation or None, args.db)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
