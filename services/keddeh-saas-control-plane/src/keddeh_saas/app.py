from __future__ import annotations

import hmac
import os
from pathlib import Path
from typing import Any, Callable

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .braink_bridge import BrainkBridge
from .domain import Domain, Relation, permitted
from .store import ControlPlaneStore

DB_PATH = os.getenv("KEDDEH_SAAS_DB", "/data/keddeh_saas.sqlite3")
app = FastAPI(
    title="KEDDEH Quarantined SaaS Control Plane",
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
store = ControlPlaneStore(DB_PATH)
braink = BrainkBridge()


class TenantIn(BaseModel):
    product: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=160)


class IdentityIn(BaseModel):
    tenant_id: str
    subject_ref: str = Field(min_length=1, max_length=256)
    roles: list[str] = Field(default_factory=list, max_length=32)


class PaymentEventIn(BaseModel):
    tenant_id: str
    provider: str = Field(min_length=1, max_length=64)
    provider_reference: str = Field(min_length=1, max_length=256)
    sku: str = Field(min_length=1, max_length=128)
    amount_minor: int = Field(ge=0, le=10**12)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    terminal_state: str


class JobIn(BaseModel):
    tenant_id: str
    service: str = Field(min_length=1, max_length=128)
    payload_ref: str = Field(min_length=1, max_length=512)


class BoundaryProbe(BaseModel):
    source: Domain
    target: Domain
    relation: Relation


def mutation_auth(x_keddeh_control_key: str | None = Header(default=None)) -> None:
    required = os.getenv("KEDDEH_CONTROL_API_KEY")
    if required and (
        not x_keddeh_control_key
        or not hmac.compare_digest(required, x_keddeh_control_key)
    ):
        raise HTTPException(401, "CONTROL_KEY_REQUIRED")


def braink_status() -> dict[str, Any]:
    try:
        return braink.preflight()
    except Exception as exc:
        return {
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def mirror_local_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Project a committed local receipt into BRAINK IL-LLM evidence.

    The local SaaS mutation remains the business/SaaS state mutation. BRAINK is
    the governance/evidence projection. A projection failure is persisted and
    returned; it is never silently rewritten as successful qualification.
    """
    try:
        event = braink.record(
            receipt["event"],
            receipt["subject"],
            {
                "local_receipt_hash": receipt["receipt_hash"],
                "local_payload_hash": receipt["payload_hash"],
                "local_sequence": receipt["seq"],
                "local_observed_at_ns": receipt["observed_at_ns"],
            },
        )
        sync = store.mark_braink_evidence_synced(
            receipt["receipt_hash"], event["event_root"]
        )
        return {
            "status": "SYNCED",
            "event_root": event["event_root"],
            "sync": sync,
        }
    except Exception as exc:
        sync = store.mark_braink_evidence_failed(
            receipt["receipt_hash"], f"{type(exc).__name__}:{exc}"
        )
        return {
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "sync": sync,
        }


def mutate(operation: Callable[[], tuple[dict, dict]]) -> tuple[dict, dict, dict]:
    row, receipt = operation()
    evidence = mirror_local_receipt(receipt)
    return row, receipt, evidence


@app.get("/health")
def health():
    return {
        "status": "PASS" if store.verify_chain() else "FAIL",
        "service": "saas-control-plane",
        "version": "2.1.0",
        "local_evidence_chain": store.verify_chain(),
    }


@app.get("/ready")
def ready():
    local_ok = store.verify_chain()
    b = braink_status()
    pending = store.pending_braink_evidence()
    return {
        "service_ready": local_ok,
        "braink_evidence_ready": b.get("status") == "PASS" and not pending,
        "qualification_ready": local_ok and b.get("status") == "PASS" and not pending,
        "local_db": str(Path(DB_PATH).name),
        "braink": b,
        "pending_braink_evidence": len(pending),
    }


@app.get("/v1/catalog")
def catalog():
    return {
        "implemented": [
            "tenant-registry",
            "identity-registry",
            "billing-entitlement-ledger",
            "job-queue",
            "local-evidence-ledger",
            "boundary-probe",
            "braink-illlm-evidence-bridge",
            "braink-runtime-registry-bridge",
        ],
        "descriptor_only": [
            "casepath-saas-adapter-description",
            "claimpath-saas-adapter-description",
        ],
        "declared_unbound": [
            "external-database-provider",
            "external-identity-provider",
            "external-payment-provider-network",
            "external-job-worker",
            "public-ingress",
            "public-production-deployment",
        ],
        "products": ["casepath", "claimpath", "braink", "kex"],
    }


@app.post("/v1/tenants", dependencies=[Depends(mutation_auth)])
def create_tenant(body: TenantIn):
    row, receipt, evidence = mutate(
        lambda: store.create_tenant(body.product, body.display_name)
    )
    return {"tenant": row, "receipt": receipt, "braink_evidence": evidence}


@app.post("/v1/identities", dependencies=[Depends(mutation_auth)])
def create_identity(body: IdentityIn):
    try:
        row, receipt, evidence = mutate(
            lambda: store.register_identity(body.tenant_id, body.subject_ref, body.roles)
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    return {"identity": row, "receipt": receipt, "braink_evidence": evidence}


@app.post("/v1/billing/events", dependencies=[Depends(mutation_auth)])
def payment_event(body: PaymentEventIn):
    try:
        row, receipt, evidence = mutate(
            lambda: store.apply_payment_event(**body.model_dump())
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    return {"billing": row, "receipt": receipt, "braink_evidence": evidence}


@app.post("/v1/jobs", dependencies=[Depends(mutation_auth)])
def enqueue_job(body: JobIn):
    try:
        row, receipt, evidence = mutate(
            lambda: store.enqueue_job(**body.model_dump())
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    return {"job": row, "receipt": receipt, "braink_evidence": evidence}


@app.post("/v1/boundaries/probe")
def boundary_probe(body: BoundaryProbe):
    rule = permitted(body.source, body.target, body.relation)
    return {
        "allowed": rule.allowed,
        "reason": rule.reason,
        "source": body.source,
        "target": body.target,
        "relation": body.relation,
    }


@app.get("/v1/evidence")
def evidence():
    return {"local": store.snapshot(), "braink": braink_status()}


@app.get("/v1/braink/status")
def get_braink_status():
    return braink_status()


@app.post("/v1/braink/runtime/admit", dependencies=[Depends(mutation_auth)])
def admit_braink_runtime():
    return braink.admit_runtime_candidate()


@app.get("/v1/adapters/casepath")
def casepath_adapter():
    return {
        "identity": "adapter-description://saas/casepath",
        "implementation_state": "DESCRIPTOR_ONLY",
        "owns": "SaaS dependencies only",
        "business_runtime": "app://casepath / volume://casepath/v19",
        "declared_services": [
            "identity",
            "billing",
            "job-queue",
            "durable-storage",
            "evidence",
        ],
        "forbidden": ["DNTG theorem mutation", "legal conclusion promotion"],
    }


@app.get("/v1/adapters/claimpath")
def claimpath_adapter():
    return {
        "identity": "adapter-description://saas/claimpath",
        "implementation_state": "DESCRIPTOR_ONLY",
        "owns": "SaaS dependencies only",
        "product_runtime": "app://claimpath",
        "declared_services": [
            "database",
            "identity",
            "billing",
            "job-queue",
            "ingress",
            "durable-storage",
        ],
        "forbidden": [
            "replacement of CasePath runtime",
            "research-model promotion",
        ],
    }
