from __future__ import annotations
from typing import Any, Mapping
import hashlib, json, time

from enterprise.foundry_closure_r23 import DurableStore, TransitionReceipt


def _token_root(token: str) -> str:
    if not token:
        raise ValueError("SESSION_TOKEN_REQUIRED")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class CustomerAccessControl:
    """R24 access membrane over the resident R23 customer-file lifecycle.

    OAuth remains owned by the existing OAuth rail. This component only binds the
    returned opaque session to durable customer identity/scopes, stores no bearer
    token plaintext, and emits R23-compatible transition receipts for every access
    decision. It does not claim public identity-provider execution by itself.
    """

    DEFAULT_SCOPES = ("customer_file:read",)

    def __init__(self, store: DurableStore):
        self.store = store
        missing = [k for k in ("customer_sessions", "customer_access_audit") if k not in self.store.state]
        if missing:
            def init(s):
                s.setdefault("customer_sessions", {})
                s.setdefault("customer_access_audit", [])
                return {"initialized": missing}
            self.store.commit(init)

    def bind_oauth_session(
        self,
        session_token: str,
        profile: Mapping[str, Any],
        *,
        customer_id: str | None = None,
        scopes: list[str] | tuple[str, ...] | None = None,
        ttl_ns: int = 3_600_000_000_000,
        now_ns: int | None = None,
    ) -> TransitionReceipt:
        now = int(now_ns if now_ns is not None else time.time_ns())
        sub = str(profile.get("sub") or "").strip()
        email = str(profile.get("email") or "").strip().lower()
        if not sub:
            raise ValueError("OAUTH_SUB_REQUIRED")
        if ttl_ns <= 0:
            raise ValueError("SESSION_TTL_INVALID")
        sid = _token_root(session_token)
        cid = customer_id or f"customer://google/{sub}"
        normalized_scopes = sorted(set(scopes or self.DEFAULT_SCOPES))
        record = {
            "session_root": sid,
            "customer_id": cid,
            "subject": sub,
            "email": email,
            "scopes": normalized_scopes,
            "issued_ns": now,
            "expires_ns": now + int(ttl_ns),
            "status": "ACTIVE",
            "provider": "GOOGLE_OAUTH_RAIL",
        }
        self.store.commit(lambda s: s["customer_sessions"].__setitem__(sid, record) or record)
        return self.store.record(TransitionReceipt(
            "CUSTOMER_ACCESS", "SESSION_BIND", cid, "EXECUTED",
            {k: v for k, v in record.items() if k != "email"}, now,
        ))

    def revoke(self, session_token: str, reason: str = "revoked", now_ns: int | None = None) -> TransitionReceipt:
        now = int(now_ns if now_ns is not None else time.time_ns())
        sid = _token_root(session_token)
        current = json.loads(json.dumps(self.store.state["customer_sessions"].get(sid) or {}))
        if not current:
            raise KeyError("SESSION_NOT_FOUND")
        current["status"] = "REVOKED"
        current["revoked_ns"] = now
        current["revoke_reason"] = reason
        self.store.commit(lambda s: s["customer_sessions"].__setitem__(sid, current) or current)
        return self.store.record(TransitionReceipt(
            "CUSTOMER_ACCESS", "SESSION_REVOKE", current["customer_id"], "EXECUTED",
            {"session_root": sid, "reason": reason}, now,
        ))

    def authorize(
        self,
        session_token: str,
        file_id: str,
        operation: str = "customer_file:read",
        *,
        now_ns: int | None = None,
    ) -> TransitionReceipt:
        now = int(now_ns if now_ns is not None else time.time_ns())
        sid = _token_root(session_token)
        session = self.store.state["customer_sessions"].get(sid)
        file_obj = self.store.state["customer_files"].get(file_id)
        status = "AUTHORIZED"
        reason = "AUTHORIZED_OWNER_SCOPE_CONSENT"

        if not session:
            status, reason = "REJECTED", "SESSION_NOT_FOUND"
        elif session.get("status") != "ACTIVE":
            status, reason = "REJECTED", "SESSION_NOT_ACTIVE"
        elif int(session.get("expires_ns", 0)) <= now:
            status, reason = "REJECTED", "SESSION_EXPIRED"
        elif not file_obj:
            status, reason = "REJECTED", "CUSTOMER_FILE_NOT_FOUND"
        elif operation not in set(session.get("scopes") or []):
            status, reason = "REJECTED", "SCOPE_DENIED"
        elif file_obj.get("customer_id") != session.get("customer_id") and "customer_file:admin" not in set(session.get("scopes") or []):
            status, reason = "REJECTED", "CUSTOMER_OWNERSHIP_MISMATCH"
        elif not bool((file_obj.get("consent") or {}).get("privacy")):
            status, reason = "REJECTED", "PRIVACY_CONSENT_REQUIRED"

        effect = {
            "session_root": sid,
            "file_id": file_id,
            "operation": operation,
            "reason": reason,
            "customer_id": (session or {}).get("customer_id"),
            "file_state": (file_obj or {}).get("state"),
        }
        audit = {**effect, "status": status, "produced_ns": now}
        self.store.commit(lambda s: s["customer_access_audit"].append(audit) or audit)
        return self.store.record(TransitionReceipt("CUSTOMER_ACCESS", "AUTHORIZE", file_id, status, effect, now))

    def read_customer_file(self, session_token: str, file_id: str, *, now_ns: int | None = None) -> dict[str, Any]:
        decision = self.authorize(session_token, file_id, "customer_file:read", now_ns=now_ns)
        if decision.status != "AUTHORIZED":
            raise PermissionError(str(decision.effect.get("reason")))
        obj = json.loads(json.dumps(self.store.state["customer_files"][file_id]))
        return {
            "file_id": file_id,
            "customer_id": obj.get("customer_id"),
            "state": obj.get("state"),
            "communications": obj.get("communications", []),
            "billing": obj.get("billing", []),
            "exports": obj.get("exports", []),
            "retention": obj.get("retention"),
            "version": obj.get("version"),
            "access_receipt_root": decision.receipt_root,
        }
