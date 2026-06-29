"""
test_github_oauth.py — Tests for the GitHub OAuth flow.

These tests mock the GitHub API calls since we don't want to hit
real GitHub during tests. We test:
  - The authorize redirect sends correct URL
  - The callback exchanges code, fetches user, creates/links user
  - Invalid state is rejected (CSRF protection)
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_github_authorize_redirects(client: AsyncClient):
    """GET /auth/github should return a redirect to GitHub."""
    response = await client.get(
        "/api/v1/auth/github",
        follow_redirects=False,
    )
    # Should be a redirect (307 or 302)
    assert response.status_code in (302, 307)
    location = response.headers.get("location", "")
    assert "github.com/login/oauth/authorize" in location
    assert "state=" in location


@pytest.mark.asyncio
async def test_github_callback_invalid_state(client: AsyncClient):
    """Callback with a state that wasn't set should return 400."""
    response = await client.get(
        "/api/v1/auth/github/callback",
        params={"code": "fake_code", "state": "invalid_state"},
    )
    assert response.status_code == 400
    assert "Invalid or expired" in response.json()["detail"]


@pytest.mark.asyncio
async def test_github_callback_success(client: AsyncClient):
    """
    Callback with valid state and mocked GitHub API should return tokens.
    """
    import redis.asyncio as aioredis
    from app.config import settings

    # Set up a valid state in Redis
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    state = "test_valid_state_123"
    await r.set(f"oauth_state:{state}", "1", ex=600)
    await r.aclose()

    mock_github_user = {
        "id": 12345678,
        "login": "testghuser",
        "email": "ghuser@example.com",
        "avatar_url": "https://avatars.githubusercontent.com/u/12345678",
        "name": "Test GitHub User",
    }

    with patch(
        "app.api.v1.endpoints.github.exchange_code_for_token",
        new_callable=AsyncMock,
        return_value="gho_fake_access_token",
    ), patch(
        "app.api.v1.endpoints.github.get_github_user",
        new_callable=AsyncMock,
        return_value=mock_github_user,
    ), patch(
        "app.services.github_oauth.encrypt_token",
        return_value="encrypted_fake_token",
    ):
        response = await client.get(
            "/api/v1/auth/github/callback",
            params={"code": "valid_code", "state": state},
        )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
