from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.institutions.models import InstitutionStatus


class LinkTokenResponse(BaseModel):
    link_token: str


class InstitutionCreate(BaseModel):
    public_token: str = Field(min_length=1)
    # Forwarded from Plaid Link's onSuccess(publicToken, metadata) —
    # metadata.institution.institution_id / .name. Optional because an
    # API-only caller (or a test) has no Link metadata to forward; falls
    # back to "Linked account" rather than a fabricated institution name.
    institution_id: str | None = None
    institution_name: str | None = None


class InstitutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    plaid_institution_id: str | None
    status: InstitutionStatus
    created_at: datetime


class SyncResponse(BaseModel):
    transactions_changed: int
