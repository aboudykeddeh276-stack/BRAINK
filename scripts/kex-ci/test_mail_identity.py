#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[2]
MODULES = BASE / "modules" / "kex_wbos"
sys.path.insert(0, str(MODULES))

from mail_identity import MailIdentityRegistry, MailboxProvisionRequest, UnboundMailAdapter  # noqa: E402


class VerifiedAdapter:
    def provision(self, request: MailboxProvisionRequest):
        return {"provisioned": True, "provider": "TEST", "mailbox": request.mailbox}

    def readback(self, mailbox: str):
        return {"matched": True, "mailbox": mailbox, "observed": "TEST_PROVIDER"}


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        registry = MailIdentityRegistry(Path(tmp) / "mail-identities.json")
        request = MailboxProvisionRequest(
            authority="A.KEDDEH / KEDDEH_SYSTEMS",
            local_part="system",
            domain="example.invalid",
            purpose="SYSTEM_SERVICE",
            provider_route="provider://test/mail",
        )

        first = registry.register(request)
        assert first["status"] == "REGISTERED"
        assert first["state"] == "REGISTERED_UNPROVISIONED"

        duplicate = registry.register(request)
        assert duplicate["status"] == "ALREADY_REGISTERED"
        assert duplicate["mutated"] is False

        blocked = registry.provision(request, UnboundMailAdapter())
        assert blocked["status"] == "BLOCKED"
        assert blocked["state"] == "REGISTERED_UNPROVISIONED"

        verified = registry.provision(request, VerifiedAdapter())
        assert verified["status"] == "VERIFIED"
        assert verified["state"] == "PROVISIONED_VERIFIED"
        assert registry.resolve(request.mailbox)["state"] == "PROVISIONED_VERIFIED"
        assert verified["receiptHash"]

    print("PASS mail identity/provisioning boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
