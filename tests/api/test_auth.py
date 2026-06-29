"""
test_auth.py — Tests for the authentication endpoints.

Tests the full JWT auth flow: register → login → me → refresh → logout.
Also tests error cases: duplicate email, wrong password, expired token.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Registration with a new email should return tokens."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "newuser@test.com", "password": "strongpass123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Registering with an already-used email should return 409."""
    payload = {"email": "duplicate@test.com", "password": "pass123"}
    # First registration succeeds
    resp1 = await client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    # Second registration with same email fails
    resp2 = await client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Login with valid credentials should return tokens."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login@test.com", "password": "mypassword"},
    )

    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@test.com", "password": "mypassword"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Login with wrong password should return 401."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpass@test.com", "password": "correctpass"},
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@test.com", "password": "wrongpass"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_email(client: AsyncClient):
    """Login with an email that doesn't exist should return 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.com", "password": "anything"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_token(client: AsyncClient):
    """GET /me with a valid access token should return the user."""
    # Register and get token
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "me@test.com", "password": "pass123"},
    )
    token = reg_resp.json()["access_token"]

    # Access protected endpoint
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@test.com"
    assert "id" in data
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient):
    """GET /me without a token should return 401."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_invalid_token(client: AsyncClient):
    """GET /me with a garbage token should return 401."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_flow(client: AsyncClient):
    """Refreshing with a valid refresh token should return new tokens."""
    # Register
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "refresh@test.com", "password": "pass123"},
    )
    refresh_token = reg_resp.json()["refresh_token"]

    # Refresh
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client: AsyncClient):
    """After logout, the refresh token should be invalid."""
    # Register
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "logout@test.com", "password": "pass123"},
    )
    tokens = reg_resp.json()

    # Logout
    logout_resp = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert logout_resp.status_code == 200

    # Try to refresh — should fail because token was revoked
    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_resp.status_code == 401
