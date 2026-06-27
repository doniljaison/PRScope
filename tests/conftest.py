"""
conftest.py — Shared pytest fixtures.

Fixtures defined here are available to ALL test files automatically.
No import needed — pytest discovers them by convention.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """An async HTTP client wired directly to our FastAPI app — no network involved."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    A database session for tests that gets thrown away afterward.

    IMPORTANT: We create a fresh engine per test to avoid the
    "attached to a different loop" error. The module-level engine in
    app/database.py gets bound to the app's event loop, which is different
    from the test event loop. Creating a test-scoped engine ensures the
    connection pool lives in the correct event loop.

    The pattern: yield the session, and on teardown call rollback() instead
    of commit(). As long as your TEST CODE never calls db_session.commit()
    itself, nothing it does is ever permanently written to Postgres —
    rollback() discards the whole transaction.

    In your tests: use `await db_session.flush()`, never `.commit()`.
    """
    # Create a test-scoped engine to avoid event loop mismatch
    test_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()
    await test_engine.dispose()
