"""
github_oauth.py — GitHub OAuth service layer.

Handles the OAuth 2.0 authorization code flow with GitHub:
  1. Generate the authorize URL (user clicks this to start)
  2. Exchange the authorization code for an access token
  3. Fetch the GitHub user profile
  4. Upsert the user in our database (create or link to existing)
"""

import uuid

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
    """
    Build the GitHub OAuth authorize URL.

    The `state` parameter is a random string that prevents CSRF attacks:
    we generate it, store it in Redis, and verify it when GitHub redirects
    back to us. If an attacker forges a callback, the state won't match.
    """
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
        "scope": "read:user user:email repo",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GITHUB_AUTHORIZE_URL}?{query}"


async def exchange_code_for_token(code: str) -> str:
    """
    Exchange the authorization code for a GitHub access token.

    GitHub sends the code to our callback URL. We send it back to GitHub
    along with our client secret to prove we're the app that initiated
    the flow. GitHub responds with an access token.
    """
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
    """
    Fetch the authenticated user's GitHub profile.

    Returns a dict with keys like: id, login, email, avatar_url, name.
    """
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
    db: AsyncSession,
    github_user: dict,
    access_token: str,
) -> User:
    """
    Create or update a user from GitHub OAuth data.

    Three scenarios:
    1. User with this github_id exists → update their token
    2. User with this email exists (registered with password) → link GitHub
    3. No existing user → create new account (no password)
    """
    github_id = github_user["id"]
    email = github_user.get("email") or f"{github_user['login']}@github.noemail"
    github_username = github_user["login"]
    avatar_url = github_user.get("avatar_url", "")

    # Check if we already have a user with this GitHub ID
    result = await db.execute(
        select(User).where(User.github_id == github_id)
    )
    user = result.scalar_one_or_none()

    if user:
        # Scenario 1: returning GitHub user — update token
        user.github_access_token = encrypt_token(access_token)
        user.avatar_url = avatar_url
        await db.flush()
        return user

    # Check if a user with this email already exists (password-registered)
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()

    if user:
        # Scenario 2: link GitHub to existing password account
        user.github_id = github_id
        user.github_username = github_username
        user.github_access_token = encrypt_token(access_token)
        user.avatar_url = avatar_url
        await db.flush()
        return user

    # Scenario 3: brand new user from GitHub (no password)
    user = User(
        email=email,
        hashed_password="",  # OAuth users don't have a password
        github_id=github_id,
        github_username=github_username,
        github_access_token=encrypt_token(access_token),
        avatar_url=avatar_url,
    )
    db.add(user)
    await db.flush()
    return user
