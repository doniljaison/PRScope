"""Auth service — registration, authentication, and refresh token management."""

import uuid

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


async def register_user(db: AsyncSession, user_data: UserCreate) -> User:
    """Create a new user with a hashed password."""
    user = User(email=user_data.email, hashed_password=hash_password(user_data.password))
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """Verify email + password. Returns User or None (no user enumeration)."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user


def _refresh_key(user_id: uuid.UUID) -> str:
    return f"refresh_token:{user_id}"


async def store_refresh_token(redis_conn: aioredis.Redis, user_id: uuid.UUID, token: str) -> None:
    """Store a refresh token in Redis with TTL."""
    await redis_conn.set(_refresh_key(user_id), token, ex=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)


async def validate_refresh_token(redis_conn: aioredis.Redis, user_id: uuid.UUID, token: str) -> bool:
    """Check if the stored refresh token matches."""
    stored = await redis_conn.get(_refresh_key(user_id))
    if stored is None:
        return False
    stored_str = stored if isinstance(stored, str) else stored.decode("utf-8")
    return stored_str == token


async def revoke_refresh_token(redis_conn: aioredis.Redis, user_id: uuid.UUID) -> None:
    """Delete the refresh token from Redis (logout)."""
    await redis_conn.delete(_refresh_key(user_id))
