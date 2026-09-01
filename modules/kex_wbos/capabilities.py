#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

from hardening import canonical_json_bytes


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def mint_capability(
    secret: str,
    *,
    actions: list[str],
    target_prefixes: list[str],
    ttl_seconds: int,
    delegated_by: str,
) -> str:
    if not secret:
        raise ValueError("capability secret required")
    if ttl_seconds <= 0 or ttl_seconds > 86400:
        raise ValueError("ttl_seconds must be in 1..86400")
    normalized_actions = sorted({str(action).upper() for action in actions if str(action).strip()})
    normalized_prefixes = sorted({str(prefix) for prefix in target_prefixes if str(prefix)})
    if not normalized_actions:
        raise ValueError("at least one capability action is required")
    if not normalized_prefixes:
        raise ValueError("at least one explicit target prefix is required; use '*' only when deliberately granting wildcard scope")
    payload = {
        "capabilityId": f"KEXCAP-{uuid.uuid4().hex[:16]}",
        "actions": normalized_actions,
        "targetPrefixes": normalized_prefixes,
        "issuedAt": int(time.time()),
        "expiresAt": int(time.time()) + ttl_seconds,
        "delegatedBy": delegated_by,
    }
    body = canonical_json_bytes(payload)
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return f"{_b64(body)}.{_b64(signature)}"


def verify_capability(
    secret: str,
    token: str,
    *,
    action: str,
    target: str,
    now: int | None = None,
) -> tuple[bool, dict[str, Any]]:
    if not secret or not token or "." not in token:
        return False, {"error": "capability_missing_or_malformed"}
    try:
        body_part, sig_part = token.split(".", 1)
        body = _unb64(body_part)
        supplied = _unb64(sig_part)
        expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied, expected):
            return False, {"error": "capability_signature_invalid"}
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:
        return False, {"error": "capability_decode_failed", "exception": type(exc).__name__}

    timestamp = int(time.time()) if now is None else int(now)
    if timestamp > int(payload.get("expiresAt", 0)):
        return False, {"error": "capability_expired", "capabilityId": payload.get("capabilityId")}
    allowed_actions = {str(item).upper() for item in payload.get("actions", [])}
    if action.upper() not in allowed_actions and "*" not in allowed_actions:
        return False, {"error": "capability_action_denied", "capabilityId": payload.get("capabilityId")}
    prefixes = [str(item) for item in payload.get("targetPrefixes", []) if str(item)]
    if not prefixes:
        return False, {"error": "capability_target_scope_missing", "capabilityId": payload.get("capabilityId")}
    if "*" not in prefixes and not any(target.startswith(prefix) for prefix in prefixes):
        return False, {"error": "capability_target_denied", "capabilityId": payload.get("capabilityId")}
    return True, payload
