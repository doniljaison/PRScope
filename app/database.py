"""
database.py — Async SQLAlchemy engine and session factory.

This file owns:
  - `Base`            — the class every ORM model inherits from
  - `engine`          — manages the connection pool to Postgres
  - `AsyncSessionLocal` — a factory that creates a new session per request

Why a session FACTORY and not one global session?
  A session wraps a single database transaction. If two concurrent requests
  shared one session, their queries and uncommitted changes would bleed into
  each other. Each request must get its OWN session — that's what the
  factory (and the `get_db` dependency in app/api/deps.py) gives us.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """
    Every ORM model (User, Repository, PullRequest, ...) inherits from this.

    SQLAlchemy collects every model's table definition into `Base.metadata`.
    Alembic reads that metadata to figure out what tables SHOULD exist when
    you run `alembic revision --autogenerate` — it diffs metadata against
    the actual database schema.
    """

    pass


# ── Engine ───────────────────────────────────────────────────────────────────
# The engine manages a POOL of connections — it does not open a new TCP
# connection to Postgres on every query. Connections are reused.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # When True, logs every SQL statement — great for learning, noisy in prod
    pool_pre_ping=True,  # "Ping" a pooled connection before using it — catches stale/dropped connections
    pool_size=5,  # Max number of persistent connections kept open
    max_overflow=10,  # Extra connections allowed temporarily under load spikes
)

# ── Session factory ──────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    # expire_on_commit=False matters: by default, SQLAlchemy "expires" all
    # attributes on commit, forcing a fresh DB hit next time you touch the
    # object. With FastAPI, you often return an ORM object AFTER commit
    # (e.g. inside a Pydantic response). With expire_on_commit=True, that
    # would trigger a surprise extra query — or worse, an error if the
    # session is already closed. False avoids both.
    autoflush=False,
    # autoflush=False means pending changes are NOT auto-sent to the DB
    # before every query. You flush explicitly when you need to. This makes
    # transaction boundaries predictable instead of implicit "magic".
)
