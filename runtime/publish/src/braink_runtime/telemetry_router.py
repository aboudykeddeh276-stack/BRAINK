from __future__ import annotations

import os
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .telemetry import TelemetryFabric
from .telemetry_google_projection import SheetProjectionConfig, project_snapshot
from .pool_carrier import PoolProfileError, available_pool_profiles, probe_provider


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


class StratumProbeRequest(BaseModel):
    endpoint_profile: str = "VIABTC_BTC"
    observe_s: float = 2.0
    timeout_s: float = 4.0


def build_telemetry_router(*, data_dir: str, auth_token: str) -> APIRouter:
    router = APIRouter(prefix="/telemetry", tags=["telemetry"])
    fabric = TelemetryFabric(data_dir)

    def require_auth(token: str | None) -> None:
        if auth_token and token != auth_token:
            raise HTTPException(401, "invalid token")

    @router.post("/ingest")
    def ingest(req: TelemetryIngestRequest, x_braink_token: str | None = Header(default=None)):
        require_auth(x_braink_token)
        result = fabric.ingest(req.model_dump(exclude_none=True))
        if result["status"] == "QUARANTINED":
            raise HTTPException(422, result)
        return result

    @router.get("/snapshot")
    def snapshot():
        return fabric.snapshot()

    @router.get("/sheet-projection")
    def sheet_projection(x_braink_token: str | None = Header(default=None)):
        require_auth(x_braink_token)
        return {"rows": fabric.sheet_projection()}

    @router.get("/pool-profiles")
    def pool_profiles():
        return {"profiles": available_pool_profiles(), "default": os.getenv("BRAINK_MINING_PROVIDER", "VIABTC_BTC")}

    @router.post("/stratum-probe")
    async def stratum_probe(req: StratumProbeRequest, x_braink_token: str | None = Header(default=None)):
        """Open a read-only Stratum session through a named external provider profile.

        Provider identity is a projection. BRAINK/KEX remains canonical authority.
        The probe may subscribe/authorize but never calls mining.submit.
        """
        require_auth(x_braink_token)
        profile = req.endpoint_profile.strip().upper() or os.getenv("BRAINK_MINING_PROVIDER", "VIABTC_BTC")
        worker_name = os.getenv("BRAINK_STRATUM_WORKER", "").strip() or None
        password = os.getenv("BRAINK_STRATUM_PASSWORD", os.getenv("BRAINK_POOL_PASSWORD", "x"))
        observe_s = max(0.1, min(req.observe_s, 10.0))
        timeout_s = max(0.5, min(req.timeout_s, 10.0))
        try:
            return await probe_provider(
                profile,
                worker_name=worker_name,
                password=password,
                observe_s=observe_s,
                timeout_s=timeout_s,
            )
        except PoolProfileError as exc:
            raise HTTPException(400, {
                "status": "UNKNOWN_POOL_PROFILE",
                "requested": profile,
                "allowed": available_pool_profiles(),
                "error": str(exc),
            }) from exc
        except Exception as exc:
            raise HTTPException(502, {
                "status": "STRATUM_SESSION_FAILED",
                "endpoint_profile": profile,
                "error": f"{type(exc).__name__}:{exc}",
            }) from exc

    @router.post("/google-project")
    def google_project(x_braink_token: str | None = Header(default=None)):
        require_auth(x_braink_token)
        credentials_file = (
            os.getenv("BRAINK_GOOGLE_CREDENTIALS", "").strip()
            or os.getenv("BRAINK_GOOGLE_OAUTH_CLIENT_FILE", "").strip()
        )
        token_file = (
            os.getenv("BRAINK_GOOGLE_TOKEN", "").strip()
            or os.getenv("BRAINK_GOOGLE_OAUTH_TOKEN_FILE", "").strip()
        )
        spreadsheet_id = os.getenv("BRAINK_TELEMETRY_SPREADSHEET_ID", "").strip()
        target_range = os.getenv("BRAINK_TELEMETRY_RANGE", "TCP_SOCKET_TELEMETRY!B11:N17").strip()
        missing = []
        if not credentials_file:
            missing.append("BRAINK_GOOGLE_CREDENTIALS")
        if not token_file:
            missing.append("BRAINK_GOOGLE_TOKEN")
        if not spreadsheet_id:
            missing.append("BRAINK_TELEMETRY_SPREADSHEET_ID")
        if missing:
            raise HTTPException(503, {"status": "GOOGLE_PROJECTION_UNBOUND", "missing": missing})
        snap = fabric.snapshot()
        if not snap["streams"]:
            raise HTTPException(409, {"status": "NO_CANONICAL_TELEMETRY_TO_PROJECT"})
        try:
            return project_snapshot(
                snap,
                credentials_file=credentials_file,
                token_file=token_file,
                config=SheetProjectionConfig(
                    spreadsheet_id=spreadsheet_id,
                    telemetry_range=target_range,
                ),
            )
        except Exception as exc:
            raise HTTPException(502, {"status": "GOOGLE_PROJECTION_FAILED", "error": str(exc)}) from exc

    return router
