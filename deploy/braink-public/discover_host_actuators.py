#!/usr/bin/env python3
from __future__ import annotations

"""Read-only discovery of concrete resident public-TLS actuator boundaries.

This probe runs on the self-hosted KEDDEH fabric machine and reports the actual
registrar database, restart command, local TLS listener, candidate certificate/key
paths, and ACME tooling.  It does not mutate DNS, certificates, or server state.
"""

from pathlib import Path
import json
import os
import shutil
import socket
import ssl
import subprocess
import time

FABRIC = Path(os.environ.get("KEDDEH_DOMAIN_FABRIC_ROOT", "/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5")).resolve()
EVIDENCE = Path(os.environ.get("KEDDEH_EVIDENCE_ROOT", "/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5_EVIDENCE")).resolve()
OUT = Path(os.environ.get("KEDDEH_HOST_ACTUATOR_DISCOVERY", "deploy/braink-public/BRAINK_HOST_ACTUATOR_DISCOVERY.json"))


def existing(paths):
    return [str(p) for p in paths if p.exists()]


def registrar_candidates():
    direct = [
        FABRIC / "substrate_ledger" / "keddeh_registrar.sqlite",
        FABRIC / "runtime" / "domain_authority" / "substrate_ledger" / "keddeh_registrar.sqlite",
        FABRIC / "keddeh_registrar.sqlite",
    ]
    recursive = list(FABRIC.rglob("keddeh_registrar.sqlite")) if FABRIC.exists() else []
    seen = []
    for p in direct + recursive:
        s = str(p)
        if p.is_file() and s not in seen:
            seen.append(s)
    return seen


def scan_tls_references():
    refs = []
    suffixes = {".py", ".sh", ".command", ".json", ".yaml", ".yml", ".toml", ".conf", ".ini"}
    if not FABRIC.exists():
        return refs
    count = 0
    for path in FABRIC.rglob("*"):
        if count >= 1500:
            break
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        count += 1
        try:
            text = path.read_text("utf-8", errors="ignore")
        except Exception:
            continue
        low = text.lower()
        if any(token in low for token in ("load_cert_chain", "certfile", "keyfile", "fullchain", "privkey", "8443", "sslcontext")):
            lines = []
            for i, line in enumerate(text.splitlines(), 1):
                ll = line.lower()
                if any(token in ll for token in ("load_cert_chain", "certfile", "keyfile", "fullchain", "privkey", "8443", "sslcontext")):
                    lines.append({"line": i, "text": line[:500]})
            refs.append({"path": str(path), "matches": lines[:30]})
    return refs[:100]


def local_tls_probe(host="127.0.0.1", port=8443):
    result = {"host": host, "port": port, "reachable": False}
    try:
        ctx = ssl._create_unverified_context()
        with socket.create_connection((host, port), timeout=3) as raw:
            with ctx.wrap_socket(raw, server_hostname="braink.com.au") as tls:
                result.update({
                    "reachable": True,
                    "tls_version": tls.version(),
                    "cipher": tls.cipher(),
                    "peer_certificate_present": bool(tls.getpeercert(binary_form=True)),
                })
    except Exception as exc:
        result["error"] = str(exc)
    return result


def main():
    restart = FABRIC / "START_FULL_DOMAIN_FABRIC.command"
    acme_candidates = {
        name: shutil.which(name)
        for name in ("certbot", "lego", "acme.sh", "step")
    }
    data = {
        "schema": "kex.braink.host-actuator-discovery.v1",
        "discovered_ns": time.time_ns(),
        "fabric_root": str(FABRIC),
        "fabric_exists": FABRIC.exists(),
        "evidence_root": str(EVIDENCE),
        "restart_command": str(restart),
        "restart_command_exists": restart.is_file(),
        "registrar_databases": registrar_candidates(),
        "acme_clients": acme_candidates,
        "local_tls": local_tls_probe(),
        "tls_references": scan_tls_references(),
        "explicit_bindings": {
            "KEDDEH_SERVER_CERT_PATH": os.environ.get("KEDDEH_SERVER_CERT_PATH"),
            "KEDDEH_SERVER_KEY_PATH": os.environ.get("KEDDEH_SERVER_KEY_PATH"),
            "KEDDEH_REGISTRAR_DB": os.environ.get("KEDDEH_REGISTRAR_DB"),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", "utf-8")
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
