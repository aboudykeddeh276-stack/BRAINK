from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from .sector_requirements import qualify_sector, requirements_for_sector


class SectorQualificationRequest(BaseModel):
    sector: str
    through_layer: str | None = None
    receipts: dict[str, str] = Field(default_factory=dict)


def build_sector_requirements_router(*, auth_token: str) -> APIRouter:
    router = APIRouter(prefix="/requirements", tags=["requirements"])

    def require_auth(token: str | None) -> None:
        if auth_token and token != auth_token:
            raise HTTPException(401, "invalid token")

    @router.get("/sector/{sector}")
    def sector_requirements(sector: str, through_layer: str | None = None):
        try:
            rows = requirements_for_sector(sector, through_layer=through_layer)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {
            "sector": sector.strip().upper(),
            "through_layer": through_layer.strip().upper() if through_layer else None,
            "selection_policy": "ALL_MANDATORY_REQUIREMENTS_IN_SELECTED_SECTOR_SCOPE",
            "requirements": [r.__dict__ for r in rows],
        }

    @router.post("/qualify")
    def qualify(req: SectorQualificationRequest, x_braink_token: str | None = Header(default=None)):
        require_auth(x_braink_token)
        try:
            result = qualify_sector(req.sector, req.receipts, through_layer=req.through_layer)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        if result["status"] != "QUALIFIED":
            raise HTTPException(409, result)
        return result

    return router
