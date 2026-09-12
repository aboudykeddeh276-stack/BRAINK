#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from braink_runtime.process_engine import ExecutionContract, ProcessEngine, make_receipt

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
        (("permission denied", "sysctl"), Diagnosis("HOST_PRIVILEGE_REQUIRED", "USER_OPERATOR", "RUN_WITH_REQUIRED_HOST_PRIVILEGE", False, "Host kernel/firewall mutation requires operator privilege.")),
        (("google_projection_unbound",), Diagnosis("GOOGLE_CREDENTIALS_UNBOUND", "USER_OPERATOR", "BIND_GOOGLE_OAUTH_FILES", False, "Google credentials/token are not bound.")),
        (("stripe", "requirements.past_due"), Diagnosis("PROVIDER_ONBOARDING_REQUIRED", "EXTERNAL_PROVIDER_AND_USER", "COMPLETE_PROVIDER_ONBOARDING", False, "Provider requires account-holder/compliance action.")),
        (("runtime failed health readback",), Diagnosis("RUNTIME_HEALTH_FAILED", "BRAINK", "RESTART_AND_RETRY_RUNTIME", True, "Resident runtime failed health readback.")),
        (("stratum_session_failed",), Diagnosis("POOL_SESSION_FAILED", "BRAINK_PROVIDER_ADAPTER", "RETRY_PROVIDER_FAILOVER", True, "Provider session failed.")),
        (("all_viabtc_btc_endpoints_failed",), Diagnosis("POOL_FAILOVER_EXHAUSTED", "EXTERNAL_NETWORK_OR_PROVIDER", "BACKOFF_AND_RETRY", True, "Configured provider endpoints failed.")),
        (("address already in use",), Diagnosis("PORT_IN_USE", "HOST_RUNTIME", "REUSE_OR_REPORT_CONFLICT", False, "Unknown process already owns the port.")),
        (("no supported host runtime found",), Diagnosis("HOST_RUNTIME_MISSING", "USER_OPERATOR", "INSTALL_DOCKER_OR_PYTHON", False, "No supported host runtime is available.")),
        (("modulenotfounderror",), Diagnosis("DEPENDENCY_IMPORT_FAILED", "BRAINK", "REINSTALL_PACKAGE_AND_RETRY", True, "Resident dependency/import failed.")),
        (("connection refused",), Diagnosis("DEPENDENCY_CONNECTION_REFUSED", "BRAINK_OR_EXTERNAL_SERVICE", "RETRY_AFTER_RESTART", True, "Dependency refused connection.")),
    ]
    for needles, diagnosis in rules:
        if all(n in text for n in needles):
            return diagnosis
    if returncode == 0:
        return Diagnosis("DEPLOYMENT_OK", "NONE", "NONE", False, "Deployment completed successfully.")
    return Diagnosis("UNCLASSIFIED_FAILURE", "BRAINK_REVIEW", "PRESERVE_STATE_AND_ESCALATE", False, "Failure is outside the authorised repair table.")


def _deploy_capability(contract: ExecutionContract):
    started = time.time_ns()
    proc = subprocess.run(
        ["bash", str(DEPLOY)],
        cwd=ROOT,
        env=os.environ.copy(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    diagnosis = classify(proc.stdout, proc.returncode)
    return make_receipt(
        contract,
        status="PASS" if proc.returncode == 0 else ("BLOCKED" if not diagnosis.auto_repairable else "FAIL"),
        started_ns=started,
        observed={
            "returncode": proc.returncode,
            "diagnosis": asdict(diagnosis),
            "output_tail": proc.stdout[-8000:],
        },
    )


def safe_repair(diagnosis: Diagnosis) -> dict[str, Any]:
    if not diagnosis.auto_repairable:
        return {"attempted": False, "status": "NOT_AUTHORISED", "action": diagnosis.action}
    if diagnosis.code == "DEPENDENCY_IMPORT_FAILED":
        python = shutil.which("python3") or shutil.which("python")
        if not python:
            return {"attempted": False, "status": "NO_PYTHON", "action": diagnosis.action}
        proc = subprocess.run([python, "-m", "pip", "install", "-e", "."], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return {"attempted": True, "status": "PASS" if proc.returncode == 0 else "FAILED", "action": diagnosis.action, "returncode": proc.returncode, "output_tail": proc.stdout[-4000:]}
    return {"attempted": True, "status": "RETRY_SCHEDULED", "action": diagnosis.action}


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    ledger_path = DATA / "operator_agent_ledger.jsonl"
    final_path = DATA / "operator_agent_receipt.json"
    authority = os.getenv("BRAINK_OPERATOR_AUTHORITY", "USER_OPERATOR")
    engine = ProcessEngine()
    engine.register_capability("RUN_OPERATOR_DEPLOYMENT", _deploy_capability)
    attempts: list[dict[str, Any]] = []

    for attempt_no in range(1, MAX_ATTEMPTS + 1):
        contract = ExecutionContract(
            contract_id=f"deploy-{uuid.uuid4().hex}",
            state="OPERATOR_DEPLOYMENT",
            authority=authority,
            target="BRAINK_OPERATOR_HOST",
            capability="RUN_OPERATOR_DEPLOYMENT",
            payload={"attempt": attempt_no},
        )
        transition = engine.execute(contract)
        observed = transition["receipt"]["observed"]
        diagnosis = Diagnosis(**observed["diagnosis"])
        repair = safe_repair(diagnosis)
        record = {"attempt": attempt_no, "transition": transition, "repair": repair}
        attempts.append(record)
        with ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

        if transition["receipt"]["status"] == "PASS":
            final = {"schema": "braink.operator.agent.receipt.v2", "status": "QUALIFIED_AFTER_AGENTIC_EXECUTION", "authority": authority, "attempts": attempts, "human_action_required": False}
            final_path.write_text(json.dumps(final, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps(final, indent=2, sort_keys=True))
            return 0

        if transition["receipt"]["status"] == "BLOCKED":
            final = {"schema": "braink.operator.agent.receipt.v2", "status": "USER_ACTION_REQUIRED", "authority": authority, "attempts": attempts, "human_action_required": True, "intervention": {"code": diagnosis.code, "owner": diagnosis.owner, "required_action": diagnosis.action, "detail": diagnosis.detail}}
            final_path.write_text(json.dumps(final, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps(final, indent=2, sort_keys=True))
            return 1

        if attempt_no < MAX_ATTEMPTS:
            time.sleep(BACKOFF_S * attempt_no)

    final = {"schema": "braink.operator.agent.receipt.v2", "status": "AUTO_REPAIR_EXHAUSTED", "authority": authority, "attempts": attempts, "human_action_required": True, "intervention": {"code": attempts[-1]["transition"]["receipt"]["observed"]["diagnosis"]["code"], "required_action": "REVIEW_AFTER_BOUNDED_AUTO_REPAIR"}}
    final_path.write_text(json.dumps(final, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(final, indent=2, sort_keys=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
