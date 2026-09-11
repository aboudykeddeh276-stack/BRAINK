from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


class SaaSCatalog:
    """Authoritative saleable-service and checkout admission catalog."""

    def __init__(self, data_dir: str):
        self.db_path = Path(data_dir) / "saas_node.sqlite3"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS service_catalog (
                    system_id TEXT NOT NULL,
                    service_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    runtime_uri TEXT NOT NULL,
                    plans_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    active INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY(system_id, service_id)
                );
                CREATE TABLE IF NOT EXISTS checkout_admissions (
                    admission_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    system_id TEXT NOT NULL,
                    service_id TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    runtime_uri TEXT NOT NULL,
                    provider TEXT,
                    provider_session_id TEXT UNIQUE,
                    kex_receipt_id TEXT,
                    status TEXT NOT NULL,
                    created_ns INTEGER NOT NULL,
                    bound_ns INTEGER,
                    verified_ns INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_checkout_admissions_route
                  ON checkout_admissions(tenant_id,system_id,service_id,plan,status);
                """
            )

    def upsert_service(
        self,
        *,
        system_id: str,
        service_id: str,
        display_name: str,
        runtime_uri: str,
        plans: dict[str, dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not system_id or not service_id or not runtime_uri:
            raise ValueError("system_id, service_id and runtime_uri are required")
        if not plans or any(not isinstance(v, dict) for v in plans.values()):
            raise ValueError("at least one structured plan is required")
        with self._connect() as con:
            system = con.execute("SELECT active FROM systems WHERE system_id=?", (system_id,)).fetchone()
            if not system or not bool(system["active"]):
                raise ValueError(f"system unavailable: {system_id}")
            con.execute(
                """INSERT INTO service_catalog(system_id,service_id,display_name,runtime_uri,plans_json,metadata_json,active)
                   VALUES(?,?,?,?,?,?,1)
                   ON CONFLICT(system_id,service_id) DO UPDATE SET
                     display_name=excluded.display_name,runtime_uri=excluded.runtime_uri,
                     plans_json=excluded.plans_json,metadata_json=excluded.metadata_json,active=1""",
                (system_id, service_id, display_name, runtime_uri, json.dumps(plans, sort_keys=True), json.dumps(metadata or {}, sort_keys=True)),
            )
        return self.get_service(system_id, service_id)

    def get_service(self, system_id: str, service_id: str) -> dict[str, Any]:
        with self._connect() as con:
            row = con.execute("SELECT * FROM service_catalog WHERE system_id=? AND service_id=?", (system_id, service_id)).fetchone()
        if not row:
            raise ValueError(f"unknown service: {system_id}:{service_id}")
        return {
            "system_id": row["system_id"], "service_id": row["service_id"], "display_name": row["display_name"],
            "runtime_uri": row["runtime_uri"], "plans": json.loads(row["plans_json"]), "metadata": json.loads(row["metadata_json"]),
            "active": bool(row["active"]),
        }

    def list_services(self) -> list[dict[str, Any]]:
        with self._connect() as con:
            keys = [(r[0], r[1]) for r in con.execute("SELECT system_id,service_id FROM service_catalog ORDER BY system_id,service_id")]
        return [self.get_service(system_id, service_id) for system_id, service_id in keys]

    def admit_checkout(self, *, tenant_id: str, system_id: str, service_id: str, plan: str) -> dict[str, Any]:
        with self._connect() as con:
            tenant = con.execute("SELECT active FROM tenants WHERE tenant_id=?", (tenant_id,)).fetchone()
            system = con.execute("SELECT active FROM systems WHERE system_id=?", (system_id,)).fetchone()
        if not tenant or not bool(tenant["active"]): raise ValueError(f"tenant unavailable: {tenant_id}")
        if not system or not bool(system["active"]): raise ValueError(f"system unavailable: {system_id}")
        service = self.get_service(system_id, service_id)
        if not service["active"]: raise ValueError(f"service unavailable: {system_id}:{service_id}")
        plans = service["plans"]
        if plan not in plans: raise ValueError(f"plan unavailable: {system_id}:{service_id}:{plan}")
        plan_spec = dict(plans[plan]); plan_spec["plan_id"] = plan
        allowed_keys = {"plan_id","stripe_price_id","price_id","mode","unit_amount","currency","quantity","interval","name","success_url","cancel_url"}
        provider_plan = {k: v for k, v in plan_spec.items() if k in allowed_keys}
        if not (provider_plan.get("stripe_price_id") or provider_plan.get("price_id") or provider_plan.get("unit_amount") is not None):
            raise ValueError("plan has no provider pricing binding")
        admission_id = "adm_" + uuid.uuid4().hex
        created_ns = time.time_ns()
        with self._connect() as con:
            con.execute(
                """INSERT INTO checkout_admissions(admission_id,tenant_id,system_id,service_id,plan,runtime_uri,status,created_ns)
                   VALUES(?,?,?,?,?,?, 'ADMITTED', ?)""",
                (admission_id, tenant_id, system_id, service_id, plan, service["runtime_uri"], created_ns),
            )
        return {
            "status": "ADMITTED", "admission_id": admission_id, "tenant_id": tenant_id, "system_id": system_id,
            "service_id": service_id, "plan": plan, "runtime_uri": service["runtime_uri"], "provider_plan": provider_plan,
        }

    def bind_checkout(self, *, admission_id: str, provider: str, provider_session_id: str, kex_receipt_id: str | None = None) -> dict[str, Any]:
        provider = provider.strip().lower(); provider_session_id = provider_session_id.strip()
        if not admission_id or not provider or not provider_session_id: raise ValueError("admission_id, provider and provider_session_id are required")
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM checkout_admissions WHERE admission_id=?", (admission_id,)).fetchone()
            if not row: raise ValueError("checkout admission not found")
            if row["status"] in {"BOUND", "VERIFIED"}:
                if row["provider"] != provider or row["provider_session_id"] != provider_session_id:
                    raise ValueError("checkout admission already bound to a different provider session")
                con.commit()
                return {"status": row["status"], "admission_id": admission_id, "provider": provider, "provider_session_id": provider_session_id, "duplicate": True}
            if row["status"] != "ADMITTED": raise ValueError(f"checkout admission state invalid: {row['status']}")
            con.execute(
                """UPDATE checkout_admissions SET provider=?,provider_session_id=?,kex_receipt_id=?,status='BOUND',bound_ns=?
                   WHERE admission_id=? AND status='ADMITTED'""",
                (provider, provider_session_id, kex_receipt_id, time.time_ns(), admission_id),
            )
            con.commit()
        return {"status": "BOUND", "admission_id": admission_id, "provider": provider, "provider_session_id": provider_session_id, "duplicate": False}

    def verify_provider_event(
        self, *, admission_id: str, provider: str, provider_session_id: str,
        tenant_id: str, system_id: str, service_id: str, plan: str,
    ) -> dict[str, Any]:
        provider = provider.strip().lower(); provider_session_id = provider_session_id.strip()
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM checkout_admissions WHERE admission_id=?", (admission_id,)).fetchone()
            if not row: raise ValueError("checkout admission not found")
            expected = {
                "provider": row["provider"], "provider_session_id": row["provider_session_id"], "tenant_id": row["tenant_id"],
                "system_id": row["system_id"], "service_id": row["service_id"], "plan": row["plan"],
            }
            actual = {
                "provider": provider, "provider_session_id": provider_session_id, "tenant_id": tenant_id,
                "system_id": system_id, "service_id": service_id, "plan": plan,
            }
            if expected != actual: raise ValueError("provider event does not match admitted checkout")
            if row["status"] not in {"BOUND", "VERIFIED"}: raise ValueError(f"checkout admission not bound: {row['status']}")
            duplicate = row["status"] == "VERIFIED"
            if not duplicate:
                con.execute("UPDATE checkout_admissions SET status='VERIFIED',verified_ns=? WHERE admission_id=? AND status='BOUND'", (time.time_ns(), admission_id))
            con.commit()
        return {"status": "VERIFIED", "admission_id": admission_id, "provider": provider, "provider_session_id": provider_session_id, "duplicate": duplicate}
