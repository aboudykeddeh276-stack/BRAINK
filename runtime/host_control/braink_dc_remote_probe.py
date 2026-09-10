#!/usr/bin/env python3
"""External BRAINK Desktop Commander host probe.

This executable is intended to be invoked on the target host through the Desktop
Commander remote control path. It answers a BRAINK activation challenge by
performing bounded host capability probes and atomically writing a correlated
response receipt.

This is operational carrier-path evidence, not cryptographic hardware or carrier
attestation. BRAINK authority remains separate from the carrier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import tempfile
import time
from pathlib import Path
from typing import Any, Dict


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


def run_probe(challenge_path: Path, response_path: Path) -> Dict[str, Any]:
    challenge = read_json(challenge_path)
    required = {"challenge_id", "nonce", "issued_ns", "challenge_root", "required_actor"}
    if not required.issubset(challenge):
        raise RuntimeError("HOST_CHALLENGE_INCOMPLETE")
    expected_root = sha({k: v for k, v in challenge.items() if k != "challenge_root"})
    if challenge["challenge_root"] != expected_root:
        raise RuntimeError("HOST_CHALLENGE_ROOT_INVALID")
    if challenge["required_actor"] != "desktop-commander-remote":
        raise RuntimeError("HOST_CHALLENGE_ACTOR_INVALID")

    test_dir = Path(tempfile.gettempdir()) / "braink-host-control-proof"
    test_dir.mkdir(parents=True, exist_ok=True)
    probe = test_dir / f"{challenge['challenge_id']}.txt"
    payload = f"BRAINK_HOST_CONTROL_PROBE:{challenge['nonce']}\n"
    probe.write_text(payload, encoding="utf-8")
    readback = probe.read_text(encoding="utf-8")
    probe.unlink(missing_ok=True)
    if readback != payload:
        raise RuntimeError("FILESYSTEM_READBACK_MISMATCH")

    result = {
        "challenge_id": challenge["challenge_id"],
        "challenge_root": challenge["challenge_root"],
        "nonce": challenge["nonce"],
        "proved_ns": time.time_ns(),
        "actor": "desktop-commander-remote",
        "transport_claim": "desktop-commander-remote",
        "attestation_class": "OPERATIONAL_CORRELATION",
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "uid": os.getuid() if hasattr(os, "getuid") else None,
        "euid": os.geteuid() if hasattr(os, "geteuid") else None,
        "capability_probe": {
            "filesystem_write": True,
            "filesystem_readback": True,
            "hostname_read": bool(socket.gethostname()),
            "platform_read": bool(platform.system()),
        },
    }
    result["response_root"] = sha(result)
    write_json_atomic(response_path, result)
    return result


def self_test() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        c = {
            "challenge_id": "self-test",
            "nonce": "abc123",
            "issued_ns": time.time_ns(),
            "hostname": "controller",
            "required_actor": "desktop-commander-remote",
        }
        c["challenge_root"] = sha(c)
        cp = root / "challenge.json"
        rp = root / "response.json"
        write_json_atomic(cp, c)
        r = run_probe(cp, rp)
        assert r["challenge_root"] == c["challenge_root"]
        assert r["transport_claim"] == "desktop-commander-remote"
        assert r["attestation_class"] == "OPERATIONAL_CORRELATION"
        assert all(r["capability_probe"].values())
        assert rp.exists()
    return {"status": "PASS", "checks": ["challenge_integrity", "bounded_probe", "atomic_response", "transport_claim"]}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--challenge")
    p.add_argument("--response")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        print(json.dumps(self_test(), indent=2)); return 0
    if not a.challenge or not a.response:
        p.error("--challenge and --response are required")
    print(json.dumps(run_probe(Path(a.challenge), Path(a.response)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
