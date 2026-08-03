from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BudgetUpsert(BaseModel):
    category_id: UUID
    month: date
    amount_minor: int = Field(gt=0)

    @field_validator("month")
    @classmethod
    def normalize_to_first_of_month(cls, value: date) -> date:
        return value.replace(day=1)


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category_id: UUID
    month: date
    amount_minor: int
    created_at: datetime


class BudgetActualItem(BaseModel):
    category_id: UUID
    category_name: str
    budgeted_minor: int
    actual_minor: int
    remaining_minor: int
