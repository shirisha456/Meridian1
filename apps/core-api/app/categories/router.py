from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.models import User
from app.categories.models import Category
from app.categories.schemas import CategoryResponse
from app.core.db import get_db

router = APIRouter(prefix="/api/v1/categories", tags=["categories"])


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Category]:
    # Global reference data, not user-scoped — auth is still required so
    # the category list isn't exposed to unauthenticated callers.
    result = await db.scalars(select(Category).order_by(Category.name))
    return list(result)
