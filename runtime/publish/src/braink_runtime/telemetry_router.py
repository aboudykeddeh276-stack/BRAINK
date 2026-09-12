from __future__ import annotations
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from .telemetry import TelemetryFabric

class TelemetryIngestRequest(BaseModel):
    worker_id: str
    accepted_shares: int | str
    rejected_shares: int | str
    last_reject_reason: str = "NONE"
    status: str = "ONLINE"
    difficulty: int | str | None = None
    job_id: str | None = None
    carrier_uri: str = "carrier://tl2"
    source_kind: str = "CARRIER_READBACK"
    observed_ns: int | None = None

def build_telemetry_router(*, data_dir: str, auth_token: str) -> APIRouter:
    router=APIRouter(prefix="/telemetry", tags=["telemetry"]); fabric=TelemetryFabric(data_dir)
    def require_auth(token):
        if auth_token and token != auth_token: raise HTTPException(401,"invalid token")
    @router.post("/ingest")
    def ingest(req:TelemetryIngestRequest, x_braink_token:str|None=Header(default=None)):
        require_auth(x_braink_token); result=fabric.ingest(req.model_dump(exclude_none=True))
        if result["status"]=="QUARANTINED": raise HTTPException(422,result)
        return result
    @router.get("/snapshot")
    def snapshot(): return fabric.snapshot()
    @router.get("/sheet-projection")
    def sheet_projection(x_braink_token:str|None=Header(default=None)):
        require_auth(x_braink_token); return {"rows":fabric.sheet_projection()}
    return router
