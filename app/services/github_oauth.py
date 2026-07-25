"""GitHub OAuth 2.0 service — authorize, token exchange, user upsert."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.encryption import encrypt_token
from app.models.user import User

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_API_URL = "https://api.github.com/user"


def get_authorize_url(state: str) -> str:
    """Build the GitHub OAuth authorize URL with CSRF state parameter."""
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
        "scope": "read:user user:email repo",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GITHUB_AUTHORIZE_URL}?{query}"


async def exchange_code_for_token(code: str) -> str:
    """Exchange the authorization code for a GitHub access token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GITHUB_TOKEN_URL,
            json={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

    if "error" in data:
        raise ValueError(f"GitHub OAuth error: {data['error_description']}")
    return data["access_token"]


async def get_github_user(access_token: str) -> dict:
    """Fetch the authenticated user's GitHub profile."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GITHUB_USER_API_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        response.raise_for_status()
        return response.json()


async def upsert_user_from_github(
    db: AsyncSession, github_user: dict, access_token: str,
) -> User:
    """Create or update a user from GitHub OAuth data.

    Handles three cases:
    1. User with this github_id exists → update token
    2. User with this email exists (password-registered) → link GitHub
    3. New user → create account (no password)
    """
    github_id = github_user["id"]
    email = github_user.get("email") or f"{github_user['login']}@github.noemail"
    github_username = github_user["login"]
    avatar_url = github_user.get("avatar_url", "")

    result = await db.execute(select(User).where(User.github_id == github_id))
    user = result.scalar_one_or_none()

    if user:
        user.github_access_token = encrypt_token(access_token)
        user.avatar_url = avatar_url
        await db.flush()
        return user

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user:
        user.github_id = github_id
        user.github_username = github_username
        user.github_access_token = encrypt_token(access_token)
        user.avatar_url = avatar_url
        await db.flush()
        return user

    user = User(
        email=email, hashed_password="",
        github_id=github_id, github_username=github_username,
        github_access_token=encrypt_token(access_token), avatar_url=avatar_url,
    )
    db.add(user)
    await db.flush()
    return user
