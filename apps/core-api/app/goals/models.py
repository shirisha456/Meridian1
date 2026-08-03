import uuid
from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Goal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "goals"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    target_amount_minor: Mapped[int] = mapped_column(BigInteger)
    current_amount_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
