"""
github.py — GitHub OAuth endpoints.

GET  /api/v1/auth/github          — redirect to GitHub authorize URL
GET  /api/v1/auth/github/callback — handle GitHub's redirect, issue JWT tokens

The OAuth flow:
  1. User clicks "Login with GitHub" → hits GET /auth/github
  2. We redirect them to GitHub with a random `state` param (stored in Redis)
  3. User authorizes on GitHub → GitHub redirects to /auth/github/callback
  4. We verify `state`, exchange the `code` for a GitHub access token
  5. Fetch the user's GitHub profile
  6. Create or link the user in our DB
  7. Return JWT tokens

The `state` parameter prevents CSRF: without it, an attacker could craft
a callback URL and trick a victim into linking the attacker's GitHub account.
"""

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
    exchange_code_for_token,
    get_authorize_url,
    get_github_user,
    upsert_user_from_github,
)

router = APIRouter(prefix="/auth")


@router.get("/github")
async def github_authorize(
    redis_conn: aioredis.Redis = Depends(get_redis),
):
    """
    Redirect the user to GitHub's OAuth authorize page.

    Generates a random state parameter and stores it in Redis with a
    short TTL (10 minutes). When GitHub redirects back, we verify the
    state matches to prevent CSRF attacks.
    """
    state = secrets.token_urlsafe(32)
    # Store state in Redis with 10-minute TTL
    await redis_conn.set(f"oauth_state:{state}", "1", ex=600)

    authorize_url = get_authorize_url(state)
    return RedirectResponse(url=authorize_url)


@router.get("/github/callback", response_model=TokenResponse)
async def github_callback(
    code: str = Query(..., description="Authorization code from GitHub"),
    state: str = Query(..., description="Anti-CSRF state parameter"),
    db: AsyncSession = Depends(get_db),
    redis_conn: aioredis.Redis = Depends(get_redis),
):
    """
    Handle GitHub's OAuth callback.

    Verifies the state, exchanges the code for a token, fetches the
    GitHub user profile, and creates/links the user in our database.
    Returns JWT tokens for our API.
    """
    # ── Verify state (CSRF protection) ───────────────────────────────────────
    stored = await redis_conn.get(f"oauth_state:{state}")
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state parameter",
        )
    # Delete the state so it can't be reused
    await redis_conn.delete(f"oauth_state:{state}")

    # ── Exchange code for GitHub access token ────────────────────────────────
    try:
        github_token = await exchange_code_for_token(code)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange code: {str(e)}",
        )

    # ── Fetch GitHub user profile ────────────────────────────────────────────
    try:
        github_user = await get_github_user(github_token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch GitHub user: {str(e)}",
        )

    # ── Create or link user ──────────────────────────────────────────────────
    user = await upsert_user_from_github(db, github_user, github_token)

    # ── Issue JWT tokens ─────────────────────────────────────────────────────
    token_data = {"sub": str(user.id)}
    tokens = {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer",
    }
    await store_refresh_token(redis_conn, user.id, tokens["refresh_token"])

    return tokens
