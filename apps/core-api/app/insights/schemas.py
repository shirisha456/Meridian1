from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InsightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    period_start: date
    period_end: date
    summary: str
    created_at: datetime


class GenerateInsightRequest(BaseModel):
    # Both optional — default to the current calendar month if omitted.
    period_start: date | None = None
    period_end: date | None = None
