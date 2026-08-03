import uuid
from datetime import date as date_
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Security(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "securities"

    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    # NULL until a price refresh actually succeeds — no synthetic/mock
    # price is ever stored, so "no price yet" in a response always means
    # exactly that, never a placeholder value someone mistakes for real data.
    latest_price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    latest_price_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SecurityPrice(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "security_prices"
    __table_args__ = (
        UniqueConstraint("security_id", "price_date", name="uq_security_price_date"),
    )

    security_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("securities.id", ondelete="CASCADE"), index=True
    )
    price_date: Mapped[date_] = mapped_column(Date)
    close_price_minor: Mapped[int] = mapped_column(BigInteger)


class Holding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "holdings"

    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("securities.id", ondelete="CASCADE"), index=True
    )
    quantity: Mapped[float] = mapped_column(Numeric(18, 6, asdecimal=False))
    cost_basis_minor: Mapped[int] = mapped_column(BigInteger)


class Watchlist(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "security_id", name="uq_watchlist_user_security"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("securities.id", ondelete="CASCADE"), index=True
    )
