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
from fastapi import APIRouter

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
async def detailed_health_check():
    """
    Detailed health check — actually connects to Redis.
    (DB check will be added in Day 3 once SQLAlchemy is set up.)

    If Redis is down, this returns {"status": "degraded"}.
    The HTTP status code is still 200 — that's a design choice.
    Some teams use 503 for degraded state. Both are valid.
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

    # ── DB check (placeholder — filled in Day 3) ──────────────────────────────
    checks["database"] = "not_configured_yet"

    return {
        "status": overall_status,
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "uptime_seconds": int(time.time() - _START_TIME),
        "checks": checks,
    }
