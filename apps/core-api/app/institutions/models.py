import enum
import uuid

from sqlalchemy import Enum, ForeignKey, LargeBinary, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class InstitutionStatus(str, enum.Enum):
    active = "active"
    error = "error"
    revoked = "revoked"


class Institution(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "institutions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    plaid_item_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # Populated from Plaid Link's onSuccess metadata, forwarded by the
    # client — nullable because an API-only caller (or a test) has no
    # Link metadata to forward. Never hardcoded to a placeholder string.
    plaid_institution_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    access_token_ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    status: Mapped[InstitutionStatus] = mapped_column(
        Enum(InstitutionStatus, name="institution_status"), default=InstitutionStatus.active
    )
    transactions_cursor: Mapped[str | None] = mapped_column(String(255), nullable=True)
