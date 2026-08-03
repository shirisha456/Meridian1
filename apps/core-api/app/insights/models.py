import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Insight(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "insights"

    # Overrides TimestampMixin's DB-generated-only default: GET /latest
    # picks a single row via ORDER BY created_at DESC LIMIT 1, so this is
    # the one table where sub-second precision matters for correctness —
    # two ORM inserts in the same second would otherwise tie (SQLite's
    # CURRENT_TIMESTAMP has only 1-second resolution, and this was caught
    # by test_get_latest_returns_the_most_recently_generated_insight
    # failing nondeterministically). A Python-side microsecond timestamp
    # is used for the normal ORM insert path; server_default remains as a
    # fallback for any insert that bypasses the ORM.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    # No uniqueness on (user_id, period) — POST /insights/generate can be
    # called again for the same period (e.g. after more transactions land
    # or get recategorized) and simply adds a newer row; GET /latest
    # always returns the most recent by created_at.
    summary: Mapped[str] = mapped_column(Text)
