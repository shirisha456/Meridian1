import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.transactions.models import Transaction


class AccountType(str, enum.Enum):
    checking = "checking"
    savings = "savings"
    credit = "credit"
    investment = "investment"
    loan = "loan"
    cash = "cash"


class Account(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # NULL for manually-created accounts; set for accounts that arrived
    # via a Plaid sync (Phase 6). Deferred to Phase 6's own migration
    # rather than added in Phase 3 nullable-and-unused, since the
    # `institutions` table this references didn't exist until now.
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "institutions.id",
            ondelete="CASCADE",
            # Named explicitly: this FK is added via ALTER TABLE (accounts
            # already existed before institutions did), so — unlike a FK
            # baked into a table's original CREATE TABLE — Alembic needs
            # a real name to generate a working downgrade() DROP CONSTRAINT.
            name="fk_accounts_institution_id_institutions",
        ),
        nullable=True,
        index=True,
    )
    # index=True (not just unique=True) so this becomes a named Index
    # rather than an anonymous UniqueConstraint — same reasoning as the
    # FK above; every other unique column in this app pairs unique with
    # index for exactly this reason.
    plaid_account_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[AccountType] = mapped_column(Enum(AccountType, name="account_type"))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    # Integer minor units (cents), never a float — avoids floating-point
    # error accumulating across balance updates. Negative = liability
    # (credit/loan) balances owed, positive = asset balances held.
    current_balance_minor: Mapped[int] = mapped_column(BigInteger, default=0)

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
