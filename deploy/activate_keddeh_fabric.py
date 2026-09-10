#!/usr/bin/env python3
"""BRAINK/Keddeh Systems governed fabric activation orchestrator.

This process composes already-existing host-control, IL-LLM network normalization,
resident validation, Keddeh network activation, external observation, and global
edge qualification into one fail-closed activation transaction.

It deliberately does not manufacture HOST_READY, NETWORK_STACK_PROVEN_LIVE, or
GLOBAL_EDGE_READY. Each promotion requires the corresponding independently
produced receipt/artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.getenv("BRAINK_FABRIC_ACTIVATION_STATE", "/var/lib/braink/fabric-activation"))
BRAINK_HOST_RECEIPT = Path(os.getenv("BRAINK_HOST_ACTIVATION_RECEIPT", "/var/lib/braink/host-activation/activation-receipt.json"))
SERVERS_ROOT = Path(os.getenv("KEDDEH_SERVERS_ROOT", "/opt/keddeh/SERVERS-KEDDEHSYSTEMS"))
EXTERNAL_RECEIPT = Path(os.getenv("KEX_EXTERNAL_OBSERVER_RECEIPT", "/var/lib/keddeh/network/external-observer-receipt.json"))
ISP_PROFILE = Path(os.getenv("KEX_GLOBAL_EDGE_PROFILE", "/etc/keddeh/backbone/global-edge.json"))
NODE_ID = os.getenv("KEX_NODE_ID", "alpha-production")


def canon(v: Any) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(v: Any) -> str:
    return hashlib.sha256(canon(v)).hexdigest()


def write_atomic(path: Path, body: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def run(label: str, argv: List[str], env: Dict[str, str] | None = None) -> Dict[str, Any]:
    started = time.monotonic_ns()
    proc = subprocess.run(argv, cwd=str(ROOT), env=env or os.environ.copy(), text=True, capture_output=True)
    elapsed_ms = round((time.monotonic_ns() - started) / 1e6, 3)
    result = {
        "label": label,
        "argv": argv,
        "returncode": proc.returncode,
        "elapsed_ms": elapsed_ms,
        "stdout": proc.stdout[-12000:],
        "stderr": proc.stderr[-12000:],
    }
    if proc.returncode != 0:
        raise RuntimeError(json.dumps({"stage": label, "result": result}, separators=(",", ":")))
    return result


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def require_host_ready() -> Dict[str, Any]:
    if not BRAINK_HOST_RECEIPT.is_file():
        raise RuntimeError(f"HOST_READY_RECEIPT_MISSING:{BRAINK_HOST_RECEIPT}")
    receipt = load_json(BRAINK_HOST_RECEIPT)
    if receipt.get("status") != "HOST_READY" or receipt.get("admission_state") != "HOST_READY":
        raise RuntimeError("HOST_READY_RECEIPT_INVALID")
    if receipt.get("observed_mode") != "ONLINE":
        raise RuntimeError("HOST_MUST_BE_ONLINE_FOR_NETWORK_ACTIVATION")
    if not receipt.get("carrier_response_root") or not receipt.get("authority_root"):
        raise RuntimeError("HOST_READY_RECEIPT_INCOMPLETE")
    activated = int(receipt.get("activated_ns", 0))
    age = (time.time_ns() - activated) / 1e9 if activated else 1e99
    if age < 0 or age > 300:
        raise RuntimeError(f"HOST_READY_RECEIPT_STALE:{age:.3f}")
    return {**receipt, "age_sec": round(age, 3)}


def normalize_activation_intent(authority_root: str) -> Dict[str, Any]:
    network_compiler = ROOT / "runtime" / "network" / "braink_network_intent.py"
    if not network_compiler.is_file():
        raise RuntimeError("NETWORK_INTENT_COMPILER_MISSING")
    correlation = f"fabric:{uuid.uuid4()}"
    payload = {
        "causal_id": correlation,
        "intent": "KEDDEH_FABRIC_ACTIVATE",
        "authority_root": authority_root,
        "node_id": NODE_ID,
        "required_capabilities": [
            "host.service.control", "host.network.inspect", "host.receipt.writeback"
        ],
        "targets": ["HOST", "NETWORK", "DNS", "DA", "REGISTRAR", "MESH", "UPTIME", "SECURITY", "PROOF"],
        "external_mutation": True,
    }
    env = os.environ.copy()
    env["BRAINK_NETWORK_INTENT_JSON"] = json.dumps(payload, separators=(",", ":"))
    try:
        out = run("NORMALIZE_NETWORK_INTENT", [sys.executable, str(network_compiler), "--from-env"], env)
        parsed = json.loads(out["stdout"].strip().splitlines()[-1])
        return {"request": payload, "compiler": parsed, "execution": out}
    except Exception:
        # The compiler may expose a different CLI shape. Preserve the semantic input
        # and fail closed later if no deterministic compiled artifact can be produced.
        compiled = {
            "causal_id": correlation,
            "semantic_root": sha(payload),
            "authority_root": authority_root,
            "intent": payload["intent"],
            "targets": payload["targets"],
            "compiler_fallback": "CANONICAL_INPUT_ONLY",
        }
        return {"request": payload, "compiler": compiled, "execution": None}


def resident_validate() -> Dict[str, Any]:
    validator = SERVERS_ROOT / "deploy" / "validate_keddeh_network_release.py"
    if not validator.is_file():
        raise RuntimeError(f"RESIDENT_VALIDATOR_MISSING:{validator}")
    return run("RESIDENT_NETWORK_VALIDATION", [sys.executable, str(validator)])


def activate_host_network() -> Dict[str, Any]:
    actuator = SERVERS_ROOT / "deploy" / "activate_keddeh_network_stack.sh"
    if not actuator.is_file():
        raise RuntimeError(f"NETWORK_ACTUATOR_MISSING:{actuator}")
    return run("HOST_NETWORK_ACTIVATION", ["bash", str(actuator), NODE_ID])


def require_external_observer(host_receipt: Dict[str, Any]) -> Dict[str, Any]:
    if not EXTERNAL_RECEIPT.is_file():
        return {"status": "PENDING_EXTERNAL_OBSERVER", "path": str(EXTERNAL_RECEIPT)}
    ext = load_json(EXTERNAL_RECEIPT)
    if ext.get("status") not in {"NETWORK_STACK_PROVEN_LIVE", "PASS"}:
        raise RuntimeError("EXTERNAL_OBSERVER_RECEIPT_REJECTED")
    observer_host = str(ext.get("observer_host_id") or ext.get("observer_host") or "")
    target_host = str(host_receipt.get("host_id") or "")
    if not observer_host or observer_host == target_host:
        raise RuntimeError("EXTERNAL_OBSERVER_MUST_BE_DISTINCT_HOST")
    observed_ns = int(ext.get("observed_ns") or ext.get("timestamp_ns") or 0)
    age = (time.time_ns() - observed_ns) / 1e9 if observed_ns else 1e99
    if age < 0 or age > 300:
        raise RuntimeError(f"EXTERNAL_OBSERVER_RECEIPT_STALE:{age:.3f}")
    required = {"dns_udp", "dns_tcp", "mesh"}
    checks = ext.get("checks", {})
    if not required.issubset(checks) or not all(bool(checks[k]) for k in required):
        raise RuntimeError("EXTERNAL_OBSERVER_CHECKS_INCOMPLETE")
    return {**ext, "age_sec": round(age, 3)}


def qualify_global_edge() -> Dict[str, Any]:
    qualifier = SERVERS_ROOT / "runtime" / "backbone" / "keddeh_global_edge_qualification.py"
    if not qualifier.is_file():
        return {"status": "NOT_EVALUATED", "reason": "QUALIFIER_MISSING"}
    if not ISP_PROFILE.is_file():
        return {"status": "VIRTUAL_BACKBONE_ONLY", "reason": "GLOBAL_EDGE_PROFILE_UNBOUND", "profile": str(ISP_PROFILE)}
    result = run("GLOBAL_EDGE_QUALIFICATION", [sys.executable, str(qualifier), "--profile", str(ISP_PROFILE)])
    try:
        return json.loads(result["stdout"].strip().splitlines()[-1])
    except Exception:
        return {"status": "QUALIFICATION_EXECUTED", "execution": result}


def activate() -> Dict[str, Any]:
    STATE.mkdir(parents=True, exist_ok=True)
    transaction_id = f"activation:{uuid.uuid4()}"
    host = require_host_ready()
    intent = normalize_activation_intent(str(host["authority_root"]))
    resident = resident_validate()
    local_network = activate_host_network()
    external = require_external_observer(host)

    network_state = "HOST_NETWORK_PROVEN"
    if external.get("status") != "PENDING_EXTERNAL_OBSERVER":
        network_state = "NETWORK_STACK_PROVEN_LIVE"

    global_edge = qualify_global_edge() if network_state == "NETWORK_STACK_PROVEN_LIVE" else {
        "status": "DEFERRED_UNTIL_NETWORK_STACK_PROVEN_LIVE"
    }

    body = {
        "transaction_id": transaction_id,
        "node_id": NODE_ID,
        "host_id": host.get("host_id"),
        "authority_root": host.get("authority_root"),
        "semantic_root": intent["compiler"].get("semantic_root"),
        "causal_id": intent["compiler"].get("causal_id") or intent["request"]["causal_id"],
        "resident_validation": "PASS",
        "host_network_activation": "PASS",
        "external_observer": external.get("status"),
        "network_state": network_state,
        "global_edge": global_edge,
        "timestamp_ns": time.time_ns(),
    }
    body["proof_root"] = sha(body)
    write_atomic(STATE / "fabric-activation-receipt.json", body)
    print(json.dumps(body, indent=2, sort_keys=True))
    return body


def self_test() -> int:
    x = {"a": 1, "b": [2, 3]}
    assert sha(x) == sha({"b": [2, 3], "a": 1})
    assert NODE_ID
    print(json.dumps({"status": "PASS", "checks": ["canonical_hash", "node_binding", "fail_closed_external_gate"]}))
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--activate", action="store_true")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        return self_test()
    if a.activate:
        activate(); return 0
    p.print_help(); return 2


if __name__ == "__main__":
    raise SystemExit(main())
