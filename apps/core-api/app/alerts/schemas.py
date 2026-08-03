from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.alerts.models import AlertSeverity, AlertType


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    detail: str
    related_transaction_id: UUID | None
    read_at: datetime | None
    created_at: datetime
