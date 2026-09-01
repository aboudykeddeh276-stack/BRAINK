#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Protocol

from hardening import atomic_write_text, canonical_json_bytes

_EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$", re.ASCII)


class MailProvisioningAdapter(Protocol):
    """Provider boundary for mailbox/account creation.

    An adapter may target Google Workspace, a sovereign SMTP/IMAP server, or a
    future Keddeh mail service. The registry remains provider-neutral and does
    not fabricate external provisioning success.
    """

    def provision(self, request: "MailboxProvisionRequest") -> dict[str, Any]: ...
    def readback(self, mailbox: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class MailboxProvisionRequest:
    authority: str
    local_part: str
    domain: str
    display_name: str = ""
    purpose: str = "SYSTEM_SERVICE"
    provider_route: str = "UNBOUND"
    require_readback: bool = True

    @property
    def mailbox(self) -> str:
        return f"{self.local_part}@{self.domain}".lower()

    def validate(self) -> None:
        if not self.authority.strip():
            raise ValueError("authority_required")
        if not _EMAIL_RE.fullmatch(self.mailbox):
            raise ValueError("invalid_mailbox_identity")
        if self.provider_route == "":
            raise ValueError("provider_route_required")


@dataclass(frozen=True, slots=True)
class MailIdentity:
    mailbox: str
    authority: str
    domain: str
    local_part: str
    display_name: str
    purpose: str
    provider_route: str
    state: str
    created_at: float
    identity_hash: str


class MailIdentityRegistry:
    """Resident, proof-oriented mail identity registry.

    Registry state records Keddeh Systems' mailbox identity and intended
    provider binding. It deliberately separates registration from external
    provider provisioning so `REGISTERED` cannot be mistaken for a mailbox that
    has actually been created at Google Workspace or another provider.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.identities: dict[str, MailIdentity] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        for item in raw.get("identities", []):
            ident = MailIdentity(**item)
            self.identities[ident.mailbox] = ident

    def _persist(self) -> None:
        payload = {
            "schema": "kex.mail-identity-registry.v1",
            "identities": [asdict(self.identities[key]) for key in sorted(self.identities)],
        }
        atomic_write_text(self.path, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def register(self, request: MailboxProvisionRequest) -> dict[str, Any]:
        request.validate()
        material = {
            "authority": request.authority,
            "mailbox": request.mailbox,
            "purpose": request.purpose,
            "providerRoute": request.provider_route,
        }
        identity_hash = hashlib.sha256(canonical_json_bytes(material)).hexdigest()
        existing = self.identities.get(request.mailbox)
        if existing:
            return {
                "status": "ALREADY_REGISTERED",
                "mutated": False,
                "mailbox": request.mailbox,
                "identityHash": existing.identity_hash,
                "state": existing.state,
            }
        ident = MailIdentity(
            mailbox=request.mailbox,
            authority=request.authority,
            domain=request.domain.lower(),
            local_part=request.local_part.lower(),
            display_name=request.display_name,
            purpose=request.purpose,
            provider_route=request.provider_route,
            state="REGISTERED_UNPROVISIONED",
            created_at=time.time(),
            identity_hash=identity_hash,
        )
        self.identities[ident.mailbox] = ident
        self._persist()
        return {
            "status": "REGISTERED",
            "mutated": True,
            "mailbox": ident.mailbox,
            "identityHash": ident.identity_hash,
            "state": ident.state,
            "claimBoundary": "Identity registration is resident Keddeh Systems state. It does not prove the external mailbox exists.",
        }

    def provision(self, request: MailboxProvisionRequest, adapter: MailProvisioningAdapter) -> dict[str, Any]:
        request.validate()
        registration = self.register(request)
        provider_receipt = adapter.provision(request)
        provisioned = bool(provider_receipt.get("provisioned"))
        readback = adapter.readback(request.mailbox) if provisioned and request.require_readback else None
        verified = provisioned and (not request.require_readback or bool((readback or {}).get("matched")))

        old = self.identities[request.mailbox]
        state = "PROVISIONED_VERIFIED" if verified else ("PROVISIONED_UNVERIFIED" if provisioned else "REGISTERED_UNPROVISIONED")
        self.identities[request.mailbox] = MailIdentity(
            mailbox=old.mailbox,
            authority=old.authority,
            domain=old.domain,
            local_part=old.local_part,
            display_name=old.display_name,
            purpose=old.purpose,
            provider_route=old.provider_route,
            state=state,
            created_at=old.created_at,
            identity_hash=old.identity_hash,
        )
        self._persist()
        receipt = {
            "status": "VERIFIED" if verified else ("PARTIAL" if provisioned else "BLOCKED"),
            "mailbox": request.mailbox,
            "registration": registration,
            "providerReceipt": provider_receipt,
            "readback": readback,
            "state": state,
            "timestamp": time.time(),
        }
        receipt["receiptHash"] = hashlib.sha256(canonical_json_bytes(receipt)).hexdigest()
        return receipt

    def resolve(self, mailbox: str) -> dict[str, Any]:
        ident = self.identities.get(mailbox.lower())
        if not ident:
            return {"found": False, "mailbox": mailbox.lower()}
        return {"found": True, **asdict(ident)}


class UnboundMailAdapter:
    """Explicit no-actuator adapter used until a concrete provider is bound."""

    def provision(self, request: MailboxProvisionRequest) -> dict[str, Any]:
        return {
            "provisioned": False,
            "status": "EXTERNAL_ADAPTER_UNBOUND",
            "providerRoute": request.provider_route,
            "mailbox": request.mailbox,
        }

    def readback(self, mailbox: str) -> dict[str, Any]:
        return {"matched": False, "status": "NO_EXTERNAL_READBACK", "mailbox": mailbox}
