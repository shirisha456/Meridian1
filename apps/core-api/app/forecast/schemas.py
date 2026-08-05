from datetime import date

from pydantic import BaseModel


class RecurringItem(BaseModel):
    merchant_name: str
    category_name: str | None
    average_amount_minor: int
    occurrences: int
    average_interval_days: float
    last_seen: date
    next_expected_date: date


class ForecastPoint(BaseModel):
    date: date
    projected_balance_minor: int


class ForecastResponse(BaseModel):
    as_of: date
    horizon_days: int
    starting_balance_minor: int
    projected_ending_balance_minor: int
    recurring_items: list[RecurringItem]
    daily_projection: list[ForecastPoint]
