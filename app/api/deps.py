"""
deps.py — Shared FastAPI dependencies.

A "dependency" in FastAPI is a function that runs BEFORE your route handler,
and whose return value gets injected into it via `Depends(...)`.

Today: just the database session dependency.
Later (Week 1, Day 5-6): get_current_user (JWT auth) will live here too —
every protected route will declare `user: User = Depends(get_current_user)`.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields a database session scoped to exactly one HTTP request.

    Usage in a route:
        @router.get("/something")
        async def handler(db: AsyncSession = Depends(get_db)):
            result = await db.execute(...)

    The flow:
      1. FastAPI calls this function when a request comes in
      2. `async with AsyncSessionLocal() as session` opens a new session
      3. We `yield` it — this is where your route handler's code actually runs
      4. If the route handler finishes WITHOUT raising → we commit
      5. If the route handler raises an exception → we roll back, then re-raise
      6. The `async with` block closes the session either way

    This means you almost never call db.commit() yourself inside a route —
    it happens automatically here, in exactly one place.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
