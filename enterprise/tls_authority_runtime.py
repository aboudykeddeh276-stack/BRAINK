from __future__ import annotations

"""Resident TLS authority/controller for BRAINK/KEX.

This module closes the resident TLS_ROOT without pretending to be a public CA.
It owns a local persisted certificate authority and exposes concrete TLS semantics:

    resident TLS authority state
      -> CA identity
      -> server certificate issuance / renewal
      -> certificate + chain readback
      -> Python SSLContext
      -> TLS transport consumer

Public ACME/edge/CA issuance is deliberately outside this authority boundary.  A
future public-CA adapter may consume the same typed TLS object without changing
its semantic identity.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import shutil
import sqlite3
import ssl
import subprocess
import tempfile
import time

SCHEMA = "braink.kex.tls-authority.v1"
AUTHORITY = "BRAINK_LOCAL_TLS_AUTHORITY"


def _canon(v: Any) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _run(argv: list[str], *, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(argv, input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def _openssl() -> str:
    exe = shutil.which("openssl")
    if not exe:
        raise RuntimeError("OPENSSL_NOT_AVAILABLE")
    return exe


def _parse_openssl_time(value: str) -> int:
    # OpenSSL emits e.g. "Sep  3 05:00:00 2026 GMT".
    dt = datetime.strptime(" ".join(value.split()), "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


@dataclass(frozen=True)
class TLSMaterial:
    certificate_id: str
    common_name: str
    cert_path: str
    key_path: str
    ca_cert_path: str
    cert_sha256: str
    public_key_sha256: str
    serial_hex: str
    not_before_epoch: int
    not_after_epoch: int
    authority: str = AUTHORITY

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            **self.__dict__,
        }


class ResidentTLSAuthority:
    """Persisted local CA and server-certificate controller.

    Private keys remain runtime files and are never intended for source control.
    SQLite records provide readback/lineage; OpenSSL provides the cryptographic
    implementation; Python's ssl module consumes the resulting material.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.ca_dir = self.root / "ca"
        self.cert_dir = self.root / "certificates"
        self.ca_dir.mkdir(exist_ok=True)
        self.cert_dir.mkdir(exist_ok=True)
        self.db_path = self.root / "tls-authority.sqlite3"
        self.ca_key = self.ca_dir / "ca-key.pem"
        self.ca_cert = self.ca_dir / "ca-cert.pem"
        self.openssl = _openssl()
        self._init_db()

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _init_db(self) -> None:
        db = self._db()
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS authority(
              authority_id TEXT PRIMARY KEY,
              ca_cert_sha256 TEXT NOT NULL,
              ca_public_key_sha256 TEXT NOT NULL,
              created_ns INTEGER NOT NULL,
              updated_ns INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS certificates(
              certificate_id TEXT PRIMARY KEY,
              common_name TEXT NOT NULL,
              cert_path TEXT NOT NULL,
              key_path TEXT NOT NULL,
              cert_sha256 TEXT NOT NULL,
              public_key_sha256 TEXT NOT NULL,
              serial_hex TEXT NOT NULL,
              not_before_epoch INTEGER NOT NULL,
              not_after_epoch INTEGER NOT NULL,
              issued_ns INTEGER NOT NULL,
              renewed_from TEXT
            );
            CREATE TABLE IF NOT EXISTS receipts(
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              event TEXT NOT NULL,
              object_id TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              payload_sha256 TEXT NOT NULL,
              created_ns INTEGER NOT NULL
            );
            """
        )
        db.commit()
        db.close()

    def _receipt(self, event: str, object_id: str, payload: dict[str, Any]) -> None:
        raw = _canon(payload)
        db = self._db()
        db.execute(
            "INSERT INTO receipts(event,object_id,payload_json,payload_sha256,created_ns) VALUES(?,?,?,?,?)",
            (event, object_id, raw.decode("utf-8"), _sha256_bytes(raw), time.time_ns()),
        )
        db.commit()
        db.close()

    def ensure_ca(self, *, common_name: str = "BRAINK KEX Resident TLS Root", days: int = 3650) -> dict[str, Any]:
        if not self.ca_key.exists() or not self.ca_cert.exists():
            _run([self.openssl, "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:3072", "-out", str(self.ca_key)])
            os.chmod(self.ca_key, 0o600)
            _run([
                self.openssl, "req", "-x509", "-new", "-sha256",
                "-key", str(self.ca_key), "-out", str(self.ca_cert),
                "-days", str(days), "-subj", f"/CN={common_name}",
                "-addext", "basicConstraints=critical,CA:TRUE",
                "-addext", "keyUsage=critical,keyCertSign,cRLSign",
                "-addext", "subjectKeyIdentifier=hash",
            ])
        pub = _run([self.openssl, "x509", "-in", str(self.ca_cert), "-pubkey", "-noout"]).stdout
        state = {
            "schema": SCHEMA,
            "authority": AUTHORITY,
            "ca_cert_path": str(self.ca_cert),
            "ca_cert_sha256": _sha256_file(self.ca_cert),
            "ca_public_key_sha256": _sha256_bytes(pub),
        }
        now = time.time_ns()
        db = self._db()
        db.execute(
            """INSERT INTO authority(authority_id,ca_cert_sha256,ca_public_key_sha256,created_ns,updated_ns)
               VALUES(?,?,?,?,?)
               ON CONFLICT(authority_id) DO UPDATE SET
                 ca_cert_sha256=excluded.ca_cert_sha256,
                 ca_public_key_sha256=excluded.ca_public_key_sha256,
                 updated_ns=excluded.updated_ns""",
            (AUTHORITY, state["ca_cert_sha256"], state["ca_public_key_sha256"], now, now),
        )
        db.commit(); db.close()
        self._receipt("CA_READY", AUTHORITY, state)
        return state

    def _inspect_cert(self, cert: Path, key: Path, common_name: str, certificate_id: str) -> TLSMaterial:
        text = _run([
            self.openssl, "x509", "-in", str(cert), "-noout",
            "-serial", "-startdate", "-enddate",
        ]).stdout.decode("utf-8")
        fields: dict[str, str] = {}
        for line in text.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                fields[k.strip()] = v.strip()
        pub = _run([self.openssl, "x509", "-in", str(cert), "-pubkey", "-noout"]).stdout
        return TLSMaterial(
            certificate_id=certificate_id,
            common_name=common_name,
            cert_path=str(cert),
            key_path=str(key),
            ca_cert_path=str(self.ca_cert),
            cert_sha256=_sha256_file(cert),
            public_key_sha256=_sha256_bytes(pub),
            serial_hex=fields["serial"],
            not_before_epoch=_parse_openssl_time(fields["notBefore"]),
            not_after_epoch=_parse_openssl_time(fields["notAfter"]),
        )

    def issue_server_certificate(
        self,
        common_name: str,
        *,
        dns_names: list[str] | None = None,
        ip_addresses: list[str] | None = None,
        days: int = 90,
        renewed_from: str | None = None,
    ) -> TLSMaterial:
        self.ensure_ca()
        dns_names = list(dict.fromkeys(dns_names or [common_name]))
        ip_addresses = list(dict.fromkeys(ip_addresses or []))
        seed = _canon({"cn": common_name, "dns": dns_names, "ip": ip_addresses, "ns": time.time_ns()})
        certificate_id = "TLS-" + _sha256_bytes(seed)[:24]
        out = self.cert_dir / certificate_id
        out.mkdir(parents=True, exist_ok=False)
        key = out / "server-key.pem"
        csr = out / "server.csr.pem"
        cert = out / "server-cert.pem"
        ext = out / "extensions.cnf"
        _run([self.openssl, "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(key)])
        os.chmod(key, 0o600)
        _run([self.openssl, "req", "-new", "-key", str(key), "-out", str(csr), "-subj", f"/CN={common_name}"])
        san = [f"DNS:{name}" for name in dns_names] + [f"IP:{ip}" for ip in ip_addresses]
        ext.write_text(
            "\n".join([
                "basicConstraints=critical,CA:FALSE",
                "keyUsage=critical,digitalSignature,keyEncipherment",
                "extendedKeyUsage=serverAuth",
                "subjectKeyIdentifier=hash",
                "authorityKeyIdentifier=keyid,issuer",
                "subjectAltName=" + ",".join(san),
            ]) + "\n",
            "utf-8",
        )
        _run([
            self.openssl, "x509", "-req", "-sha256", "-in", str(csr),
            "-CA", str(self.ca_cert), "-CAkey", str(self.ca_key), "-CAcreateserial",
            "-out", str(cert), "-days", str(days), "-extfile", str(ext),
        ])
        material = self._inspect_cert(cert, key, common_name, certificate_id)
        if not self.verify_chain(material):
            raise RuntimeError("TLS_CHAIN_VERIFICATION_FAILED")
        db = self._db()
        db.execute(
            """INSERT INTO certificates VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                material.certificate_id, material.common_name, material.cert_path, material.key_path,
                material.cert_sha256, material.public_key_sha256, material.serial_hex,
                material.not_before_epoch, material.not_after_epoch, time.time_ns(), renewed_from,
            ),
        )
        db.commit(); db.close()
        self._receipt("CERT_ISSUED" if renewed_from is None else "CERT_RENEWED", material.certificate_id, material.as_dict())
        return material

    def verify_chain(self, material: TLSMaterial) -> bool:
        proc = subprocess.run(
            [self.openssl, "verify", "-CAfile", str(self.ca_cert), material.cert_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return proc.returncode == 0

    def readback(self, certificate_id: str) -> TLSMaterial:
        db = self._db()
        row = db.execute("SELECT * FROM certificates WHERE certificate_id=?", (certificate_id,)).fetchone()
        db.close()
        if not row:
            raise KeyError(certificate_id)
        cert = Path(row["cert_path"]); key = Path(row["key_path"])
        if not cert.exists() or not key.exists():
            raise RuntimeError("TLS_MATERIAL_MISSING")
        current = self._inspect_cert(cert, key, row["common_name"], certificate_id)
        if current.cert_sha256 != row["cert_sha256"] or current.public_key_sha256 != row["public_key_sha256"]:
            raise RuntimeError("TLS_READBACK_MISMATCH")
        if not self.verify_chain(current):
            raise RuntimeError("TLS_CHAIN_READBACK_FAILED")
        return current

    def renew_if_needed(self, certificate_id: str, *, renew_before_seconds: int = 30 * 24 * 3600, days: int = 90) -> TLSMaterial:
        current = self.readback(certificate_id)
        if current.not_after_epoch - int(time.time()) > renew_before_seconds:
            return current
        return self.issue_server_certificate(current.common_name, dns_names=[current.common_name], days=days, renewed_from=certificate_id)

    def server_context(self, certificate_id: str) -> ssl.SSLContext:
        material = self.readback(certificate_id)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(material.cert_path, material.key_path)
        return ctx

    def client_context(self) -> ssl.SSLContext:
        self.ensure_ca()
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(self.ca_cert))
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        return ctx

    def authority_state(self) -> dict[str, Any]:
        ca = self.ensure_ca()
        db = self._db()
        cert_count = db.execute("SELECT COUNT(*) FROM certificates").fetchone()[0]
        last = db.execute("SELECT seq,event,object_id,payload_sha256,created_ns FROM receipts ORDER BY seq DESC LIMIT 1").fetchone()
        db.close()
        return {
            "schema": SCHEMA,
            "authority": AUTHORITY,
            "state": "BOUND",
            "ca": ca,
            "certificate_count": cert_count,
            "last_receipt": dict(last) if last else None,
            "public_ca_authority": False,
            "public_ca_adapter": None,
        }
