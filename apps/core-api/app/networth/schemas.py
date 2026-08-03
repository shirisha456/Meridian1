from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NetWorthSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    snapshot_date: date
    assets_minor: int
    liabilities_minor: int
    net_worth_minor: int
    created_at: datetime
