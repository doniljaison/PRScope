"""
health.py — Health check endpoints.

GET /api/v1/health         → basic check (always fast)
GET /api/v1/health/detailed → checks real DB + Redis connectivity

Why two endpoints?
  - Load balancers hit /health every few seconds — keep it instant
  - /health/detailed is for you to debug startup issues
  - In prod, /health/detailed should be on an internal network only

Why is this in a router and not in main.py?
  - Separation of concerns: main.py is the factory, endpoints handle logic
  - Easier to test in isolation
  - As the project grows, you'd have auth.py, webhooks.py, etc. here
"""

import time

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import settings

router = APIRouter()

# Module-level start time — used to calculate uptime
# Set when this module is first imported (on app startup)
_START_TIME = time.time()


@router.get("/health")
async def health_check():
    """
    Basic health check.

    Returns immediately — no DB or external calls.
    Used by Docker health checks, load balancers, and monitoring.
    """
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "uptime_seconds": int(time.time() - _START_TIME),
    }


@router.get("/health/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """
    Detailed health check — actually connects to Redis AND Postgres.

    Notice `db: AsyncSession = Depends(get_db)` in the signature. FastAPI
    sees `Depends(get_db)`, calls that generator function, runs everything
    in get_db() up to its `yield`, and hands US the yielded session. When
    this route function returns, FastAPI resumes get_db() PAST the yield —
    that's where the commit/rollback/close logic lives (see app/api/deps.py).

    If either service is down, this returns {"status": "degraded"} but
    still with a 200 HTTP status. That's a deliberate choice — some teams
    prefer a 503 here instead. Both are defensible; just be consistent.
    """
    checks: dict[str, str] = {}
    overall_status = "ok"

    # ── Redis check ───────────────────────────────────────────────────────────
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pong = await r.ping()
        await r.aclose()
        checks["redis"] = "ok" if pong else "unexpected_response"
    except Exception as e:
        checks["redis"] = f"error: {type(e).__name__}"
        overall_status = "degraded"

    # ── Database check ────────────────────────────────────────────────────────
    try:
        # text("SELECT 1") — the simplest possible query. We don't care about
        # the result, only that the round trip succeeded. Using `text()`
        # (not raw string interpolation) is required by SQLAlchemy 2.0 to
        # mark this as a literal SQL expression rather than a typo.
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {type(e).__name__}"
        overall_status = "degraded"

    return {
        "status": overall_status,
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "uptime_seconds": int(time.time() - _START_TIME),
        "checks": checks,
    }
