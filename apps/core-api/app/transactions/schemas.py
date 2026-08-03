from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TransactionCreate(BaseModel):
    account_id: UUID
    category_id: UUID | None = None
    merchant_name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    amount_minor: int
    currency: str = Field(default="USD", min_length=3, max_length=3)
    txn_date: date
    pending: bool = False


class TransactionUpdate(BaseModel):
    category_id: UUID | None = None
    merchant_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    amount_minor: int | None = None
    txn_date: date | None = None
    pending: bool | None = None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    category_id: UUID | None
    merchant_name: str
    description: str | None
    amount_minor: int
    currency: str
    txn_date: date
    pending: bool
    external_id: str | None
    created_at: datetime
