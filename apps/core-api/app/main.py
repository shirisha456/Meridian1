from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.accounts.router import router as accounts_router
from app.auth.router import router as auth_router
from app.budgets.router import router as budgets_router
from app.categories.router import router as categories_router
from app.core.config import get_settings
from app.core.db import engine
from app.core.logging import configure_logging
from app.errors import register_exception_handlers
from app.goals.router import router as goals_router
from app.health.router import router as health_router
from app.networth.router import router as networth_router
from app.transactions.router import router as transactions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    settings.assert_safe_for_environment()
    configure_logging(settings)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    register_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(accounts_router)
    app.include_router(transactions_router)
    app.include_router(categories_router)
    app.include_router(budgets_router)
    app.include_router(goals_router)
    app.include_router(networth_router)

    return app


app = create_app()
