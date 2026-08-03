from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.models import User
from app.core.db import get_db
from app.core.ownership import get_owned
from app.core.pagination import Page, Pagination
from app.goals.models import Goal
from app.goals.schemas import GoalCreate, GoalResponse, GoalUpdate

router = APIRouter(prefix="/api/v1/goals", tags=["goals"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=GoalResponse)
async def create_goal(
    body: GoalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Goal:
    goal = Goal(user_id=current_user.id, **body.model_dump())
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return goal


@router.get("", response_model=Page[GoalResponse])
async def list_goals(
    pagination: Pagination = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[GoalResponse]:
    base_query = select(Goal).where(Goal.user_id == current_user.id)

    total = await db.scalar(select(func.count()).select_from(base_query.subquery()))
    result = await db.scalars(
        base_query.order_by(Goal.created_at).limit(pagination.limit).offset(pagination.offset)
    )

    return Page(
        items=[GoalResponse.model_validate(g) for g in result],
        total=total or 0,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.patch("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: UUID,
    body: GoalUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Goal:
    goal = await get_owned(db, Goal, goal_id, current_user.id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    await db.commit()
    await db.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    goal = await get_owned(db, Goal, goal_id, current_user.id)
    await db.delete(goal)
    await db.commit()
