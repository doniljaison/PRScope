"""
deps.py — Shared FastAPI dependencies.

A "dependency" in FastAPI is a function that runs BEFORE your route handler,
and whose return value gets injected into it via `Depends(...)`.

Dependencies:
  - get_db() — yields a database session per request
  - get_redis() — yields a Redis connection per request
  - get_current_user() — extracts and validates JWT, returns the User
"""

import uuid
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import decode_token
from app.database import AsyncSessionLocal
from app.models.user import User

# OAuth2PasswordBearer tells FastAPI/Swagger that endpoints expect a
# Bearer token in the Authorization header. The tokenUrl points to
# the login endpoint for Swagger's "Authorize" button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields a database session scoped to exactly one HTTP request.
    Commits on success, rolls back on exception.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """
    Yields a Redis connection scoped to one request.

    Using decode_responses=True so we get strings back, not bytes.
    """
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield r
    finally:
        await r.aclose()


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract the JWT from the Authorization header, decode it, and
    fetch the corresponding user from the database.

    This is the dependency that makes an endpoint "protected":
      @router.get("/me")
      async def me(user: User = Depends(get_current_user)):
          return user

    Raises 401 if:
      - No token provided
      - Token is expired or invalid
      - Token type is not "access"
      - User doesn't exist or is inactive
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_exception

    try:
        payload = decode_token(token)
        user_id_str: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")

        if user_id_str is None or token_type != "access":
            raise credentials_exception

        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception

    return user
