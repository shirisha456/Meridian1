import uuid
from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class NetWorthSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "net_worth_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "snapshot_date", name="uq_networth_user_date"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date)
    assets_minor: Mapped[int] = mapped_column(BigInteger)
    liabilities_minor: Mapped[int] = mapped_column(BigInteger)
    net_worth_minor: Mapped[int] = mapped_column(BigInteger)
