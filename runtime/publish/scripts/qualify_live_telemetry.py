#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import platform
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.getenv("BRAINK_LOCAL_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.getenv("BRAINK_AUTH_TOKEN", "")
OPERATOR = os.getenv("BRAINK_OPERATOR_AUTHORITY", "USER_OPERATOR").strip()
OUT = Path(os.getenv("BRAINK_DATA_DIR", "./data")) / "live_telemetry_qualification.json"


def request_json(method: str, path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "X-BRAINK-Token": TOKEN},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP_{exc.code}:{path}:{body}") from exc


def host_identity() -> dict:
    return {
        "authority": OPERATOR,
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "execution_model": "OPERATOR_OWNED_HOST",
    }


def main() -> int:
    if not OPERATOR:
        raise SystemExit("BRAINK_OPERATOR_AUTHORITY_REQUIRED")

    result: dict = {
        "schema": "braink.kex.live-telemetry-qualification.v2",
        "authority": OPERATOR,
        "host": host_identity(),
        "runtime": None,
        "stratum": None,
        "sheet_projection": None,
        "status": "STARTING",
    }

    try:
        result["runtime"] = request_json("GET", "/api/health")
        if result["runtime"].get("status") != "ok":
            raise RuntimeError("BRAINK_RUNTIME_HEALTH_FAILED")

        result["stratum"] = request_json(
            "POST",
            "/telemetry/stratum-probe",
            {"endpoint_profile": "BTC_AUTO", "observe_s": 3.0, "timeout_s": 4.0},
        )
        if result["stratum"].get("status") != "SESSION_ESTABLISHED":
            raise RuntimeError("STRATUM_SESSION_NOT_ESTABLISHED")

        try:
            result["sheet_projection"] = request_json("POST", "/telemetry/google-project")
        except Exception as exc:
            result["sheet_projection"] = {"status": "NOT_PROJECTED", "reason": str(exc)}

        result["status"] = "OPERATOR_HOST_LIVE_CARRIER_BOUND"
        result["claim_boundary"] = {
            "host_execution": "OBSERVED_ON_OPERATOR_HOST",
            "stratum_transport": "OBSERVED",
            "share_submission": "NOT_PERFORMED",
            "pool_share_acceptance": "NOT_PROVEN_BY_PROBE",
            "bitcoin_block_discovery": False,
            "sheet_projection": result["sheet_projection"].get("status", "UNKNOWN"),
        }
        code = 0
    except Exception as exc:
        result["status"] = "OPERATOR_HOST_QUALIFICATION_BLOCKED"
        result["error"] = f"{type(exc).__name__}:{exc}"
        code = 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
