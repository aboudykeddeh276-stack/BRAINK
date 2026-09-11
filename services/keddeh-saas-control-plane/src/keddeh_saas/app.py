from __future__ import annotations
import hmac, os
from pathlib import Path
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .store import ControlPlaneStore
from .domain import Domain, Relation, permitted

DB_PATH=os.getenv("KEDDEH_SAAS_DB","/data/keddeh_saas.sqlite3")
app=FastAPI(title="KEDDEH Quarantined SaaS Control Plane",version="2.0.0",docs_url="/docs",redoc_url="/redoc")
store=ControlPlaneStore(DB_PATH)

class TenantIn(BaseModel): product:str=Field(min_length=1,max_length=64); display_name:str=Field(min_length=1,max_length=160)
class IdentityIn(BaseModel): tenant_id:str; subject_ref:str=Field(min_length=1,max_length=256); roles:list[str]=Field(default_factory=list,max_length=32)
class PaymentEventIn(BaseModel): tenant_id:str; provider:str=Field(min_length=1,max_length=64); provider_reference:str=Field(min_length=1,max_length=256); sku:str=Field(min_length=1,max_length=128); amount_minor:int=Field(ge=0,le=10**12); currency:str=Field(pattern=r"^[A-Z]{3}$"); terminal_state:str
class JobIn(BaseModel): tenant_id:str; service:str=Field(min_length=1,max_length=128); payload_ref:str=Field(min_length=1,max_length=512)
class BoundaryProbe(BaseModel): source:Domain; target:Domain; relation:Relation

def mutation_auth(x_keddeh_control_key: str | None = Header(default=None)) -> None:
    required=os.getenv("KEDDEH_CONTROL_API_KEY")
    if required and (not x_keddeh_control_key or not hmac.compare_digest(required,x_keddeh_control_key)):
        raise HTTPException(401,"CONTROL_KEY_REQUIRED")

@app.get("/health")
def health(): return {"status":"PASS","service":"saas-control-plane","version":"2.0.0","evidence_chain":store.verify_chain()}
@app.get("/ready")
def ready(): return {"ready":store.verify_chain(),"db":str(Path(DB_PATH).name)}
@app.get("/v1/catalog")
def catalog(): return {"services":["database","identity","billing","job-queue","durable-storage","runtime-dispatch","evidence"],"products":["casepath","claimpath","braink","kex"]}
@app.post("/v1/tenants",dependencies=[Depends(mutation_auth)])
def create_tenant(body:TenantIn): row,receipt=store.create_tenant(body.product,body.display_name); return {"tenant":row,"receipt":receipt}
@app.post("/v1/identities",dependencies=[Depends(mutation_auth)])
def create_identity(body:IdentityIn):
    try: row,receipt=store.register_identity(body.tenant_id,body.subject_ref,body.roles)
    except KeyError as e: raise HTTPException(404,str(e))
    return {"identity":row,"receipt":receipt}
@app.post("/v1/billing/events",dependencies=[Depends(mutation_auth)])
def payment_event(body:PaymentEventIn):
    try: row,receipt=store.apply_payment_event(**body.model_dump())
    except KeyError as e: raise HTTPException(404,str(e))
    return {"billing":row,"receipt":receipt}
@app.post("/v1/jobs",dependencies=[Depends(mutation_auth)])
def enqueue_job(body:JobIn):
    try: row,receipt=store.enqueue_job(**body.model_dump())
    except KeyError as e: raise HTTPException(404,str(e))
    return {"job":row,"receipt":receipt}
@app.post("/v1/boundaries/probe")
def boundary_probe(body:BoundaryProbe):
    rule=permitted(body.source,body.target,body.relation); return {"allowed":rule.allowed,"reason":rule.reason,"source":body.source,"target":body.target,"relation":body.relation}
@app.get("/v1/evidence")
def evidence(): return store.snapshot()
@app.get("/v1/adapters/casepath")
def casepath_adapter(): return {"identity":"adapter://saas/casepath","owns":"SaaS dependencies only","business_runtime":"app://casepath / volume://casepath/v19","services":["identity","billing","job-queue","durable-storage","evidence"],"forbidden":["DNTG theorem mutation","legal conclusion promotion"]}
@app.get("/v1/adapters/claimpath")
def claimpath_adapter(): return {"identity":"adapter://saas/claimpath","owns":"SaaS dependencies only","product_runtime":"app://claimpath","services":["database","identity","billing","job-queue","ingress","durable-storage"],"forbidden":["replacement of CasePath runtime","research-model promotion"]}
