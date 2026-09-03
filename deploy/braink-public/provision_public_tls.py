#!/usr/bin/env python3
from __future__ import annotations

"""Provision public TLS for BRAINK public domains through explicit authority adapters.

This executable closes the control path only when all three external actuators exist:
1. public DNS/ACME challenge auth hook,
2. public DNS/ACME challenge cleanup hook,
3. resident SERVER_ROOT TLS install hook.

A certificate is not considered deployed until the install hook succeeds and an
external client verifies system trust plus hostname against the public endpoint.
"""

from pathlib import Path
import json
import os
import subprocess
import time

from enterprise.public_ca_adapter import PublicCAAdapter
from enterprise.tls_authority_runtime import ResidentTLSAuthority

DOMAINS = tuple(
    d.strip()
    for d in os.environ.get(
        "KEDDEH_PUBLIC_TLS_DOMAINS",
        "braink.com.au,braink-intelligence.com.au,braink-learning.com.au",
    ).split(",")
    if d.strip()
)

STATE_ROOT = Path(os.environ.get("KEDDEH_TLS_STATE_ROOT", "build/public-tls/resident"))
PUBLIC_STATE_ROOT = Path(os.environ.get("KEDDEH_PUBLIC_CA_STATE_ROOT", "build/public-tls/public-ca"))
RECEIPT = Path(os.environ.get("KEDDEH_PUBLIC_TLS_RECEIPT", "deploy/braink-public/BRAINK_PUBLIC_TLS_RECEIPT.json"))


def _required_executable(env_name: str) -> Path:
    value = os.environ.get(env_name, "").strip()
    if not value:
        raise RuntimeError(f"{env_name}_UNBOUND")
    path = Path(value).expanduser().resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise RuntimeError(f"{env_name}_NOT_EXECUTABLE:{path}")
    return path


def _install(hook: Path, domain: str, material) -> dict:
    env = os.environ.copy()
    env.update(
        {
            "KEDDEH_TLS_DOMAIN": domain,
            "KEDDEH_TLS_REQUEST_ID": material.request_id,
            "KEDDEH_TLS_CERTIFICATE": material.certificate_path,
            "KEDDEH_TLS_CHAIN": material.chain_path,
            "KEDDEH_TLS_FULLCHAIN": material.fullchain_path,
            "KEDDEH_TLS_PRIVATE_KEY": material.private_key_path,
        }
    )
    proc = subprocess.run([str(hook)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = {
        "returncode": proc.returncode,
        "stdout": proc.stdout.decode("utf-8", "replace")[-8000:],
        "stderr": proc.stderr.decode("utf-8", "replace")[-8000:],
    }
    if proc.returncode != 0:
        raise RuntimeError("SERVER_TLS_INSTALL_FAILED:" + result["stderr"])
    return result


def main() -> int:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema": "kex.braink.public-tls-deployment.v1",
        "started_ns": time.time_ns(),
        "domains": {},
        "overall": False,
        "authority_order": [
            "TLS_ROOT resident authority",
            "PUBLIC_CA_ADAPTER",
            "domain-control challenge actuator",
            "public CA",
            "SERVER_ROOT TLS install actuator",
            "external system-trust + hostname readback",
        ],
    }
    try:
        auth_hook = _required_executable("KEDDEH_PUBLIC_CA_AUTH_HOOK")
        cleanup_hook = _required_executable("KEDDEH_PUBLIC_CA_CLEANUP_HOOK")
        install_hook = _required_executable("KEDDEH_SERVER_TLS_INSTALL_HOOK")
        tls = ResidentTLSAuthority(STATE_ROOT)
        adapter = PublicCAAdapter(
            tls,
            PUBLIC_STATE_ROOT,
            certbot_binary=os.environ.get("KEDDEH_ACME_CLIENT", "certbot"),
            challenge_auth_hook=auth_hook,
            challenge_cleanup_hook=cleanup_hook,
            directory_url=os.environ.get("KEDDEH_ACME_DIRECTORY_URL") or None,
            email=os.environ.get("KEDDEH_ACME_EMAIL") or None,
        )
        for domain in DOMAINS:
            item = {"domain": domain, "state": "PREPARING"}
            receipt["domains"][domain] = item
            request = adapter.prepare_request(domain, dns_names=[domain])
            item["request"] = request.as_dict()
            item["state"] = "CSR_PREPARED"
            material = adapter.issue(request)
            item["certificate"] = material.as_dict()
            item["state"] = "PUBLIC_CERTIFICATE_VERIFIED"
            item["server_install"] = _install(install_hook, domain, material)
            item["state"] = "SERVER_BOUND"
            item["external_readback"] = adapter.external_tls_readback(domain)
            item["state"] = "EXTERNALLY_VERIFIED"
        receipt["overall"] = all(v.get("state") == "EXTERNALLY_VERIFIED" for v in receipt["domains"].values())
        receipt["status"] = "PUBLIC_TLS_DEPLOYMENT_VERIFIED" if receipt["overall"] else "PUBLIC_TLS_DEPLOYMENT_INCOMPLETE"
        receipt["completed_ns"] = time.time_ns()
        RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0 if receipt["overall"] else 2
    except Exception as exc:
        receipt["status"] = "PUBLIC_TLS_DEPLOYMENT_BLOCKED"
        receipt["failure"] = str(exc)
        receipt["completed_ns"] = time.time_ns()
        RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
