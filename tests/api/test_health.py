"""
test_health.py — Tests for the health check endpoints.

Run with:
  docker compose exec api pytest tests/ -v
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok(client: AsyncClient):
    """Basic health check should always return status: ok."""
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_detailed_health_checks_database_and_redis(client: AsyncClient):
    """
    Detailed health check should report BOTH services as ok, since this
    test runs inside the docker compose network where db and redis are
    both real, running containers.
    """
    response = await client.get("/api/v1/health/detailed")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["redis"] == "ok"


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Root endpoint should return app name and docs URL."""
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "PRScope"
    assert "/docs" in data["docs"]
