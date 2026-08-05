from datetime import UTC, datetime

import redis.asyncio as redis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.models import User
from app.core.cache import cache_get_json, cache_set_json
from app.core.db import get_db
from app.core.redis import get_redis
from app.forecast import service
from app.forecast.schemas import ForecastResponse

router = APIRouter(prefix="/api/v1/forecast", tags=["forecast"])

# Short TTL, same reasoning as networth's cache (app/networth/router.py):
# cheap to recompute, but not free, and a page navigating back and forth
# shouldn't re-run the recurring-pattern query every time.
FORECAST_CACHE_TTL_SECONDS = 60


@router.get("", response_model=ForecastResponse)
async def get_forecast(
    horizon_days: int = Query(default=30, ge=1, le=180),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> ForecastResponse:
    as_of = datetime.now(UTC).date()
    cache_key = f"forecast:{current_user.id}:{as_of.isoformat()}:{horizon_days}"

    cached = await cache_get_json(redis_client, cache_key)
    if cached is not None:
        return ForecastResponse.model_validate(cached)

    forecast = await service.build_forecast(db, current_user.id, as_of=as_of, horizon_days=horizon_days)

    await cache_set_json(redis_client, cache_key, forecast.model_dump(), ttl_seconds=FORECAST_CACHE_TTL_SECONDS)
    return forecast
