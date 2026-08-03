from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account
from app.accounts.schemas import AccountCreate, AccountResponse, AccountUpdate
from app.auth.deps import get_current_user
from app.auth.models import User
from app.core.db import get_db
from app.core.ownership import get_owned
from app.core.pagination import Page, Pagination

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AccountResponse)
async def create_account(
    body: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Account:
    # Note: net worth is a point-in-time snapshot written only by
    # POST /networth/recompute, not derived live from account balances on
    # every read — creating/editing an account has nothing to invalidate
    # here; the next recompute picks up the new balance naturally.
    account = Account(user_id=current_user.id, **body.model_dump())
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("", response_model=Page[AccountResponse])
async def list_accounts(
    pagination: Pagination = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[AccountResponse]:
    base_query = select(Account).where(Account.user_id == current_user.id)

    total = await db.scalar(select(func.count()).select_from(base_query.subquery()))
    result = await db.scalars(
        base_query.order_by(Account.created_at).limit(pagination.limit).offset(pagination.offset)
    )

    return Page(
        items=[AccountResponse.model_validate(a) for a in result],
        total=total or 0,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Account:
    return await get_owned(db, Account, account_id, current_user.id)


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: UUID,
    body: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Account:
    account = await get_owned(db, Account, account_id, current_user.id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    account = await get_owned(db, Account, account_id, current_user.id)
    await db.delete(account)
    await db.commit()
