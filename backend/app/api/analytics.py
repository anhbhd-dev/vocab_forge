"""Analytics — file 01 mục 2.

    GET /api/analytics/overview
    GET /api/analytics/error-breakdown
    GET /api/analytics/leeches
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep
from app.schemas.api import AnalyticsOverviewOut, ErrorBreakdownOut, LeechOut
from app.services import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverviewOut)
async def overview(user: CurrentUser, session: SessionDep) -> dict:
    return await analytics_service.overview(session, user)


@router.get("/error-breakdown", response_model=ErrorBreakdownOut)
async def error_breakdown(
    user: CurrentUser,
    session: SessionDep,
    days: int = Query(default=30, ge=1, le=365),
) -> dict:
    return await analytics_service.error_breakdown(session, user.id, days=days)


@router.get("/leeches", response_model=list[LeechOut])
async def leeches(user: CurrentUser, session: SessionDep) -> list[dict]:
    return await analytics_service.leeches(session, user.id)
