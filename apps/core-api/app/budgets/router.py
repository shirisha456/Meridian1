from datetime import date

import redis.asyncio as redis
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.models import User
from app.budgets import service
from app.budgets.models import Budget
from app.budgets.schemas import BudgetActualItem, BudgetResponse, BudgetUpsert
from app.core.cache import cache_delete_prefix, cache_get_json, cache_set_json
from app.core.db import get_db
from app.core.redis import get_redis

router = APIRouter(prefix="/api/v1/budgets", tags=["budgets"])

BUDGET_ACTUAL_CACHE_TTL_SECONDS = 60


@router.put("", response_model=BudgetResponse)
async def upsert_budget(
    body: BudgetUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> Budget:
    budget = await service.upsert_budget(
        db, current_user.id, body.category_id, body.month, body.amount_minor
    )
    await cache_delete_prefix(redis_client, f"budget_actual:{current_user.id}:")
    return budget


@router.get("", response_model=list[BudgetResponse])
async def list_budgets(
    month: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Budget]:
    month = month.replace(day=1)
    result = await db.scalars(
        select(Budget).where(Budget.user_id == current_user.id, Budget.month == month)
    )
    return list(result)


@router.get("/actual", response_model=list[BudgetActualItem])
async def get_budget_actual(
    month: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> list[BudgetActualItem]:
    month = month.replace(day=1)
    cache_key = f"budget_actual:{current_user.id}:{month.isoformat()}"

    cached = await cache_get_json(redis_client, cache_key)
    if cached is not None:
        return [BudgetActualItem.model_validate(item) for item in cached]

    items = await service.compute_budget_actual(db, current_user.id, month)
    await cache_set_json(
        redis_client,
        cache_key,
        [item.model_dump() for item in items],
        ttl_seconds=BUDGET_ACTUAL_CACHE_TTL_SECONDS,
    )
    return items
