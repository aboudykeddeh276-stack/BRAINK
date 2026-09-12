from __future__ import annotations

import os
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .telemetry import TelemetryFabric
from .telemetry_google_projection import SheetProjectionConfig, project_snapshot


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

    @router.post("/google-project")
    def google_project(x_braink_token: str | None = Header(default=None)):
        """Push canonical resident telemetry into the configured Google Sheet.

        This endpoint is deliberately fail-closed. The Google OAuth credential and
        token files remain host-owned. A successful write proves only spreadsheet
        projection/readback; it does not prove socket or mining authority.
        """
        require_auth(x_braink_token)
        credentials_file = os.getenv("BRAINK_GOOGLE_OAUTH_CLIENT_FILE", "").strip()
        token_file = os.getenv("BRAINK_GOOGLE_OAUTH_TOKEN_FILE", "").strip()
        spreadsheet_id = os.getenv("BRAINK_TELEMETRY_SPREADSHEET_ID", "").strip()
        target_range = os.getenv("BRAINK_TELEMETRY_RANGE", "TCP_SOCKET_TELEMETRY!B11:N17").strip()
        missing = [
            name
            for name, value in (
                ("BRAINK_GOOGLE_OAUTH_CLIENT_FILE", credentials_file),
                ("BRAINK_GOOGLE_OAUTH_TOKEN_FILE", token_file),
                ("BRAINK_TELEMETRY_SPREADSHEET_ID", spreadsheet_id),
            )
            if not value
        ]
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
