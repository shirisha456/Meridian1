from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshToken, User
from app.auth.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.core.config import Settings, get_settings
from app.errors import ConflictError, UnauthorizedError


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str


async def register_user(db: AsyncSession, email: str, password: str) -> User:
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise ConflictError("An account with this email already exists.")

    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        # Same error for "no such user" and "wrong password" — never let a
        # client distinguish account existence from credential correctness.
        raise UnauthorizedError("Incorrect email or password.")
    return user


async def issue_token_pair(
    db: AsyncSession,
    user: User,
    *,
    family_id: UUID | None = None,
    settings: Settings | None = None,
) -> TokenPair:
    settings = settings or get_settings()
    raw_refresh = generate_refresh_token()
    record = RefreshToken(
        user_id=user.id,
        family_id=family_id or uuid4(),
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(record)
    await db.commit()

    access_token = create_access_token(user.id, settings)
    return TokenPair(access_token=access_token, refresh_token=raw_refresh)


async def rotate_refresh_token(
    db: AsyncSession, raw_refresh_token: str, settings: Settings | None = None
) -> TokenPair:
    settings = settings or get_settings()
    token_hash = hash_refresh_token(raw_refresh_token)
    record = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    if record is None:
        raise UnauthorizedError("Invalid refresh token.")

    if record.revoked or record.used:
        # A token that's already revoked or already used being presented
        # again is the signature of a stolen refresh token being replayed
        # by an attacker after the legitimate client already rotated past
        # it — kill the whole family so every session descended from this
        # login is forced to re-authenticate, not just this one token.
        await _revoke_family(db, record.family_id)
        raise UnauthorizedError("Refresh token reuse detected; session revoked.")

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)  # SQLite test DB drops tzinfo on read
    if expires_at < datetime.now(UTC):
        raise UnauthorizedError("Refresh token expired.")

    record.used = True
    await db.commit()

    user = await db.get(User, record.user_id)
    return await issue_token_pair(db, user, family_id=record.family_id, settings=settings)


async def revoke_refresh_token(db: AsyncSession, raw_refresh_token: str) -> None:
    token_hash = hash_refresh_token(raw_refresh_token)
    record = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if record is not None:
        await _revoke_family(db, record.family_id)


async def _revoke_family(db: AsyncSession, family_id: UUID) -> None:
    result = await db.scalars(select(RefreshToken).where(RefreshToken.family_id == family_id))
    for token in result:
        token.revoked = True
    await db.commit()
