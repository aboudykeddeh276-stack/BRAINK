from __future__ import annotations

"""Resolve a fail-closed SERVER_ROOT/REGISTRAR binding manifest from discovery evidence."""

from pathlib import Path
import json
import os
import re

DISCOVERY = Path(os.environ.get("KEDDEH_HOST_ACTUATOR_DISCOVERY", "deploy/braink-public/BRAINK_HOST_ACTUATOR_DISCOVERY.json"))
OUTPUT = Path(os.environ.get("KEDDEH_HOST_ACTUATOR_BINDINGS", "deploy/braink-public/BRAINK_HOST_ACTUATOR_BINDINGS.json"))
PATH_RE = re.compile(r"(?P<path>/[^\s'\";,()]+)")


def _candidate_paths(discovery: dict) -> tuple[set[str], set[str]]:
    certs: set[str] = set()
    keys: set[str] = set()
    for ref in discovery.get("tls_references", []):
        for match in ref.get("matches", []):
            for hit in PATH_RE.finditer(match.get("text", "")):
                path = hit.group("path").rstrip("]}")
                low = path.lower()
                if any(token in low for token in ("fullchain", "cert.pem", ".crt", ".cer")):
                    certs.add(path)
                if any(token in low for token in ("privkey", "private", "key.pem", ".key")):
                    keys.add(path)
    return certs, keys


def _one(values: set[str], label: str) -> str:
    existing = sorted(v for v in values if Path(v).exists())
    if len(existing) != 1:
        raise RuntimeError(f"HOST_BINDING_{label}_AMBIGUOUS:{existing}")
    return existing[0]


def resolve(discovery_path: Path = DISCOVERY, output: Path = OUTPUT) -> dict:
    if not discovery_path.is_file():
        raise RuntimeError(f"HOST_ACTUATOR_DISCOVERY_MISSING:{discovery_path}")
    d = json.loads(discovery_path.read_text("utf-8"))
    if not d.get("fabric_exists") or not d.get("restart_command_exists"):
        raise RuntimeError("HOST_FABRIC_NOT_RESOLVED")

    explicit = d.get("explicit_bindings", {})
    cert = explicit.get("KEDDEH_SERVER_CERT_PATH") or os.environ.get("KEDDEH_SERVER_TLS_CERT_TARGET")
    key = explicit.get("KEDDEH_SERVER_KEY_PATH") or os.environ.get("KEDDEH_SERVER_TLS_KEY_TARGET")
    discovered_certs, discovered_keys = _candidate_paths(d)
    if not cert:
        cert = _one(discovered_certs, "CERTIFICATE")
    if not key:
        key = _one(discovered_keys, "PRIVATE_KEY")

    registrar = explicit.get("KEDDEH_REGISTRAR_DB") or os.environ.get("KEDDEH_REGISTRAR_DB")
    if not registrar:
        dbs = [p for p in d.get("registrar_databases", []) if Path(p).is_file()]
        if len(dbs) != 1:
            raise RuntimeError(f"HOST_BINDING_REGISTRAR_AMBIGUOUS:{dbs}")
        registrar = dbs[0]

    bindings = {
        "schema": "kex.braink.host-actuator-bindings.v1",
        "fabric_root": d["fabric_root"],
        "registrar_db": str(Path(registrar).resolve()),
        "certificate_target": str(Path(cert).resolve()),
        "private_key_target": str(Path(key).resolve()),
        "restart_command": str(Path(d["restart_command"]).resolve()),
        "readback_host": d.get("local_tls", {}).get("host", "127.0.0.1"),
        "readback_port": int(d.get("local_tls", {}).get("port", 8443)),
        "source_discovery": str(discovery_path),
    }
    for field in ("registrar_db", "certificate_target", "private_key_target", "restart_command"):
        if not Path(bindings[field]).exists():
            raise RuntimeError(f"HOST_BINDING_TARGET_NOT_FOUND:{field}:{bindings[field]}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bindings, indent=2, sort_keys=True) + "\n", "utf-8")
    return bindings


def main() -> int:
    print(json.dumps(resolve(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
