from __future__ import annotations

"""SERVER_ROOT TLS certificate actuator.

Installs already-verified public certificate material into the resident fabric only
when the live server can be restarted and its presented leaf certificate can be read
back and matched to the requested certificate.
"""

from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import socket
import ssl
import subprocess
import tempfile
import time

FABRIC_ROOT = Path(os.environ.get("KEDDEH_DOMAIN_FABRIC_ROOT", "/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5"))
BINDINGS = Path(os.environ.get("KEDDEH_HOST_ACTUATOR_BINDINGS", "deploy/braink-public/BRAINK_HOST_ACTUATOR_BINDINGS.json"))
BACKUP_ROOT = Path(os.environ.get("KEDDEH_TLS_BACKUP_ROOT", "/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5_EVIDENCE/TLS_BACKUPS"))
RECEIPT_ROOT = Path(os.environ.get("KEDDEH_TLS_ACTUATOR_RECEIPT_ROOT", "/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5_EVIDENCE/TLS_ACTUATORS"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_copy(source: Path, target: Path, mode: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(source.read_bytes())
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, target)
        _fsync_dir(target.parent)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _load_bindings() -> dict:
    explicit_cert = os.environ.get("KEDDEH_SERVER_TLS_CERT_TARGET")
    explicit_key = os.environ.get("KEDDEH_SERVER_TLS_KEY_TARGET")
    if explicit_cert and explicit_key:
        return {
            "certificate_target": explicit_cert,
            "private_key_target": explicit_key,
            "restart_command": os.environ.get("KEDDEH_SERVER_TLS_RESTART_COMMAND", str(FABRIC_ROOT / "START_FULL_DOMAIN_FABRIC.command")),
            "readback_host": os.environ.get("KEDDEH_SERVER_TLS_READBACK_HOST", "127.0.0.1"),
            "readback_port": int(os.environ.get("KEDDEH_SERVER_TLS_READBACK_PORT", "8443")),
        }
    if not BINDINGS.is_file():
        raise RuntimeError(f"SERVER_TLS_BINDINGS_UNRESOLVED:{BINDINGS}")
    data = json.loads(BINDINGS.read_text("utf-8"))
    required = ("certificate_target", "private_key_target", "restart_command")
    missing = [k for k in required if not data.get(k)]
    if missing:
        raise RuntimeError(f"SERVER_TLS_BINDINGS_INCOMPLETE:{missing}")
    data.setdefault("readback_host", "127.0.0.1")
    data.setdefault("readback_port", 8443)
    return data


def _leaf_der_from_pem(path: Path) -> bytes:
    text = path.read_text("utf-8")
    begin = text.find("-----BEGIN CERTIFICATE-----")
    end = text.find("-----END CERTIFICATE-----")
    if begin < 0 or end < 0:
        raise RuntimeError("SERVER_TLS_CERTIFICATE_PEM_INVALID")
    end += len("-----END CERTIFICATE-----")
    pem = text[begin:end]
    return ssl.PEM_cert_to_DER_cert(pem)


def _live_leaf(host: str, port: int, domain: str) -> tuple[str, str | None]:
    context = ssl._create_unverified_context()
    with socket.create_connection((host, port), timeout=8.0) as raw:
        with context.wrap_socket(raw, server_hostname=domain) as tls:
            peer = tls.getpeercert(binary_form=True)
            if not peer:
                raise RuntimeError("SERVER_TLS_LIVE_CERTIFICATE_MISSING")
            return _sha256(peer), tls.version()


def _restart(command: str) -> str:
    proc = subprocess.run(["bash", command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError("SERVER_TLS_RESTART_FAILED:" + proc.stderr[-4000:])
    return proc.stdout[-8000:]


def _backup(domain: str, cert_target: Path, key_target: Path) -> Path:
    stamp = str(time.time_ns())
    root = BACKUP_ROOT / domain / stamp
    root.mkdir(parents=True, exist_ok=False)
    meta = {"domain": domain, "created_ns": time.time_ns(), "certificate_existed": cert_target.exists(), "key_existed": key_target.exists()}
    if cert_target.exists():
        shutil.copy2(cert_target, root / "certificate.pem")
        meta["certificate_sha256"] = _sha256(cert_target.read_bytes())
    if key_target.exists():
        shutil.copy2(key_target, root / "private-key.pem")
        meta["private_key_sha256"] = _sha256(key_target.read_bytes())
    (root / "snapshot.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", "utf-8")
    latest = BACKUP_ROOT / domain / "LATEST"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(str(root) + "\n", "utf-8")
    return root


def install(domain: str, fullchain: Path, private_key: Path) -> dict:
    if not domain:
        raise RuntimeError("SERVER_TLS_DOMAIN_MISSING")
    if not fullchain.is_file() or not private_key.is_file():
        raise RuntimeError("SERVER_TLS_SOURCE_MATERIAL_MISSING")
    bindings = _load_bindings()
    cert_target = Path(bindings["certificate_target"]).expanduser().resolve()
    key_target = Path(bindings["private_key_target"]).expanduser().resolve()
    restart_command = str(Path(bindings["restart_command"]).expanduser().resolve())
    if not Path(restart_command).is_file():
        raise RuntimeError(f"SERVER_TLS_RESTART_COMMAND_NOT_FOUND:{restart_command}")
    snapshot = _backup(domain, cert_target, key_target)
    requested_fp = _sha256(_leaf_der_from_pem(fullchain))
    try:
        _atomic_copy(fullchain, cert_target, 0o644)
        _atomic_copy(private_key, key_target, 0o600)
        restart_output = _restart(restart_command)
        observed_fp, tls_version = _live_leaf(str(bindings["readback_host"]), int(bindings["readback_port"]), domain)
        if observed_fp != requested_fp:
            raise RuntimeError(f"SERVER_TLS_LIVE_FINGERPRINT_MISMATCH:requested={requested_fp}:observed={observed_fp}")
        receipt = {
            "schema": "kex.braink.server-tls-actuator.v1",
            "operation": "INSTALL",
            "domain": domain,
            "certificate_target": str(cert_target),
            "private_key_target": str(key_target),
            "requested_certificate_sha256": requested_fp,
            "observed_certificate_sha256": observed_fp,
            "tls_version": tls_version,
            "snapshot": str(snapshot),
            "restart_output": restart_output,
            "status": "SERVER_TLS_BOUND",
        }
    except Exception:
        from assets.public_tls_host_actuators.rollback_server_tls import rollback
        rollback(domain, snapshot_override=snapshot)
        raise
    RECEIPT_ROOT.mkdir(parents=True, exist_ok=True)
    (RECEIPT_ROOT / f"{domain}.install.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", "utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("install",))
    parser.add_argument("--domain", default=os.environ.get("KEDDEH_TLS_DOMAIN", ""))
    parser.add_argument("--fullchain", type=Path, default=Path(os.environ.get("KEDDEH_TLS_FULLCHAIN", "")))
    parser.add_argument("--private-key", type=Path, default=Path(os.environ.get("KEDDEH_TLS_PRIVATE_KEY", "")))
    args = parser.parse_args()
    print(json.dumps(install(args.domain, args.fullchain, args.private_key), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
