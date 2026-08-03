import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.accounts.router import router as accounts_router
from app.auth.router import router as auth_router
from app.budgets.router import router as budgets_router
from app.categories.router import router as categories_router
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal, engine
from app.core.kafka import stop_kafka_producer
from app.core.logging import configure_logging
from app.core.outbox_publisher import run_outbox_publisher_loop
from app.errors import register_exception_handlers
from app.goals.router import router as goals_router
from app.health.router import router as health_router
from app.institutions.router import router as institutions_router
from app.investments.router import router as investments_router
from app.networth.router import router as networth_router
from app.transactions.router import router as transactions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Skipped in tests — same reasoning as everywhere else background
    # work touches real infrastructure: tests exercise the publisher
    # function directly (test_outbox.py) rather than the always-on loop.
    publisher_task = None
    if not settings.is_test:
        publisher_task = asyncio.create_task(run_outbox_publisher_loop(AsyncSessionLocal))

    yield

    if publisher_task is not None:
        publisher_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await publisher_task
    await stop_kafka_producer()
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
    app.include_router(investments_router)
    app.include_router(institutions_router)

    return app


app = create_app()
