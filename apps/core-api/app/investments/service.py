from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.investments.models import Security


async def get_or_create_security(db: AsyncSession, symbol: str, name: str | None = None) -> Security:
    security = await db.scalar(select(Security).where(Security.symbol == symbol))
    if security is not None:
        return security

    security = Security(symbol=symbol, name=name or symbol)
    db.add(security)
    await db.commit()
    await db.refresh(security)
    return security
