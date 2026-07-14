"""
test_integration.py — End-to-end integration tests.

These tests simulate the full pipeline:
  Webhook arrives → PR record created → Celery task dispatched → LLM called → results stored

Uses CELERY_TASK_ALWAYS_EAGER=True so tasks run synchronously during tests.
Mocks external services (GitHub API, Claude LLM) but exercises real DB operations.
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
            "html_url": "https://github.com/octocat/Hello-World/pull/42",
            "number": 42,
            "title": "Fix race condition in webhook handler",
            "head": {"sha": "abc123def456"},
            "base": {"ref": "main"},
            "user": {"login": "octocat"},
        },
        "repository": {
            "id": 123456,
            "full_name": "octocat/Hello-World",
        },
    }


@pytest.mark.asyncio
async def test_webhook_dispatches_celery_task(client, webhook_payload):
    """
    Integration test: a valid webhook with correct signature enqueues a Celery task.

    This verifies the full synchronous path:
    1. Webhook endpoint validates HMAC signature
    2. Webhook endpoint parses the PR payload
    3. Celery task is dispatched (mocked to verify it was called)
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
        # Verify the Celery task was actually dispatched
        mock_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_celery_task_runs_with_mocked_services():
    """
    Integration test: run the Celery task synchronously with mocked
    external services and verify it produces the expected result.
    """
    with patch("app.workers.tasks.GitHubClient") as mock_gh, \
         patch("app.workers.tasks.LLMClient") as mock_llm, \
         patch("app.workers.tasks.publish_status"), \
         patch("app.workers.tasks.cache_get", return_value=None), \
         patch("app.workers.tasks.cache_set", return_value=True):

        mock_gh_instance = mock_gh.return_value
        mock_gh_instance.get_pr_diff = AsyncMock(
            return_value="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new"
        )

        mock_llm_instance = mock_llm.return_value
        mock_llm_instance.analyze_diff = AsyncMock(return_value=[
            {"path": "file.py", "line": 1, "body": "Consider using a constant here."},
            {"path": "file.py", "line": 5, "body": "Missing error handling."},
        ])

        from app.workers.tasks import analyze_pr_task
        pr_id = str(uuid.uuid4())
        result = analyze_pr_task(pr_id, commit_sha="abc123def456")

        assert result["status"] == "success"
        assert result["pr_id"] == pr_id
        assert len(result["results"]) == 2
        assert result["results"][0]["body"] == "Consider using a constant here."


@pytest.mark.asyncio
async def test_celery_task_uses_cached_result_for_same_sha():
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
        # LLM should NOT have been called
        mock_llm.return_value.analyze_diff.assert_not_called()


@pytest.mark.asyncio
async def test_analytics_endpoint_with_seeded_data(client, db_session):
    """
    Integration test: seed the DB with a repo, PR, analysis job, and comments,
    then hit the analytics endpoint to verify aggregate stats.
    """
    # Seed a user
    user = User(
        email="analytics_test@example.com",
        hashed_password="hashed",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    # Seed a repository
    repo = Repository(
        github_id=999999,
        full_name="testorg/analytics-repo",
        owner_id=user.id,
    )
    db_session.add(repo)
    await db_session.flush()

    # Seed a pull request
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

    # Seed an analysis job
    job = AnalysisJob(
        status="completed",
        commit_sha="sha123",
        pull_request_id=pr.id,
    )
    db_session.add(job)
    await db_session.flush()

    # Hit the analytics endpoint
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
