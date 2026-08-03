from datetime import UTC, datetime, timedelta

import redis.asyncio as redis
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.models import User
from app.core.cache import cache_delete_prefix, cache_get_json, cache_set_json
from app.core.db import get_db
from app.core.redis import get_redis
from app.networth import service
from app.networth.models import NetWorthSnapshot
from app.networth.schemas import NetWorthSnapshotResponse

router = APIRouter(prefix="/api/v1/networth", tags=["networth"])

NETWORTH_CACHE_TTL_SECONDS = 60


@router.get("", response_model=list[NetWorthSnapshotResponse])
async def get_net_worth_history(
    days: int = Query(default=90, ge=1, le=730),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> list[NetWorthSnapshotResponse]:
    cache_key = f"networth:{current_user.id}:{days}"

    cached = await cache_get_json(redis_client, cache_key)
    if cached is not None:
        return [NetWorthSnapshotResponse.model_validate(item) for item in cached]

    cutoff = datetime.now(UTC).date() - timedelta(days=days)
    result = await db.scalars(
        select(NetWorthSnapshot)
        .where(NetWorthSnapshot.user_id == current_user.id, NetWorthSnapshot.snapshot_date >= cutoff)
        .order_by(NetWorthSnapshot.snapshot_date)
    )
    snapshots = [NetWorthSnapshotResponse.model_validate(s) for s in result]

    await cache_set_json(
        redis_client,
        cache_key,
        [s.model_dump() for s in snapshots],
        ttl_seconds=NETWORTH_CACHE_TTL_SECONDS,
    )
    return snapshots


@router.post("/recompute", response_model=NetWorthSnapshotResponse)
async def recompute_net_worth(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> NetWorthSnapshot:
    snapshot = await service.recompute_snapshot(db, current_user.id)
    await cache_delete_prefix(redis_client, f"networth:{current_user.id}:")
    return snapshot
