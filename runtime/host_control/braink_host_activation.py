#!/usr/bin/env python3
"""BRAINK deterministic host activation gate.

Promotes a host to HOST_READY only after:
1. BRAINK/KEX authority root is bound.
2. Desktop Commander carrier supervisor reports a fresh RUNNING state.
3. A separate externally executed Desktop Commander probe returns a correlated response.
4. Capability readback in that response succeeds.
5. The resulting host heartbeat is written into HostFabric.

The Desktop Commander carrier is transport, not identity or authority. The probe is
operational correlation evidence, not cryptographic carrier or hardware attestation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from runtime.host_control.braink_host_fabric import HostFabric, receipt as fabric_receipt

ROOT = Path(__file__).resolve().parents[2]
HOST_CONTROL_STATE = Path(os.getenv("BRAINK_HOST_CONTROL_STATE", Path.home() / ".braink" / "host-control"))
DC_STATE = HOST_CONTROL_STATE / "desktop-commander-state.json"
ACTIVATION_DIR = Path(os.getenv("BRAINK_HOST_ACTIVATION_STATE", ROOT / ".kex" / "state" / "host_activation"))
CHALLENGE = ACTIVATION_DIR / "challenge.json"
RESPONSE = ACTIVATION_DIR / "response.json"
ACTIVATION_RECEIPT = ACTIVATION_DIR / "activation-receipt.json"
MAX_CARRIER_AGE_SEC = int(os.getenv("BRAINK_DC_STATE_TTL_SEC", "30"))
MAX_RESPONSE_AGE_SEC = int(os.getenv("BRAINK_HOST_RESPONSE_TTL_SEC", "120"))


def canon(v: Any) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(v: Any) -> str:
    return hashlib.sha256(canon(v)).hexdigest()


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def issue_challenge() -> Dict[str, Any]:
    ACTIVATION_DIR.mkdir(parents=True, exist_ok=True)
    body = {
        "challenge_id": str(uuid.uuid4()),
        "nonce": uuid.uuid4().hex,
        "issued_ns": time.time_ns(),
        "hostname": socket.gethostname(),
        "required_actor": "desktop-commander-remote",
    }
    body["challenge_root"] = sha(body)
    write_json_atomic(CHALLENGE, body)
    RESPONSE.unlink(missing_ok=True)
    return body


def carrier_state() -> Dict[str, Any]:
    if not DC_STATE.exists():
        raise RuntimeError("DESKTOP_COMMANDER_STATE_UNOBSERVED")
    state = read_json(DC_STATE)
    if state.get("status") != "RUNNING" or state.get("mode") != "remote":
        raise RuntimeError("DESKTOP_COMMANDER_NOT_RUNNING_REMOTE")
    updated = state.get("updated_at")
    if not updated:
        raise RuntimeError("DESKTOP_COMMANDER_STATE_HAS_NO_TIME")
    ts = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - ts).total_seconds()
    if age < 0 or age > MAX_CARRIER_AGE_SEC:
        raise RuntimeError(f"DESKTOP_COMMANDER_STATE_STALE:{age:.3f}")
    return {**state, "age_sec": round(age, 3)}


def verify_response() -> Dict[str, Any]:
    if not CHALLENGE.exists() or not RESPONSE.exists():
        raise RuntimeError("EXTERNAL_CARRIER_CHALLENGE_RESPONSE_INCOMPLETE")
    c = read_json(CHALLENGE)
    r = read_json(RESPONSE)
    expected_challenge_root = sha({k: v for k, v in c.items() if k != "challenge_root"})
    if c.get("challenge_root") != expected_challenge_root:
        raise RuntimeError("CARRIER_CHALLENGE_ROOT_INVALID")
    if r.get("challenge_id") != c.get("challenge_id") or r.get("challenge_root") != c.get("challenge_root"):
        raise RuntimeError("CARRIER_RESPONSE_CHALLENGE_MISMATCH")
    if r.get("nonce") != c.get("nonce"):
        raise RuntimeError("CARRIER_RESPONSE_NONCE_MISMATCH")
    if r.get("actor") != "desktop-commander-remote" or r.get("transport_claim") != "desktop-commander-remote":
        raise RuntimeError("CARRIER_RESPONSE_TRANSPORT_MISMATCH")
    if r.get("attestation_class") != "OPERATIONAL_CORRELATION":
        raise RuntimeError("CARRIER_RESPONSE_ATTESTATION_CLASS_INVALID")
    expected_response_root = sha({k: v for k, v in r.items() if k != "response_root"})
    if r.get("response_root") != expected_response_root:
        raise RuntimeError("CARRIER_RESPONSE_ROOT_INVALID")
    age = (time.time_ns() - int(r.get("proved_ns", 0))) / 1e9
    if age < 0 or age > MAX_RESPONSE_AGE_SEC:
        raise RuntimeError(f"CARRIER_RESPONSE_STALE:{age:.3f}")
    probes = r.get("capability_probe", {})
    required_probes = {"filesystem_write", "filesystem_readback", "hostname_read", "platform_read"}
    if not required_probes.issubset(probes) or not all(bool(probes[k]) for k in required_probes):
        raise RuntimeError("CAPABILITY_PROBE_FAILED")
    return {**r, "age_sec": round(age, 3)}


def activate() -> Dict[str, Any]:
    authority_root = os.getenv("BRAINK_HOST_AUTHORITY_ROOT", "UNBOUND")
    if authority_root == "UNBOUND" or not authority_root:
        raise PermissionError("BRAINK_HOST_AUTHORITY_ROOT_UNBOUND")

    dc = carrier_state()
    response = verify_response()
    fabric = HostFabric()
    host = fabric.discover_local(carrier="desktop-commander")
    if host.get("hostname") != response.get("hostname"):
        raise RuntimeError("CARRIER_RESPONSE_HOSTNAME_MISMATCH")
    host = fabric.heartbeat(host["host_id"], observed_mode="ONLINE")

    result = {
        "status": "HOST_READY",
        "host_id": host["host_id"],
        "node_id": host["node_id"],
        "carrier": "desktop-commander",
        "carrier_pid": dc.get("pid"),
        "carrier_state_age_sec": dc.get("age_sec"),
        "carrier_response_root": response["response_root"],
        "carrier_attestation_class": response["attestation_class"],
        "authority_root": authority_root,
        "admission_state": host["admission_state"],
        "observed_mode": host["observed_mode"],
        "activated_ns": time.time_ns(),
    }
    result["proof_root"] = sha(result)
    write_json_atomic(ACTIVATION_RECEIPT, result)
    fabric_receipt("HOST_ACTIVATION_PROVEN", **result)
    return result


def self_test() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        c = {
            "challenge_id": "x",
            "nonce": "n",
            "issued_ns": time.time_ns(),
            "hostname": "h",
            "required_actor": "desktop-commander-remote",
        }
        c["challenge_root"] = sha(c)
        r = {
            "challenge_id": "x",
            "challenge_root": c["challenge_root"],
            "nonce": "n",
            "proved_ns": time.time_ns(),
            "actor": "desktop-commander-remote",
            "transport_claim": "desktop-commander-remote",
            "attestation_class": "OPERATIONAL_CORRELATION",
            "hostname": "h",
            "os": "Linux",
            "kernel": "k",
            "architecture": "x86_64",
            "uid": 1000,
            "euid": 1000,
            "capability_probe": {"filesystem_write": True, "filesystem_readback": True, "hostname_read": True, "platform_read": True},
        }
        r["response_root"] = sha(r)
        cp = root / "challenge.json"
        rp = root / "response.json"
        write_json_atomic(cp, c)
        write_json_atomic(rp, r)
        assert read_json(cp)["challenge_root"] == c["challenge_root"]
        assert read_json(rp)["response_root"] == r["response_root"]
        assert r["transport_claim"] == "desktop-commander-remote"
        assert all(r["capability_probe"].values())
    return {"status": "PASS", "checks": ["challenge_integrity", "response_integrity", "transport_contract", "capability_probe_contract"]}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--issue-challenge", action="store_true")
    p.add_argument("--activate", action="store_true")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.issue_challenge:
        print(json.dumps(issue_challenge(), indent=2)); return 0
    if a.activate:
        print(json.dumps(activate(), indent=2)); return 0
    if a.self_test:
        print(json.dumps(self_test(), indent=2)); return 0
    p.print_help(); return 2


if __name__ == "__main__":
    raise SystemExit(main())
