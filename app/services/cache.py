"""
cache.py — Redis cache-aside helper.

Provides a simple, consistent interface for caching arbitrary JSON-serializable
data in Redis. This module implements the "cache-aside" (lazy-loading) pattern:

  1. Check cache first → return if hit
  2. On miss → fetch from source, write to cache, return
  3. Invalidate explicitly when data changes

Why cache-aside and not write-through?
  - We don't control GitHub's data. We can't guarantee our cache stays in sync
    with GitHub's state. Cache-aside with short TTLs is the pragmatic choice.
  - For our own data (analysis results), we cache on write since we control both sides.

All keys are prefixed with "prscope:" to avoid collisions in a shared Redis instance.
"""

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level async Redis client — shared across the app.
# This is safe because redis.asyncio.Redis is designed for concurrent use.
_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    """Lazy-initialize and return the module-level Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,  # Return strings instead of bytes
        )
    return _redis_client


# ── Public API ────────────────────────────────────────────────────────────────

async def cache_get(key: str) -> Any | None:
    """
    Retrieve a value from Redis cache.

    Returns the deserialized Python object, or None if the key doesn't exist.
    """
    r = _get_redis()
    prefixed_key = f"prscope:{key}"

    try:
        raw = await r.get(prefixed_key)
        if raw is None:
            logger.debug(f"Cache MISS: {prefixed_key}")
            return None

        logger.debug(f"Cache HIT: {prefixed_key}")
        return json.loads(raw)

    except Exception as e:
        # Cache failures should NEVER break the app.
        # Log and return None — the caller falls through to the real source.
        logger.warning(f"Cache GET failed for {prefixed_key}: {e}")
        return None


async def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> bool:
    """
    Store a JSON-serializable value in Redis with a TTL.

    Args:
        key: The cache key (will be prefixed with "prscope:")
        value: Any JSON-serializable Python object
        ttl_seconds: Time-to-live in seconds (default: 5 minutes)

    Returns:
        True if the value was stored successfully, False otherwise.
    """
    r = _get_redis()
    prefixed_key = f"prscope:{key}"

    try:
        serialized = json.dumps(value)
        await r.set(prefixed_key, serialized, ex=ttl_seconds)
        logger.debug(f"Cache SET: {prefixed_key} (TTL={ttl_seconds}s)")
        return True

    except Exception as e:
        logger.warning(f"Cache SET failed for {prefixed_key}: {e}")
        return False


async def cache_delete(key: str) -> bool:
    """
    Remove a key from the cache.

    Useful for explicit invalidation — e.g., when a PR is updated,
    delete its cached data so the next read fetches fresh data.

    Returns:
        True if the key was deleted, False otherwise.
    """
    r = _get_redis()
    prefixed_key = f"prscope:{key}"

    try:
        result = await r.delete(prefixed_key)
        logger.debug(f"Cache DELETE: {prefixed_key} (deleted={result})")
        return result > 0

    except Exception as e:
        logger.warning(f"Cache DELETE failed for {prefixed_key}: {e}")
        return False


async def cache_exists(key: str) -> bool:
    """Check if a key exists in the cache without retrieving its value."""
    r = _get_redis()
    prefixed_key = f"prscope:{key}"

    try:
        return bool(await r.exists(prefixed_key))
    except Exception as e:
        logger.warning(f"Cache EXISTS failed for {prefixed_key}: {e}")
        return False
