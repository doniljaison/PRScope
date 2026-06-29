"""
auth_service.py — Business logic for authentication.

This layer sits between the API endpoints and the raw crypto utilities.
It handles:
  - User registration (hash + store)
  - Authentication (lookup + verify)
  - Refresh token management (store/validate/revoke in Redis)
"""

import uuid

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


async def register_user(db: AsyncSession, user_data: UserCreate) -> User:
    """
    Create a new user with a hashed password.

    Raises IntegrityError if email is already taken (handled by the endpoint).
    """
    user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> User | None:
    """
    Look up user by email and verify password.
    Returns the User if credentials are valid, None otherwise.

    Note: we don't distinguish between "email not found" and "wrong password"
    in the return value — this prevents user enumeration attacks (an attacker
    can't tell which emails are registered by observing different error messages).
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# ── Refresh token management (Redis) ────────────────────────────────────────
# We store refresh tokens in Redis with a TTL matching the token expiry.
# This lets us revoke tokens by deleting the Redis key (logout).
# Key format: "refresh_token:{user_id}"

def _refresh_key(user_id: uuid.UUID) -> str:
    return f"refresh_token:{user_id}"


async def store_refresh_token(
    redis_conn: aioredis.Redis,
    user_id: uuid.UUID,
    token: str,
) -> None:
    """Store a refresh token in Redis with TTL."""
    key = _refresh_key(user_id)
    ttl_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis_conn.set(key, token, ex=ttl_seconds)


async def validate_refresh_token(
    redis_conn: aioredis.Redis,
    user_id: uuid.UUID,
    token: str,
) -> bool:
    """Check if the refresh token in Redis matches the one provided."""
    key = _refresh_key(user_id)
    stored = await redis_conn.get(key)
    if stored is None:
        return False
    # Redis returns bytes, token is str
    stored_str = stored if isinstance(stored, str) else stored.decode("utf-8")
    return stored_str == token


async def revoke_refresh_token(
    redis_conn: aioredis.Redis,
    user_id: uuid.UUID,
) -> None:
    """Delete the refresh token from Redis (logout)."""
    key = _refresh_key(user_id)
    await redis_conn.delete(key)
