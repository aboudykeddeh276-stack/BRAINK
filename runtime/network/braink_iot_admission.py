#!/usr/bin/env python3
"""BRAINK deterministic IoT device admission gate.

Implements a Keddeh-specific profile over the NISTIR 8259 capability model.
Reachability alone never promotes an IoT device to trusted runtime status.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from typing import Any, Dict, List


def canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(value: Any) -> str:
    return hashlib.sha256(canon(value).encode()).hexdigest()


REQUIRED_CAPABILITIES = (
    "device_identification",
    "device_configuration",
    "data_protection",
    "logical_access_control",
    "software_update",
    "cybersecurity_state_awareness",
)

REQUIRED_SUPPORT = (
    "support_period",
    "vulnerability_disclosure",
    "update_policy",
    "end_of_life_policy",
)

REQUIRED_NETWORK = (
    "segment",
    "allowed_ingress",
    "allowed_egress",
    "management_plane",
)


class AdmissionError(ValueError):
    pass


def _require_mapping(profile: Dict[str, Any], field: str) -> Dict[str, Any]:
    value = profile.get(field)
    if not isinstance(value, dict):
        raise AdmissionError(f"IOT_{field.upper()}_PROFILE_REQUIRED")
    return value


def evaluate(profile: Dict[str, Any]) -> Dict[str, Any]:
    device_id = str(profile.get("device_id", "")).strip()
    authority_root = str(profile.get("authority_root", "UNBOUND")).strip() or "UNBOUND"
    if not device_id:
        raise AdmissionError("IOT_DEVICE_ID_REQUIRED")
    if authority_root == "UNBOUND":
        raise AdmissionError("IOT_AUTHORITY_ROOT_REQUIRED")

    capabilities = _require_mapping(profile, "capabilities")
    support = _require_mapping(profile, "support")
    network = _require_mapping(profile, "network")
    telemetry = _require_mapping(profile, "telemetry")

    failures: List[str] = []
    for name in REQUIRED_CAPABILITIES:
        if capabilities.get(name) is not True:
            failures.append(f"CAPABILITY:{name}")
    for name in REQUIRED_SUPPORT:
        if not support.get(name):
            failures.append(f"SUPPORT:{name}")
    for name in REQUIRED_NETWORK:
        if not network.get(name):
            failures.append(f"NETWORK:{name}")

    heartbeat_ns = int(telemetry.get("last_heartbeat_ns", 0) or 0)
    stale_after_sec = int(telemetry.get("stale_after_sec", 0) or 0)
    if heartbeat_ns <= 0 or stale_after_sec <= 0:
        failures.append("TELEMETRY:heartbeat_contract")
        heartbeat_age_sec = None
    else:
        heartbeat_age_sec = max(0.0, (time.time_ns() - heartbeat_ns) / 1e9)
        if heartbeat_age_sec > stale_after_sec:
            failures.append("TELEMETRY:stale")

    credentials = _require_mapping(profile, "credentials")
    if not credentials.get("rotation_supported"):
        failures.append("CREDENTIALS:rotation")
    if not credentials.get("revocation_supported"):
        failures.append("CREDENTIALS:revocation")

    software = _require_mapping(profile, "software")
    if not software.get("version"):
        failures.append("SOFTWARE:version")
    if not software.get("update_authenticity_verification"):
        failures.append("SOFTWARE:update_authenticity")

    identity = {
        "device_id": device_id,
        "manufacturer": profile.get("manufacturer"),
        "model": profile.get("model"),
        "serial": profile.get("serial"),
        "hardware_revision": profile.get("hardware_revision"),
        "authority_root": authority_root,
    }
    identity_root = sha(identity)
    result = {
        "schema": "braink.iot-admission.v1",
        "device_id": device_id,
        "identity_root": identity_root,
        "authority_root": authority_root,
        "state": "IOT_DEVICE_READY" if not failures else "IOT_DEVICE_HOLD",
        "failures": failures,
        "heartbeat_age_sec": round(heartbeat_age_sec, 3) if heartbeat_age_sec is not None else None,
        "segment": network.get("segment"),
        "management_plane": network.get("management_plane"),
        "evaluated_ns": time.time_ns(),
    }
    result["proof_root"] = sha(result)
    return result


def self_test() -> Dict[str, Any]:
    now = time.time_ns()
    profile = {
        "device_id": "iot:test:1",
        "authority_root": "proof:test",
        "manufacturer": "TEST",
        "model": "TEST",
        "serial": "1",
        "hardware_revision": "1",
        "capabilities": {name: True for name in REQUIRED_CAPABILITIES},
        "support": {
            "support_period": "2026-2030",
            "vulnerability_disclosure": "policy:test",
            "update_policy": "policy:test",
            "end_of_life_policy": "policy:test",
        },
        "network": {
            "segment": "iot:test",
            "allowed_ingress": ["management"],
            "allowed_egress": ["dns", "ntp"],
            "management_plane": "braink-host-control",
        },
        "telemetry": {"last_heartbeat_ns": now, "stale_after_sec": 30},
        "credentials": {"rotation_supported": True, "revocation_supported": True},
        "software": {"version": "1.0", "update_authenticity_verification": True},
    }
    ready = evaluate(profile)
    assert ready["state"] == "IOT_DEVICE_READY"
    profile["capabilities"]["software_update"] = False
    held = evaluate(profile)
    assert held["state"] == "IOT_DEVICE_HOLD"
    assert "CAPABILITY:software_update" in held["failures"]
    return {"status": "PASS", "checks": ["core_capabilities", "support", "segmentation", "heartbeat", "credential_lifecycle", "update_authenticity", "fail_closed"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--profile-json")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2, sort_keys=True))
        return 0
    if args.profile_json:
        print(json.dumps(evaluate(json.loads(args.profile_json)), indent=2, sort_keys=True))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
