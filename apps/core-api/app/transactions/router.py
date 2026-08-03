from datetime import date
from uuid import UUID

import redis.asyncio as redis
from fastapi import APIRouter, Depends, Header, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account
from app.auth.deps import get_current_user
from app.auth.models import User
from app.core.cache import cache_delete_prefix
from app.core.db import get_db
from app.core.idempotency import cache_response, get_cached_response
from app.core.ownership import get_owned
from app.core.pagination import Page, Pagination
from app.core.redis import get_redis
from app.errors import NotFoundError
from app.transactions.models import Transaction
from app.transactions.schemas import TransactionCreate, TransactionResponse, TransactionUpdate

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


async def _get_owned_account(db: AsyncSession, account_id: UUID, user_id: UUID) -> Account:
    return await get_owned(db, Account, account_id, user_id)


async def _get_owned_transaction(db: AsyncSession, transaction_id: UUID, user_id: UUID) -> Transaction:
    # Transactions have no user_id column of their own — ownership is
    # derived by joining through the account, so this can't reuse
    # core/ownership.py's single-table helper directly.
    txn = await db.get(Transaction, transaction_id)
    if txn is None:
        raise NotFoundError("Transaction not found.")
    account = await db.get(Account, txn.account_id)
    if account is None or account.user_id != user_id:
        raise NotFoundError("Transaction not found.")
    return txn


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TransactionResponse)
async def create_transaction(
    body: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TransactionResponse:
    if idempotency_key is not None:
        cached = await get_cached_response(redis_client, current_user.id, idempotency_key)
        if cached is not None:
            return TransactionResponse.model_validate(cached)

    # Must own the account before a transaction can be attached to it —
    # otherwise any authenticated user could post transactions onto an
    # account_id they merely guessed.
    await _get_owned_account(db, body.account_id, current_user.id)

    transaction = Transaction(**body.model_dump())
    db.add(transaction)
    await db.commit()
    await db.refresh(transaction)
    await cache_delete_prefix(redis_client, f"budget_actual:{current_user.id}:")

    response = TransactionResponse.model_validate(transaction)
    if idempotency_key is not None:
        await cache_response(redis_client, current_user.id, idempotency_key, response.model_dump())
    return response


@router.get("", response_model=Page[TransactionResponse])
async def list_transactions(
    account_id: UUID | None = None,
    category_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    pagination: Pagination = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[TransactionResponse]:
    base_query = select(Transaction).join(Account).where(Account.user_id == current_user.id)

    if account_id is not None:
        base_query = base_query.where(Transaction.account_id == account_id)
    if category_id is not None:
        base_query = base_query.where(Transaction.category_id == category_id)
    if date_from is not None:
        base_query = base_query.where(Transaction.txn_date >= date_from)
    if date_to is not None:
        base_query = base_query.where(Transaction.txn_date <= date_to)
    if q:
        base_query = base_query.where(Transaction.merchant_name.ilike(f"%{q}%"))

    total = await db.scalar(select(func.count()).select_from(base_query.subquery()))
    result = await db.scalars(
        base_query.order_by(Transaction.txn_date.desc(), Transaction.created_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )

    return Page(
        items=[TransactionResponse.model_validate(t) for t in result],
        total=total or 0,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Transaction:
    return await _get_owned_transaction(db, transaction_id, current_user.id)


@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: UUID,
    body: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> Transaction:
    transaction = await _get_owned_transaction(db, transaction_id, current_user.id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(transaction, field, value)
    await db.commit()
    await db.refresh(transaction)
    await cache_delete_prefix(redis_client, f"budget_actual:{current_user.id}:")
    return transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> None:
    transaction = await _get_owned_transaction(db, transaction_id, current_user.id)
    await db.delete(transaction)
    await db.commit()
    await cache_delete_prefix(redis_client, f"budget_actual:{current_user.id}:")
