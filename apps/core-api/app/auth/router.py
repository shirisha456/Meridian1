import redis.asyncio as redis
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.deps import get_current_user
from app.auth.models import User
from app.auth.schemas import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    WsTicketResponse,
)
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.redis import get_redis
from app.core.ws_tickets import TICKET_TTL_SECONDS, issue_ticket
from app.errors import UnauthorizedError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "meridian_refresh_token"
# Scoped to the auth prefix (not "/") so the refresh token — the one that
# can mint new access tokens — isn't sent on every unrelated API request.
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, refresh_token: str, settings: Settings) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=AuthResponse)
async def register(
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    user = await service.register_user(db, body.email, body.password)
    tokens = await service.issue_token_pair(db, user, settings=settings)
    _set_refresh_cookie(response, tokens.refresh_token, settings)
    return AuthResponse(access_token=tokens.access_token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    user = await service.authenticate_user(db, body.email, body.password)
    tokens = await service.issue_token_pair(db, user, settings=settings)
    _set_refresh_cookie(response, tokens.refresh_token, settings)
    return AuthResponse(access_token=tokens.access_token, user=UserResponse.model_validate(user))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh is None:
        raise UnauthorizedError("No refresh token provided.")

    tokens = await service.rotate_refresh_token(db, raw_refresh, settings=settings)
    _set_refresh_cookie(response, tokens.refresh_token, settings)
    return TokenResponse(access_token=tokens.access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> None:
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh is not None:
        await service.revoke_refresh_token(db, raw_refresh)
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.post("/ws-ticket", response_model=WsTicketResponse)
async def create_ws_ticket(
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> WsTicketResponse:
    """A short-lived, single-use ticket for the WebSocket handshake
    (app/notifications/router.py) — browsers can't set a custom
    Authorization header on a WS connection, so *something* has to go in
    the URL. Putting the long-lived access token there (the reference
    implementation's approach) means it can end up in server/proxy
    access logs; a 30-second, single-use ticket meaningfully narrows
    that exposure instead of eliminating the constraint."""
    ticket = await issue_ticket(redis_client, current_user.id)
    return WsTicketResponse(ticket=ticket, expires_in_seconds=TICKET_TTL_SECONDS)
