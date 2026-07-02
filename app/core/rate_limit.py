"""
rate_limit.py — Centralized SlowAPI Limiter instance.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

# Use Redis as the storage backend for rate limits so it works across multiple API instances.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL
)
