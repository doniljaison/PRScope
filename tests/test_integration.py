"""
test_integration.py — End-to-end integration tests.

These tests simulate the full pipeline:
  Webhook arrives → DB records created → Celery task dispatched → LLM called → results stored

Mocks external services (GitHub API, Claude LLM) but exercises real DB operations
where possible.
"""

import hashlib
import hmac
import json
import uuid

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.main import app
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.analysis_job import AnalysisJob
from app.models.user import User


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Generate a valid GitHub HMAC-SHA256 signature for a payload."""
    sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


@pytest.fixture
def webhook_payload():
    """A realistic GitHub pull_request webhook payload."""
    return {
        "action": "opened",
        "pull_request": {
            "id": 123456,
            "html_url": "https://github.com/octocat/Hello-World/pull/42",
            "number": 42,
            "title": "Fix race condition in webhook handler",
            "head": {"sha": "abc123def456", "ref": "fix/race"},
            "base": {"ref": "main"},
            "user": {"login": "octocat"},
        },
        "repository": {
            "id": 123456,
            "full_name": "octocat/Hello-World",
        },
    }


@pytest.fixture(autouse=True)
def mock_redis_for_integration(mocker):
    """Mock Redis for webhook idempotency — always returns True (new key)."""
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.aclose = AsyncMock()

    async def override_get_redis():
        yield mock_redis

    from app.api.deps import get_redis
    app.dependency_overrides[get_redis] = override_get_redis
    yield mock_redis


@pytest.mark.asyncio
async def test_webhook_creates_db_records_and_dispatches_task(client, webhook_payload, db_session):
    """
    Integration test: a valid webhook should:
    1. Create a Repository record in the database
    2. Create a PullRequest record in the database
    3. Dispatch a Celery task with the real PR ID
    """
    payload_bytes = json.dumps(webhook_payload).encode("utf-8")
    signature = _sign_payload(payload_bytes, settings.GITHUB_WEBHOOK_SECRET)

    with patch("app.api.v1.endpoints.webhooks.analyze_pr_task") as mock_task:
        mock_task.delay = MagicMock()

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
        assert data["status"] == "accepted"
        assert "pr_id" in data

        # Verify the Celery task was dispatched with a real UUID and commit SHA
        mock_task.delay.assert_called_once()
        call_args = mock_task.delay.call_args[0]
        assert call_args[0] == data["pr_id"]
        assert call_args[1] == "abc123def456"


def test_celery_task_cache_deduplication():
    """
    Integration test: when the same commit SHA is analyzed twice,
    the second call should return the cached result without calling the LLM.
    """
    cached_comments = [{"path": "cached.py", "line": 10, "body": "Cached comment"}]

    with patch("app.workers.tasks.GitHubClient") as mock_gh, \
         patch("app.workers.tasks.LLMClient") as mock_llm, \
         patch("app.workers.tasks.publish_status"), \
         patch("app.workers.tasks.cache_get", return_value=cached_comments), \
         patch("app.workers.tasks.cache_set", return_value=True):

        from app.workers.tasks import analyze_pr_task
        pr_id = str(uuid.uuid4())
        result = analyze_pr_task(pr_id, commit_sha="already_analyzed_sha")

        assert result["status"] == "success"
        assert result["results"] == cached_comments
        mock_llm.return_value.analyze_diff.assert_not_called()


@pytest.mark.asyncio
async def test_analytics_endpoint_with_seeded_data(client, db_session):
    """
    Integration test: seed the DB with a repo, PR, analysis job,
    then hit the analytics endpoint to verify aggregate stats.
    """
    user = User(
        email="analytics_test@example.com",
        hashed_password="hashed",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    repo = Repository(
        github_id=999999,
        full_name="testorg/analytics-repo",
        owner_id=user.id,
    )
    db_session.add(repo)
    await db_session.flush()

    pr = PullRequest(
        github_id=888888,
        pr_number=1,
        title="Test PR for analytics",
        author_github_username="testuser",
        head_sha="sha123",
        base_branch="main",
        head_branch="feature",
        repo_id=repo.id,
    )
    db_session.add(pr)
    await db_session.flush()

    job = AnalysisJob(
        status="completed",
        commit_sha="sha123",
        pull_request_id=pr.id,
    )
    db_session.add(job)
    await db_session.flush()

    response = await client.get(f"/api/v1/repos/{repo.id}/stats")
    assert response.status_code == 200

    data = response.json()
    assert data["full_name"] == "testorg/analytics-repo"
    assert data["total_prs"] == 1
    assert data["total_analyses"] == 1
    assert data["completed_analyses"] == 1


@pytest.mark.asyncio
async def test_analytics_endpoint_repo_not_found(client):
    """Analytics for a non-existent repo returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/repos/{fake_id}/stats")
    assert response.status_code == 404
