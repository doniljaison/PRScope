"""Authentication endpoints — register, login, refresh, logout, me."""

import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_redis
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.schemas.auth import LoginRequest, MessageResponse, RefreshRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import (
    authenticate_user, register_user, revoke_refresh_token,
    store_refresh_token, validate_refresh_token,
)

router = APIRouter(prefix="/auth")


def _make_tokens(user: User) -> dict:
    token_data = {"sub": str(user.id)}
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer",
    }


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    redis_conn: aioredis.Redis = Depends(get_redis),
):
    """Create a new user account and return JWT tokens."""
    try:
        user = await register_user(db, user_data)
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    tokens = _make_tokens(user)
    await store_refresh_token(redis_conn, user.id, tokens["refresh_token"])
    return tokens


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis_conn: aioredis.Redis = Depends(get_redis),
):
    """Verify email + password, return JWT tokens."""
    user = await authenticate_user(db, login_data.email, login_data.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    tokens = _make_tokens(user)
    await store_refresh_token(redis_conn, user.id, tokens["refresh_token"])
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    refresh_data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis_conn: aioredis.Redis = Depends(get_redis),
):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    try:
        payload = decode_token(refresh_data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        user_id_str = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user_id = uuid.UUID(user_id_str)
    is_valid = await validate_refresh_token(redis_conn, user_id, refresh_data.refresh_token)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    tokens = _make_tokens(user)
    await store_refresh_token(redis_conn, user.id, tokens["refresh_token"])
    return tokens


@router.post("/logout", response_model=MessageResponse)
async def logout(
    user: User = Depends(get_current_user),
    redis_conn: aioredis.Redis = Depends(get_redis),
):
    """Revoke the user's refresh token."""
    await revoke_refresh_token(redis_conn, user.id)
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return user
