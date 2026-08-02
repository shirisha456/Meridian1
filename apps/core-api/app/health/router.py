import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import database_is_ready, get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/live")
async def live() -> dict:
    """Process is up and can accept traffic. No dependency checks — this
    must stay cheap and fast, since orchestrators poll it frequently to
    decide whether to kill and restart the container."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(response: Response, db: AsyncSession = Depends(get_db)) -> dict:
    """Process is up AND its dependencies (today: just the database) are
    reachable. Orchestrators use this to decide whether to route traffic
    to this instance, distinct from whether to restart it — so, unlike
    /health, the HTTP status code itself carries the signal (a Kubernetes
    readinessProbe checks the status code, not the body)."""
    checks = await _run_checks(db)
    all_ok = all(checks.values())
    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if all_ok else "not_ready", "checks": checks}


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    """Aggregate health for humans/dashboards — same checks as /ready,
    kept as a separate endpoint since it's the one operators and this
    repo's own docs link to, while /live and /ready are for orchestrators."""
    checks = await _run_checks(db)
    all_ok = all(checks.values())
    return {"status": "ok" if all_ok else "degraded", "checks": checks}


async def _run_checks(db: AsyncSession) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    try:
        checks["database"] = await database_is_ready(db)
    except Exception:
        logger.warning("Readiness check failed: database unreachable", exc_info=True)
        checks["database"] = False
    return checks
