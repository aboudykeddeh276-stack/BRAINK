from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import time

FABRIC_ROOT = Path(os.environ.get("KEDDEH_DOMAIN_FABRIC_ROOT", "/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5"))
BINDINGS = Path(os.environ.get("KEDDEH_HOST_ACTUATOR_BINDINGS", "deploy/braink-public/BRAINK_HOST_ACTUATOR_BINDINGS.json"))
BACKUP_ROOT = Path(os.environ.get("KEDDEH_TLS_BACKUP_ROOT", "/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5_EVIDENCE/TLS_BACKUPS"))
RECEIPT_ROOT = Path(os.environ.get("KEDDEH_TLS_ACTUATOR_RECEIPT_ROOT", "/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5_EVIDENCE/TLS_ACTUATORS"))


def _load_bindings() -> dict:
    explicit_cert = os.environ.get("KEDDEH_SERVER_TLS_CERT_TARGET")
    explicit_key = os.environ.get("KEDDEH_SERVER_TLS_KEY_TARGET")
    if explicit_cert and explicit_key:
        return {
            "certificate_target": explicit_cert,
            "private_key_target": explicit_key,
            "restart_command": os.environ.get("KEDDEH_SERVER_TLS_RESTART_COMMAND", str(FABRIC_ROOT / "START_FULL_DOMAIN_FABRIC.command")),
        }
    if not BINDINGS.is_file():
        raise RuntimeError(f"SERVER_TLS_BINDINGS_UNRESOLVED:{BINDINGS}")
    data = json.loads(BINDINGS.read_text("utf-8"))
    for key in ("certificate_target", "private_key_target", "restart_command"):
        if not data.get(key):
            raise RuntimeError(f"SERVER_TLS_BINDING_MISSING:{key}")
    return data


def _latest_snapshot(domain: str) -> Path:
    marker = BACKUP_ROOT / domain / "LATEST"
    if not marker.is_file():
        raise RuntimeError(f"SERVER_TLS_ROLLBACK_SNAPSHOT_UNAVAILABLE:{domain}")
    path = Path(marker.read_text("utf-8").strip())
    if not path.is_dir():
        raise RuntimeError(f"SERVER_TLS_ROLLBACK_SNAPSHOT_MISSING:{path}")
    return path


def rollback(domain: str, *, snapshot_override: Path | None = None) -> dict:
    bindings = _load_bindings()
    cert_target = Path(bindings["certificate_target"]).expanduser().resolve()
    key_target = Path(bindings["private_key_target"]).expanduser().resolve()
    restart_command = str(Path(bindings["restart_command"]).expanduser().resolve())
    snapshot = snapshot_override or _latest_snapshot(domain)
    meta = json.loads((snapshot / "snapshot.json").read_text("utf-8"))

    if meta.get("certificate_existed"):
        shutil.copy2(snapshot / "certificate.pem", cert_target)
    elif cert_target.exists():
        cert_target.unlink()

    if meta.get("key_existed"):
        shutil.copy2(snapshot / "private-key.pem", key_target)
    elif key_target.exists():
        key_target.unlink()

    proc = subprocess.run(["bash", restart_command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError("SERVER_TLS_ROLLBACK_RESTART_FAILED:" + proc.stderr[-4000:])

    receipt = {
        "schema": "kex.braink.server-tls-actuator.v1",
        "operation": "ROLLBACK",
        "domain": domain,
        "snapshot": str(snapshot),
        "restored_certificate": bool(meta.get("certificate_existed")),
        "restored_private_key": bool(meta.get("key_existed")),
        "restart_output": proc.stdout[-8000:],
        "completed_ns": time.time_ns(),
        "status": "SERVER_TLS_ROLLED_BACK",
    }
    RECEIPT_ROOT.mkdir(parents=True, exist_ok=True)
    (RECEIPT_ROOT / f"{domain}.rollback.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", "utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", default=os.environ.get("KEDDEH_TLS_DOMAIN", ""))
    args = parser.parse_args()
    if not args.domain:
        raise RuntimeError("SERVER_TLS_DOMAIN_MISSING")
    print(json.dumps(rollback(args.domain), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
