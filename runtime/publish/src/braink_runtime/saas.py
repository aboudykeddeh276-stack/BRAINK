from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProvisioningIntent:
    tenant_id: str
    system_id: str
    service_id: str
    plan: str
    requested_by: str
    idempotency_key: str | None = None


class SaaSNode:
    """Cross-system SaaS control-plane node.

    This node does not replace a product runtime. It binds tenants and
    entitlements to registered system/service adapters and emits durable
    provisioning/audit records that downstream actuators may execute.

    Payment events accepted here are assumed to have been authenticated and
    verified by the upstream payment rail. This class deliberately does not
    handle provider secrets or webhook signature verification.
    """

    PAID_STATUSES = {"paid", "succeeded", "complete", "completed"}

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "saas_node.sqlite3"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS systems (
                    system_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    adapter_uri TEXT NOT NULL,
                    runtime_uri TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS tenants (
                    tenant_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS entitlements (
                    tenant_id TEXT NOT NULL,
                    system_id TEXT NOT NULL,
                    service_id TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    status TEXT NOT NULL,
                    limits_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (tenant_id, system_id, service_id)
                );
                CREATE TABLE IF NOT EXISTS provisioning_intents (
                    intent_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    system_id TEXT NOT NULL,
                    service_id TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS payment_events (
                    event_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    system_id TEXT NOT NULL,
                    service_id TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    payment_status TEXT NOT NULL,
                    processing_status TEXT NOT NULL,
                    provisioning_intent_id TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _canonical_hash(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _audit(self, event_type: str, subject: str, payload: dict[str, Any]) -> dict[str, Any]:
        created_at = datetime.now(timezone.utc).isoformat()
        body = {"event_type": event_type, "subject": subject, "payload": payload, "created_at": created_at}
        event_id = self._canonical_hash(body)
        with self._connect() as con:
            con.execute(
                "INSERT OR IGNORE INTO audit_events(event_id,event_type,subject,payload_json,created_at) VALUES(?,?,?,?,?)",
                (event_id, event_type, subject, json.dumps(payload, sort_keys=True), created_at),
            )
        return {"event_id": event_id, **body}

    def register_system(self, system_id: str, name: str, adapter_uri: str, runtime_uri: str | None = None,
                        metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        metadata = metadata or {}
        with self._connect() as con:
            con.execute(
                """INSERT INTO systems(system_id,name,adapter_uri,runtime_uri,metadata_json,active)
                   VALUES(?,?,?,?,?,1)
                   ON CONFLICT(system_id) DO UPDATE SET
                     name=excluded.name,adapter_uri=excluded.adapter_uri,runtime_uri=excluded.runtime_uri,
                     metadata_json=excluded.metadata_json,active=1""",
                (system_id, name, adapter_uri, runtime_uri, json.dumps(metadata, sort_keys=True)),
            )
        self._audit("SYSTEM_REGISTERED", system_id, {"adapter_uri": adapter_uri, "runtime_uri": runtime_uri})
        return self.get_system(system_id)

    def get_system(self, system_id: str) -> dict[str, Any] | None:
        with self._connect() as con:
            row = con.execute("SELECT * FROM systems WHERE system_id=?", (system_id,)).fetchone()
        if not row:
            return None
        out = dict(row)
        out["metadata"] = json.loads(out.pop("metadata_json"))
        out["active"] = bool(out["active"])
        return out

    def list_systems(self) -> list[dict[str, Any]]:
        with self._connect() as con:
            ids = [r[0] for r in con.execute("SELECT system_id FROM systems ORDER BY system_id")]
        return [self.get_system(i) for i in ids if self.get_system(i)]

    def upsert_tenant(self, tenant_id: str, display_name: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        metadata = metadata or {}
        with self._connect() as con:
            con.execute(
                """INSERT INTO tenants(tenant_id,display_name,metadata_json,active) VALUES(?,?,?,1)
                   ON CONFLICT(tenant_id) DO UPDATE SET display_name=excluded.display_name,
                   metadata_json=excluded.metadata_json,active=1""",
                (tenant_id, display_name, json.dumps(metadata, sort_keys=True)),
            )
        self._audit("TENANT_UPSERTED", tenant_id, {"display_name": display_name})
        return {"tenant_id": tenant_id, "display_name": display_name, "metadata": metadata, "active": True}

    def grant_entitlement(self, tenant_id: str, system_id: str, service_id: str, plan: str,
                          limits: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.get_system(system_id):
            raise ValueError(f"unknown system: {system_id}")
        limits = limits or {}
        with self._connect() as con:
            tenant = con.execute("SELECT 1 FROM tenants WHERE tenant_id=? AND active=1", (tenant_id,)).fetchone()
            if not tenant:
                raise ValueError(f"unknown tenant: {tenant_id}")
            con.execute(
                """INSERT INTO entitlements(tenant_id,system_id,service_id,plan,status,limits_json)
                   VALUES(?,?,?,?, 'ACTIVE', ?)
                   ON CONFLICT(tenant_id,system_id,service_id) DO UPDATE SET
                     plan=excluded.plan,status='ACTIVE',limits_json=excluded.limits_json""",
                (tenant_id, system_id, service_id, plan, json.dumps(limits, sort_keys=True)),
            )
        payload = {"tenant_id": tenant_id, "system_id": system_id, "service_id": service_id,
                   "plan": plan, "status": "ACTIVE", "limits": limits}
        self._audit("ENTITLEMENT_GRANTED", f"{tenant_id}:{system_id}:{service_id}", payload)
        return payload

    def resolve(self, tenant_id: str, system_id: str, service_id: str) -> dict[str, Any]:
        system = self.get_system(system_id)
        if not system or not system["active"]:
            raise ValueError(f"system unavailable: {system_id}")
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM entitlements WHERE tenant_id=? AND system_id=? AND service_id=? AND status='ACTIVE'",
                (tenant_id, system_id, service_id),
            ).fetchone()
        if not row:
            raise PermissionError("service not entitled")
        return {
            "tenant_id": tenant_id,
            "system_id": system_id,
            "service_id": service_id,
            "plan": row["plan"],
            "limits": json.loads(row["limits_json"]),
            "adapter_uri": system["adapter_uri"],
            "runtime_uri": system["runtime_uri"],
        }

    def request_provisioning(self, intent: ProvisioningIntent) -> dict[str, Any]:
        route = self.resolve(intent.tenant_id, intent.system_id, intent.service_id)
        payload = {**intent.__dict__, "route": route}
        if intent.idempotency_key:
            intent_id = self._canonical_hash({"idempotency_key": intent.idempotency_key, "payload": payload})
            with self._connect() as con:
                existing = con.execute("SELECT * FROM provisioning_intents WHERE intent_id=?", (intent_id,)).fetchone()
            if existing:
                existing_payload = json.loads(existing["payload_json"])
                return {
                    "intent_id": intent_id,
                    "status": existing["status"],
                    "created_at": existing["created_at"],
                    "duplicate": True,
                    **existing_payload,
                }
        else:
            created_at_seed = datetime.now(timezone.utc).isoformat()
            intent_id = self._canonical_hash({"payload": payload, "created_at": created_at_seed})

        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as con:
            con.execute(
                """INSERT INTO provisioning_intents(intent_id,tenant_id,system_id,service_id,plan,requested_by,status,payload_json,created_at)
                   VALUES(?,?,?,?,?,?, 'PENDING_ACTUATION', ?,?)""",
                (intent_id, intent.tenant_id, intent.system_id, intent.service_id, intent.plan,
                 intent.requested_by, json.dumps(payload, sort_keys=True), created_at),
            )
        self._audit("PROVISIONING_REQUESTED", intent_id, payload)
        return {"intent_id": intent_id, "status": "PENDING_ACTUATION", "created_at": created_at, "duplicate": False, **payload}

    def process_verified_payment_event(
        self,
        *,
        provider: str,
        event_id: str,
        event_type: str,
        tenant_id: str,
        system_id: str,
        service_id: str,
        plan: str,
        payment_status: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Convert one already-verified provider event into SaaS state exactly once.

        The provider webhook signature must be verified before this method is
        called. Replays of the same provider/event ID return the original
        result and do not mint a second provisioning intent.
        """
        provider = provider.strip().lower()
        event_id = event_id.strip()
        payment_status = payment_status.strip().lower()
        if not provider or not event_id:
            raise ValueError("provider and event_id are required")

        canonical_event_id = f"{provider}:{event_id}"
        with self._connect() as con:
            existing = con.execute("SELECT * FROM payment_events WHERE event_id=?", (canonical_event_id,)).fetchone()
        if existing:
            return {
                "event_id": canonical_event_id,
                "provider": existing["provider"],
                "event_type": existing["event_type"],
                "payment_status": existing["payment_status"],
                "processing_status": existing["processing_status"],
                "provisioning_intent_id": existing["provisioning_intent_id"],
                "duplicate": True,
            }

        event_payload = payload or {}
        created_at = datetime.now(timezone.utc).isoformat()
        if payment_status not in self.PAID_STATUSES:
            with self._connect() as con:
                con.execute(
                    """INSERT INTO payment_events(event_id,provider,event_type,tenant_id,system_id,service_id,plan,
                       payment_status,processing_status,provisioning_intent_id,payload_json,created_at)
                       VALUES(?,?,?,?,?,?,?,?, 'IGNORED_NOT_PAID', NULL, ?,?)""",
                    (canonical_event_id, provider, event_type, tenant_id, system_id, service_id, plan,
                     payment_status, json.dumps(event_payload, sort_keys=True), created_at),
                )
            self._audit("PAYMENT_EVENT_IGNORED", canonical_event_id, {"payment_status": payment_status})
            return {
                "event_id": canonical_event_id,
                "provider": provider,
                "event_type": event_type,
                "payment_status": payment_status,
                "processing_status": "IGNORED_NOT_PAID",
                "provisioning_intent_id": None,
                "duplicate": False,
            }

        entitlement = self.grant_entitlement(tenant_id, system_id, service_id, plan)
        provisioning = self.request_provisioning(
            ProvisioningIntent(
                tenant_id=tenant_id,
                system_id=system_id,
                service_id=service_id,
                plan=plan,
                requested_by=f"payment:{canonical_event_id}",
                idempotency_key=canonical_event_id,
            )
        )
        with self._connect() as con:
            con.execute(
                """INSERT INTO payment_events(event_id,provider,event_type,tenant_id,system_id,service_id,plan,
                   payment_status,processing_status,provisioning_intent_id,payload_json,created_at)
                   VALUES(?,?,?,?,?,?,?,?, 'ENTITLED_PENDING_ACTUATION', ?,?,?)""",
                (canonical_event_id, provider, event_type, tenant_id, system_id, service_id, plan,
                 payment_status, provisioning["intent_id"], json.dumps(event_payload, sort_keys=True), created_at),
            )
        self._audit(
            "PAYMENT_ACTIVATED",
            canonical_event_id,
            {"entitlement": entitlement, "provisioning_intent_id": provisioning["intent_id"]},
        )
        return {
            "event_id": canonical_event_id,
            "provider": provider,
            "event_type": event_type,
            "payment_status": payment_status,
            "processing_status": "ENTITLED_PENDING_ACTUATION",
            "entitlement": entitlement,
            "provisioning_intent_id": provisioning["intent_id"],
            "duplicate": False,
        }

    def audit_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM audit_events ORDER BY rowid DESC LIMIT ?", (max(1, min(limit, 1000)),)
            ).fetchall()
        return [{**dict(r), "payload": json.loads(r["payload_json"])} for r in rows]
