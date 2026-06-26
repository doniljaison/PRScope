"""
env.py — Alembic's entry point. Runs every time you execute
`alembic revision --autogenerate` or `alembic upgrade head`.

Two jobs:
  1. Tell Alembic which DB to connect to (reuse our app's settings — never
     duplicate connection config in two places)
  2. Tell Alembic about our models (`target_metadata`), so --autogenerate
     can compare "what tables does the code say should exist" against
     "what tables actually exist in the DB" and write the diff for you.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.config import settings
from app.database import Base

# ── Import every model file here ────────────────────────────────────────────
# This import looks unused (no `User.something` is called below) but it is
# NOT unused — importing the module registers the User class with
# Base.metadata as a side effect of the class body running. If you add a
# new model file and forget to import it here, --autogenerate will silently
# produce an EMPTY migration for it. This is one of the most common Alembic
# gotchas — now you know about it on Day 2 instead of discovering it the
# hard way on Day 12.
from app.models.user import User  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Inject our real DB URL (built from .env via pydantic-settings) into
# Alembic's config object, overriding whatever placeholder is in alembic.ini.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """
    Generates raw SQL without ever connecting to a database.
    Useful for handing a DBA a .sql file to review before running it on
    production. We don't use this path day-to-day, but Alembic requires
    this function to exist.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    The path actually used: connects to Postgres asynchronously (same
    asyncpg driver the app itself uses) and applies migrations.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # NullPool = don't keep connections open after this script exits.
        # A migration run is a one-off — pooling would be pointless overhead.
    )

    async with connectable.connect() as connection:
        # Alembic's migration internals are synchronous. `run_sync` bridges
        # our async connection into that sync world for the duration of
        # the migration run.
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
