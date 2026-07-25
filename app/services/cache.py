"""Redis cache-aside helper with automatic key prefixing and TTL."""

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)
_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def cache_get(key: str) -> Any | None:
    """Retrieve a value from cache. Returns None on miss or error."""
    r = _get_redis()
    prefixed_key = f"prscope:{key}"
    try:
        raw = await r.get(prefixed_key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Cache GET failed for {prefixed_key}: {e}")
        return None


async def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> bool:
    """Store a JSON-serializable value with TTL. Returns True on success."""
    r = _get_redis()
    prefixed_key = f"prscope:{key}"
    try:
        await r.set(prefixed_key, json.dumps(value), ex=ttl_seconds)
        return True
    except Exception as e:
        logger.warning(f"Cache SET failed for {prefixed_key}: {e}")
        return False


async def cache_delete(key: str) -> bool:
    """Remove a key from cache. Returns True if deleted."""
    r = _get_redis()
    prefixed_key = f"prscope:{key}"
    try:
        result = await r.delete(prefixed_key)
        return result > 0
    except Exception as e:
        logger.warning(f"Cache DELETE failed for {prefixed_key}: {e}")
        return False


async def cache_exists(key: str) -> bool:
    """Check if a key exists in cache."""
    r = _get_redis()
    try:
        return bool(await r.exists(f"prscope:{key}"))
    except Exception as e:
        logger.warning(f"Cache EXISTS failed: {e}")
        return False
