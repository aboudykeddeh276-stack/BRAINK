#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv("BRAINK_DATA_DIR", str(ROOT / "data")))
DEPLOY = ROOT / "operator_deploy.sh"
MAX_ATTEMPTS = max(1, min(int(os.getenv("BRAINK_AGENT_MAX_ATTEMPTS", "3")), 10))
BACKOFF_S = max(0.0, min(float(os.getenv("BRAINK_AGENT_BACKOFF_S", "2")), 60.0))


@dataclass(frozen=True)
class Diagnosis:
    code: str
    owner: str
    action: str
    auto_repairable: bool
    detail: str


def classify(output: str, returncode: int) -> Diagnosis:
    text = output.lower()
    rules: list[tuple[tuple[str, ...], Diagnosis]] = [
        (("permission denied", "sysctl",), Diagnosis(
            "HOST_PRIVILEGE_REQUIRED", "USER_OPERATOR", "RUN_WITH_REQUIRED_HOST_PRIVILEGE", False,
            "Host kernel/firewall mutation requires operator privilege; agent will not self-escalate privileges.",
        )),
        (("google_projection_unbound",), Diagnosis(
            "GOOGLE_CREDENTIALS_UNBOUND", "USER_OPERATOR", "BIND_GOOGLE_OAUTH_FILES", False,
            "Google projection credentials/token are not bound; agent will not invent credentials.",
        )),
        (("stripe", "requirements.past_due"), Diagnosis(
            "PROVIDER_ONBOARDING_REQUIRED", "EXTERNAL_PROVIDER_AND_USER", "COMPLETE_PROVIDER_ONBOARDING", False,
            "Provider requires account-holder/compliance data; agent cannot fabricate identity or consent.",
        )),
        (("runtime failed health readback",), Diagnosis(
            "RUNTIME_HEALTH_FAILED", "BRAINK", "RESTART_AND_RETRY_RUNTIME", True,
            "Resident runtime failed health readback; safe restart/retry is allowed.",
        )),
        (("stratum_session_failed",), Diagnosis(
            "POOL_SESSION_FAILED", "BRAINK_PROVIDER_ADAPTER", "RETRY_PROVIDER_FAILOVER", True,
            "Provider session failed; retry through configured deterministic failover path.",
        )),
        (("all_viabtc_btc_endpoints_failed",), Diagnosis(
            "POOL_FAILOVER_EXHAUSTED", "EXTERNAL_NETWORK_OR_PROVIDER", "BACKOFF_AND_RETRY", True,
            "All configured provider endpoints failed; bounded backoff/retry is safe.",
        )),
        (("address already in use",), Diagnosis(
            "PORT_IN_USE", "HOST_RUNTIME", "REUSE_OR_REPORT_CONFLICT", False,
            "A port is already owned. Agent refuses to kill an unknown process automatically.",
        )),
        (("no supported host runtime found",), Diagnosis(
            "HOST_RUNTIME_MISSING", "USER_OPERATOR", "INSTALL_DOCKER_OR_PYTHON", False,
            "Neither supported Docker Compose nor Python runtime is available.",
        )),
        (("modulenotfounderror",), Diagnosis(
            "DEPENDENCY_IMPORT_FAILED", "BRAINK", "REINSTALL_PACKAGE_AND_RETRY", True,
            "Python dependency/import failure can be repaired by reinstalling the resident package.",
        )),
        (("connection refused",), Diagnosis(
            "DEPENDENCY_CONNECTION_REFUSED", "BRAINK_OR_EXTERNAL_SERVICE", "RETRY_AFTER_RESTART", True,
            "Dependency connection refused; bounded restart/retry is safe.",
        )),
    ]
    for needles, diagnosis in rules:
        if all(n in text for n in needles):
            return diagnosis
    if returncode == 0:
        return Diagnosis("DEPLOYMENT_OK", "NONE", "NONE", False, "Deployment completed successfully.")
    return Diagnosis(
        "UNCLASSIFIED_FAILURE", "BRAINK_REVIEW", "PRESERVE_STATE_AND_ESCALATE", False,
        "Failure is not in the authorised repair table; preserve state and request operator review.",
    )


def run_deploy() -> tuple[int, str]:
    env = os.environ.copy()
    proc = subprocess.run(
        ["bash", str(DEPLOY)],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc.returncode, proc.stdout


def safe_repair(diagnosis: Diagnosis) -> dict[str, Any]:
    if not diagnosis.auto_repairable:
        return {"attempted": False, "status": "NOT_AUTHORISED", "action": diagnosis.action}

    if diagnosis.code == "DEPENDENCY_IMPORT_FAILED":
        python = shutil.which("python3") or shutil.which("python")
        if not python:
            return {"attempted": False, "status": "NO_PYTHON", "action": diagnosis.action}
        proc = subprocess.run(
            [python, "-m", "pip", "install", "-e", "."],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return {
            "attempted": True,
            "status": "PASS" if proc.returncode == 0 else "FAILED",
            "action": diagnosis.action,
            "returncode": proc.returncode,
            "output_tail": proc.stdout[-4000:],
        }

    # Runtime/provider/network transient repairs are intentionally non-destructive:
    # the deploy path already rebuilds/restarts the BRAINK runtime and provider
    # failover is resident in the Stratum carrier. Re-run is the repair action.
    return {"attempted": True, "status": "RETRY_SCHEDULED", "action": diagnosis.action}


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    ledger_path = DATA / "operator_agent_ledger.jsonl"
    final_path = DATA / "operator_agent_receipt.json"
    attempts: list[dict[str, Any]] = []

    for attempt_no in range(1, MAX_ATTEMPTS + 1):
        started_ns = time.time_ns()
        rc, output = run_deploy()
        diagnosis = classify(output, rc)
        repair = safe_repair(diagnosis)
        record = {
            "attempt": attempt_no,
            "started_ns": started_ns,
            "completed_ns": time.time_ns(),
            "returncode": rc,
            "diagnosis": asdict(diagnosis),
            "repair": repair,
            "output_tail": output[-8000:],
        }
        attempts.append(record)
        with ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

        if rc == 0:
            receipt = {
                "schema": "braink.operator.agent.receipt.v1",
                "status": "QUALIFIED_AFTER_AGENTIC_EXECUTION",
                "authority": os.getenv("BRAINK_OPERATOR_AUTHORITY", "USER_OPERATOR"),
                "attempts": attempts,
                "human_action_required": False,
            }
            final_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps(receipt, indent=2, sort_keys=True))
            return 0

        if not diagnosis.auto_repairable:
            receipt = {
                "schema": "braink.operator.agent.receipt.v1",
                "status": "USER_ACTION_REQUIRED",
                "authority": os.getenv("BRAINK_OPERATOR_AUTHORITY", "USER_OPERATOR"),
                "attempts": attempts,
                "human_action_required": True,
                "intervention": {
                    "code": diagnosis.code,
                    "owner": diagnosis.owner,
                    "required_action": diagnosis.action,
                    "detail": diagnosis.detail,
                },
            }
            final_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps(receipt, indent=2, sort_keys=True))
            return rc or 1

        if attempt_no < MAX_ATTEMPTS:
            time.sleep(BACKOFF_S * attempt_no)

    receipt = {
        "schema": "braink.operator.agent.receipt.v1",
        "status": "AUTO_REPAIR_EXHAUSTED",
        "authority": os.getenv("BRAINK_OPERATOR_AUTHORITY", "USER_OPERATOR"),
        "attempts": attempts,
        "human_action_required": True,
        "intervention": {
            "code": attempts[-1]["diagnosis"]["code"],
            "owner": attempts[-1]["diagnosis"]["owner"],
            "required_action": "REVIEW_AFTER_BOUNDED_AUTO_REPAIR",
        },
    }
    final_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
