from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    target_amount_minor: int = Field(gt=0)
    current_amount_minor: int = 0
    target_date: date | None = None


class GoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    target_amount_minor: int | None = Field(default=None, gt=0)
    current_amount_minor: int | None = None
    target_date: date | None = None


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    target_amount_minor: int
    current_amount_minor: int
    target_date: date | None
    created_at: datetime
