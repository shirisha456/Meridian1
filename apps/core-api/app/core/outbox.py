from sqlalchemy import JSON, Boolean, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OutboxEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The transactional outbox (ADR-0005): a row here is written in the
    exact same DB transaction as the business change it accompanies, so
    "the transaction was created" and "an event about it exists to be
    published" can never disagree — no dual-write to Postgres and Kafka
    that could partially fail.
    """

    __tablename__ = "outbox_events"

    topic: Mapped[str] = mapped_column(String(120), index=True)
    key: Mapped[str] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSON)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


def write_outbox_event(db: AsyncSession, topic: str, key: str, payload: dict) -> None:
    """Adds the row to the session but does not commit — the caller
    must commit this together with the business row it accompanies in
    the same transaction. That's the entire transactional guarantee;
    there is no other mechanism enforcing it, so every call site must
    follow this contract."""
    db.add(OutboxEvent(topic=topic, key=key, payload=payload))
