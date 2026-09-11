from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any


class EstateBindings:
    """Bindings from the generic SaaS node to resident Keddeh/BRAINK rails.

    These bindings do not promote source files into observed runtime state. Host
    actuation remains fail-closed behind the existing HOST_READY and external
    observation gates enforced by deploy/activate_keddeh_fabric.py.
    """

    def __init__(self, repo_root: str | None = None):
        self.repo_root = Path(repo_root or os.getenv("BRAINK_REPO_ROOT", ".")).resolve()
        self.host_activation = self.repo_root / "runtime/host_control/braink_host_activation.py"
        self.host_fabric = self.repo_root / "runtime/host_control/braink_host_fabric.py"
        self.fabric_actuator = self.repo_root / "deploy/activate_keddeh_fabric.py"
        self.runner_bootstrap = self.repo_root / "deploy/bootstrap_tl2_runner.sh"
        self.systemd_dir = self.repo_root / "deploy/systemd"
        self.public_gateway = self.repo_root / "runtime/public_gateway.py"
        self.domain_broadcaster = self.repo_root / "deploy/broadcast_domains.py"
        self.stripe_socket = Path(os.getenv("BRAINK_STRIPE_SOCKET", "/tmp/braink-stripe.sock"))
        self.oauth_socket = Path(os.getenv("BRAINK_OAUTH_SOCKET", "/tmp/braink-oauth.sock"))

    @staticmethod
    def _file(path: Path) -> dict[str, Any]:
        return {"path": str(path), "source_present": path.is_file()}

    def status(self) -> dict[str, Any]:
        return {
            "host_actuation": {
                "state": "BOUND_SOURCE",
                "host_activation": self._file(self.host_activation),
                "host_fabric": self._file(self.host_fabric),
                "fabric_actuator": self._file(self.fabric_actuator),
                "runner_bootstrap": self._file(self.runner_bootstrap),
                "systemd_present": self.systemd_dir.is_dir(),
                "runtime_gate": "HOST_READY + ONLINE + external carrier proof",
            },
            "payments": {
                "state": "BOUND_RAIL",
                "transport": "unix-socket",
                "socket": str(self.stripe_socket),
                "socket_live": self.stripe_socket.exists(),
                "public_checkout_route": "/payments/checkout",
                "public_webhook_route": "/payments/stripe/webhook",
            },
            "identity": {
                "state": "BOUND_RAIL",
                "transport": "unix-socket",
                "socket": str(self.oauth_socket),
                "socket_live": self.oauth_socket.exists(),
                "public_start_route": "/auth/google/start",
                "public_callback_route": "/auth/google/callback",
            },
            "public_ingress": {
                "state": "BOUND_SOURCE",
                "gateway": self._file(self.public_gateway),
                "domain_broadcaster": self._file(self.domain_broadcaster),
                "promotion_rule": "public projection cannot promote resident runtime state",
            },
            "metering": {
                "state": "BOUND_OBSERVATION_BASE",
                "source": "runtime/public_gateway.py:/dashboards/summary",
                "tenant_accounting": "SAAS_USAGE_LEDGER_REQUIRED",
            },
        }

    def provisioning_plan(self, *, tenant_id: str, system_id: str, service_id: str, plan: str) -> dict[str, Any]:
        return {
            "tenant_id": tenant_id,
            "system_id": system_id,
            "service_id": service_id,
            "plan": plan,
            "stages": [
                "RESOLVE_HOST_CONTROL",
                "ISSUE_HOST_CHALLENGE",
                "EXTERNAL_CARRIER_PROBE",
                "VERIFY_HOST_RESPONSE",
                "ADMIT_HOSTS",
                "SCHEDULE_CAPABILITY",
                "DISPATCH_TRIGGER",
                "MUTATE_STATE",
                "READBACK",
                "WRITEBACK",
                "PROOF_COMMIT",
                "PROJECT_PUBLIC_SURFACE",
            ],
            "actuator": str(self.fabric_actuator),
            "public_gateway": str(self.public_gateway),
            "payment_rail": str(self.stripe_socket),
            "domain_broadcaster": str(self.domain_broadcaster),
            "execution_state": "READY_TO_ATTEMPT_FAIL_CLOSED" if self.fabric_actuator.is_file() else "BLOCKED_ACTUATOR_MISSING",
        }

    def actuate_fabric(self) -> dict[str, Any]:
        if os.getenv("BRAINK_SAAS_ALLOW_HOST_ACTUATION", "0") != "1":
            return {"status": "BLOCKED", "reason": "BRAINK_SAAS_ALLOW_HOST_ACTUATION_NOT_ENABLED"}
        if not self.fabric_actuator.is_file():
            return {"status": "BLOCKED", "reason": "FABRIC_ACTUATOR_MISSING", "path": str(self.fabric_actuator)}
        proc = subprocess.run(
            [sys.executable, str(self.fabric_actuator), "--activate"],
            cwd=str(self.repo_root), text=True, capture_output=True,
        )
        payload: dict[str, Any] = {
            "status": "PASS" if proc.returncode == 0 else "BLOCKED",
            "returncode": proc.returncode,
            "stdout": proc.stdout[-12000:],
            "stderr": proc.stderr[-12000:],
        }
        if proc.returncode == 0:
            try:
                payload["receipt"] = json.loads(proc.stdout)
            except Exception:
                pass
        return payload
