import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import Settings, get_settings

# OWASP Password Storage Cheat Sheet's Argon2id recommendation for a
# memory-constrained deployment: m=19 MiB, t=2, p=1. Deliberately set
# rather than left at argon2-cffi's own library defaults, so the cost is a
# conscious choice tied to this app's threat model rather than an
# incidental library version bump. Re-benchmark against real deploy
# hardware (target: ~250-500ms per hash) before treating these as final.
_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(user_id: UUID, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def generate_refresh_token() -> str:
    # Opaque, high-entropy — deliberately never a JWT. A JWT refresh token
    # would carry claims we'd have to trust before checking the DB; an
    # opaque token forces every refresh through the token_hash lookup,
    # which is what makes rotation/reuse-detection/revocation possible.
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()
