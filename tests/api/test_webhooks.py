"""
test_webhooks.py — Tests for the GitHub webhook endpoint.

Tests verify signature validation, idempotency (Redis SET NX),
payload parsing, and Celery task dispatching.
"""

import hashlib
import hmac
import json
import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient

from app.config import settings


@pytest.fixture(autouse=True)
def mock_analyze_pr_task(mocker):
    """Mock the Celery task to avoid actually firing it during HTTP tests."""
    return mocker.patch("app.api.v1.endpoints.webhooks.analyze_pr_task.delay")


@pytest.fixture(autouse=True)
def mock_redis_for_webhooks(mocker):
    """
    Mock the Redis dependency so idempotency checks don't need a real Redis.
    Returns True (new key) by default — individual tests can override.
    """
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)  # SET NX returns True = new
    mock_redis.aclose = AsyncMock()

    async def override_get_redis():
        yield mock_redis

    from app.api.deps import get_redis
    from app.main import app
    app.dependency_overrides[get_redis] = override_get_redis
    yield mock_redis
    # Cleanup is handled by the client fixture's clear()


def generate_signature(payload: bytes, secret: str) -> str:
    hash_obj = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256)
    return f"sha256={hash_obj.hexdigest()}"


def make_pr_payload(action: str = "opened") -> dict:
    """Build a realistic GitHub PR webhook payload."""
    return {
        "action": action,
        "pull_request": {
            "id": 987654321,
            "number": 42,
            "title": "Fix race condition",
            "html_url": "https://github.com/octocat/Hello-World/pull/42",
            "head": {"sha": "abc123def456", "ref": "fix/race"},
            "base": {"ref": "main"},
            "user": {"login": "octocat"},
        },
        "repository": {
            "id": 123456789,
            "full_name": "octocat/Hello-World",
        },
    }


@pytest.mark.asyncio
async def test_github_webhook_missing_signature(client: AsyncClient):
    response = await client.post("/api/v1/webhooks/github", json={})
    assert response.status_code == 401
    assert "Missing X-Hub-Signature-256" in response.json()["detail"]


@pytest.mark.asyncio
async def test_github_webhook_invalid_signature(client: AsyncClient):
    payload = b"{}"
    headers = {"X-Hub-Signature-256": "sha256=invalid_hash_here"}
    response = await client.post("/api/v1/webhooks/github", content=payload, headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid signature"


@pytest.mark.asyncio
async def test_github_webhook_missing_github_headers(client: AsyncClient):
    payload = b"{}"
    signature = generate_signature(payload, settings.GITHUB_WEBHOOK_SECRET)
    headers = {"X-Hub-Signature-256": signature}
    response = await client.post("/api/v1/webhooks/github", content=payload, headers=headers)
    assert response.status_code == 400
    assert "Missing GitHub headers" in response.json()["detail"]


@pytest.mark.asyncio
async def test_github_webhook_ignored_event(client: AsyncClient):
    payload_dict = {"action": "created"}
    payload = json.dumps(payload_dict).encode("utf-8")
    signature = generate_signature(payload, settings.GITHUB_WEBHOOK_SECRET)
    headers = {
        "X-Hub-Signature-256": signature,
        "X-GitHub-Event": "issues",
        "X-GitHub-Delivery": str(uuid.uuid4()),
    }

    response = await client.post("/api/v1/webhooks/github", content=payload, headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_github_webhook_pull_request_opened(client: AsyncClient, mock_analyze_pr_task):
    """Webhook with a valid PR payload should create DB records and dispatch task."""
    payload_dict = make_pr_payload("opened")
    payload = json.dumps(payload_dict).encode("utf-8")
    signature = generate_signature(payload, settings.GITHUB_WEBHOOK_SECRET)
    headers = {
        "X-Hub-Signature-256": signature,
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": str(uuid.uuid4()),
    }

    response = await client.post("/api/v1/webhooks/github", content=payload, headers=headers)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert "pr_id" in data

    # Verify the Celery task was dispatched with a real PR ID and commit SHA
    mock_analyze_pr_task.assert_called_once()
    call_args = mock_analyze_pr_task.call_args
    assert call_args[0][0] == data["pr_id"]  # pr_id_str
    assert call_args[0][1] == "abc123def456"  # commit_sha


@pytest.mark.asyncio
async def test_github_webhook_duplicate_delivery_is_skipped(
    client: AsyncClient, mock_analyze_pr_task, mock_redis_for_webhooks
):
    """Duplicate webhook deliveries (same X-GitHub-Delivery) should be skipped."""
    # Configure Redis to return False (key already exists = duplicate)
    mock_redis_for_webhooks.set = AsyncMock(return_value=False)

    payload_dict = make_pr_payload("opened")
    payload = json.dumps(payload_dict).encode("utf-8")
    signature = generate_signature(payload, settings.GITHUB_WEBHOOK_SECRET)
    headers = {
        "X-Hub-Signature-256": signature,
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "already-seen-delivery-id",
    }

    response = await client.post("/api/v1/webhooks/github", content=payload, headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "duplicate"

    # Task should NOT be dispatched for duplicates
    mock_analyze_pr_task.assert_not_called()
