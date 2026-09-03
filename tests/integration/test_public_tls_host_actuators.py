from __future__ import annotations

from pathlib import Path
import json
import os
import sqlite3

import pytest

from assets.public_tls_host_actuators.dns01_resident_actuator import auth, cleanup
from assets.public_tls_host_actuators.install_launchers import install


def _registrar_fixture(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE zones (
          zone TEXT PRIMARY KEY,
          primary_ns TEXT NOT NULL,
          admin_rname TEXT NOT NULL,
          serial INTEGER NOT NULL,
          refresh INTEGER NOT NULL DEFAULT 3600,
          retry INTEGER NOT NULL DEFAULT 600,
          expire INTEGER NOT NULL DEFAULT 1209600,
          minimum INTEGER NOT NULL DEFAULT 300,
          owner_hash TEXT,
          status TEXT DEFAULT 'ACTIVE'
        );
        CREATE TABLE zone_records (
          zone TEXT NOT NULL,
          name TEXT NOT NULL,
          rrtype TEXT NOT NULL,
          value TEXT NOT NULL,
          ttl INTEGER NOT NULL DEFAULT 300,
          priority INTEGER,
          status TEXT DEFAULT 'ACTIVE',
          PRIMARY KEY(zone,name,rrtype,value)
        );
        """
    )
    conn.execute(
        "INSERT INTO zones(zone,primary_ns,admin_rname,serial,owner_hash,status) VALUES(?,?,?,?,?,'ACTIVE')",
        ("braink.example", "ns1.braink.example", "hostmaster.braink.example", 1, "owner"),
    )
    conn.commit()
    conn.close()


def test_dns01_auth_and_cleanup_mutate_exact_resident_schema(tmp_path: Path) -> None:
    db = tmp_path / "keddeh_registrar.sqlite"
    _registrar_fixture(db)

    result = auth("www.braink.example", "challenge-token", db)
    assert result["zone"] == "braink.example"
    assert result["name"] == "_acme-challenge.www.braink.example"
    assert result["readback"] == "MATCH"

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT value,status FROM zone_records WHERE zone=? AND name=? AND rrtype='TXT'",
        ("braink.example", "_acme-challenge.www.braink.example"),
    ).fetchone()
    serial_after_auth = conn.execute("SELECT serial FROM zones WHERE zone='braink.example'").fetchone()[0]
    conn.close()
    assert row == ("challenge-token", "ACTIVE")
    assert serial_after_auth > 1

    cleaned = cleanup("www.braink.example", "challenge-token", db)
    assert cleaned["remaining_txt_records"] == 0


def test_dns01_rejects_unowned_zone(tmp_path: Path) -> None:
    db = tmp_path / "keddeh_registrar.sqlite"
    _registrar_fixture(db)
    with pytest.raises(RuntimeError, match="DNS01_NO_RESIDENT_AUTHORITATIVE_ZONE"):
        auth("not-owned.invalid", "challenge", db)


def test_launcher_installer_creates_executable_contracts(tmp_path: Path) -> None:
    result = install(tmp_path / "bin")
    expected = {"dns01-auth", "dns01-cleanup", "server-tls-install", "server-tls-rollback"}
    assert set(result["launchers"]) == expected
    for path in result["launchers"].values():
        p = Path(path)
        assert p.is_file()
        assert os.access(p, os.X_OK)
        text = p.read_text("utf-8")
        assert "exec" in text and "assets.public_tls_host_actuators" in text
