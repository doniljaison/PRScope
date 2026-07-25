"""Health check endpoints — basic and detailed (DB + Redis)."""

import time

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import settings

router = APIRouter()
_START_TIME = time.time()


@router.get("/health")
async def health_check():
    """Basic health check — no external calls."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "uptime_seconds": int(time.time() - _START_TIME),
    }


@router.get("/health/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """Detailed health check — verifies DB and Redis connectivity."""
    checks: dict[str, str] = {}
    overall_status = "ok"

    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pong = await r.ping()
        await r.aclose()
        checks["redis"] = "ok" if pong else "unexpected_response"
    except Exception as e:
        checks["redis"] = f"error: {type(e).__name__}"
        overall_status = "degraded"

    try:
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
