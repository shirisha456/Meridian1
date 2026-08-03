from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.models import Alert
from app.alerts.schemas import AlertResponse
from app.auth.deps import get_current_user
from app.auth.models import User
from app.core.db import get_db
from app.core.ownership import get_owned

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

# No POST /alerts here, deliberately — alerts are written directly to
# this table by anomaly-service (ADR-0007's shared-database pattern),
# not created through this API. This router is read/acknowledge only.


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Alert]:
    query = select(Alert).where(Alert.user_id == current_user.id)
    if unread_only:
        query = query.where(Alert.read_at.is_(None))
    query = query.order_by(Alert.created_at.desc())

    result = await db.scalars(query)
    return list(result)


@router.patch("/{alert_id}/read", response_model=AlertResponse)
async def mark_alert_read(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Alert:
    alert = await get_owned(db, Alert, alert_id, current_user.id)
    alert.read_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(alert)
    return alert
