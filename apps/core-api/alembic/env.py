from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

# Model modules are imported here (not in app/core/db.py) purely so their
# tables register on Base.metadata before autogenerate runs. Each phase
# that adds a domain module adds its import below.
import app.accounts.models
import app.auth.models
import app.budgets.models
import app.categories.models
import app.goals.models
import app.investments.models
import app.networth.models
import app.transactions.models  # noqa: F401
from alembic import context
from app.core.config import get_settings
from app.core.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_database_url() -> str:
    # Alembic runs migrations as one-shot synchronous scripts; there's no
    # benefit to the async driver here, so we swap it for the sync one
    # (asyncpg -> psycopg) rather than wiring async support into Alembic
    # for no real gain. The app's runtime keeps using asyncpg.
    return get_settings().database_url.replace("+asyncpg", "+psycopg")


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _sync_database_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
