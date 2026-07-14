"""
test_edge_cases.py — Edge case tests for hardening.

Tests unusual inputs, boundary conditions, and error paths that
the happy-path tests don't cover. These are the scenarios that
break production systems.
"""

import hashlib
import hmac
import json
import uuid

import pytest
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.main import app


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


# ── Webhook Edge Cases ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_webhook_invalid_json_body(client):
    """Webhook with garbled body should return 400 even with valid signature."""
    garbled = b"this is not json at all {{{{"
    signature = _sign_payload(garbled, settings.GITHUB_WEBHOOK_SECRET)

    response = await client.post(
        "/api/v1/webhooks/github",
        content=garbled,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_webhook_ignores_non_pr_events(client):
    """Non-pull_request events (like push, issues) should be accepted but ignored."""
    payload = {"action": "completed", "check_suite": {"id": 123}}
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = _sign_payload(payload_bytes, settings.GITHUB_WEBHOOK_SECRET)

    with patch("app.api.v1.endpoints.webhooks.analyze_pr_task") as mock_task:
        response = await client.post(
            "/api/v1/webhooks/github",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "check_suite",
                "X-GitHub-Delivery": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "ignored"
        # Task should NOT be dispatched for non-PR events
        mock_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_ignores_closed_pr_action(client):
    """PR events with action 'closed' should be accepted but not trigger analysis."""
    payload = {
        "action": "closed",
        "pull_request": {"html_url": "https://github.com/test/repo/pull/1"},
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = _sign_payload(payload_bytes, settings.GITHUB_WEBHOOK_SECRET)

    with patch("app.api.v1.endpoints.webhooks.analyze_pr_task") as mock_task:
        response = await client.post(
            "/api/v1/webhooks/github",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "ignored"
        mock_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_empty_body_returns_401(client):
    """An empty body can't have a valid signature, should 401."""
    response = await client.post(
        "/api/v1/webhooks/github",
        content=b"",
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=invalid",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 401


# ── Auth Edge Cases ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_missing_email_field_rejected(client):
    """Registration without an email field should be rejected."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"password": "validpass123"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_missing_password_field_rejected(client):
    """Registration without a password field should be rejected."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_with_missing_fields(client):
    """Login without required fields returns 422."""
    response = await client.post("/api/v1/auth/login", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_access_protected_endpoint_with_expired_like_token(client):
    """A completely malformed token should return 401."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.real.jwt.token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_invalid_token(client):
    """Refreshing with a garbage token should fail."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "totally-fake-refresh-token"},
    )
    assert response.status_code == 401


# ── Health Edge Cases ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint_returns_valid_json(client):
    """Health endpoint should always return valid JSON with status field."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"


# ── Analytics Edge Cases ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analytics_with_invalid_uuid_format(client):
    """Analytics with a non-UUID repo_id should return 422."""
    response = await client.get("/api/v1/repos/not-a-uuid/stats")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_recent_analyses_limit_parameter(client, db_session):
    """The limit parameter should be respected."""
    from app.models.user import User
    from app.models.repository import Repository

    user = User(email="limit_test@example.com", hashed_password="h", is_active=True)
    db_session.add(user)
    await db_session.flush()

    repo = Repository(github_id=777777, full_name="testorg/limit-repo", owner_id=user.id)
    db_session.add(repo)
    await db_session.flush()

    response = await client.get(f"/api/v1/repos/{repo.id}/recent?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 5
