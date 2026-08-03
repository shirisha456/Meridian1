from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.accounts.models import AccountType


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: AccountType
    currency: str = Field(default="USD", min_length=3, max_length=3)
    current_balance_minor: int = 0


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: AccountType | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    current_balance_minor: int | None = None


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    type: AccountType
    currency: str
    current_balance_minor: int
    created_at: datetime
