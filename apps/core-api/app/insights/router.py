from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.models import User
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.errors import NotFoundError
from app.insights import service
from app.insights.models import Insight
from app.insights.schemas import GenerateInsightRequest, InsightResponse

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])


@router.get("/latest", response_model=InsightResponse)
async def get_latest_insight(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Insight:
    insight = await db.scalar(
        select(Insight)
        .where(Insight.user_id == current_user.id)
        .order_by(Insight.created_at.desc())
        .limit(1)
    )
    if insight is None:
        raise NotFoundError("No insight has been generated yet.")
    return insight


@router.post("/generate", status_code=status.HTTP_201_CREATED, response_model=InsightResponse)
async def generate_insight(
    body: GenerateInsightRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Insight:
    period_start, period_end = service.resolve_period(body.period_start, body.period_end)
    return await service.generate_insight(db, current_user.id, period_start, period_end, settings)
