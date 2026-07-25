"""GitHub OAuth endpoints — authorize redirect and callback handler."""

import secrets

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis
from app.core.security import create_access_token, create_refresh_token
from app.schemas.auth import TokenResponse
from app.services.auth_service import store_refresh_token
from app.services.github_oauth import (
    exchange_code_for_token, get_authorize_url,
    get_github_user, upsert_user_from_github,
)

router = APIRouter(prefix="/auth")


@router.get("/github")
async def github_authorize(redis_conn: aioredis.Redis = Depends(get_redis)):
    """Redirect to GitHub's OAuth authorize page with CSRF state."""
    state = secrets.token_urlsafe(32)
    await redis_conn.set(f"oauth_state:{state}", "1", ex=600)
    return RedirectResponse(url=get_authorize_url(state))


@router.get("/github/callback", response_model=TokenResponse)
async def github_callback(
    code: str = Query(..., description="Authorization code from GitHub"),
    state: str = Query(..., description="Anti-CSRF state parameter"),
    db: AsyncSession = Depends(get_db),
    redis_conn: aioredis.Redis = Depends(get_redis),
):
    """Handle GitHub's OAuth callback — verify state, exchange code, issue JWTs."""
    stored = await redis_conn.get(f"oauth_state:{state}")
    if stored is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OAuth state parameter")
    await redis_conn.delete(f"oauth_state:{state}")

    try:
        github_token = await exchange_code_for_token(code)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to exchange code: {e}")

    try:
        github_user = await get_github_user(github_token)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to fetch GitHub user: {e}")

    user = await upsert_user_from_github(db, github_user, github_token)

    token_data = {"sub": str(user.id)}
    tokens = {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer",
    }
    await store_refresh_token(redis_conn, user.id, tokens["refresh_token"])
    return tokens
