"""
test_health.py — Tests for the health check endpoints.

This is Day 1's test file. It's simple on purpose.
As the project grows, tests get more complex (mocking external services, etc.)

Run with:
  docker compose exec api pytest tests/ -v
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_health_returns_ok():
    """Basic health check should always return status: ok."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_root_endpoint():
    """Root endpoint should return app name and docs URL."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "PRScope"
    assert "/docs" in data["docs"]
