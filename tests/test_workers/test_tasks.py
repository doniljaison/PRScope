"""
test_tasks.py — Tests for the Celery analyze_pr_task.

These tests mock external services (GitHub API, LLM, DB) to verify
the task logic in isolation. They run synchronously (no pytest-asyncio)
because the Celery task creates its own event loop.
"""

import uuid
from unittest.mock import patch, AsyncMock, MagicMock

from app.workers.tasks import analyze_pr_task


def test_analyze_pr_task_with_cached_result():
    """When analysis is cached, the LLM should not be called."""
    cached_comments = [{"path": "cached.py", "line": 10, "body": "Cached comment"}]

    with patch("app.workers.tasks.GitHubClient") as mock_gh, \
         patch("app.workers.tasks.LLMClient") as mock_llm, \
         patch("app.workers.tasks.publish_status"), \
         patch("app.workers.tasks.cache_get", return_value=cached_comments), \
         patch("app.workers.tasks.cache_set", return_value=True):

        pr_id = str(uuid.uuid4())
        result = analyze_pr_task(pr_id, commit_sha="already_analyzed_sha")

        assert result["status"] == "success"
        assert result["results"] == cached_comments
        # LLM should NOT have been called
        mock_llm.return_value.analyze_diff.assert_not_called()


def test_analyze_pr_task_pr_not_found():
    """When the PR doesn't exist in DB, the task should return an error."""
    with patch("app.workers.tasks.publish_status"), \
         patch("app.workers.tasks.cache_get", return_value=None), \
         patch("app.workers.tasks.cache_set", return_value=True), \
         patch("app.workers.tasks.get_worker_session_factory") as mock_factory:

        # Mock the DB session to return None for the PR lookup
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_factory.return_value = MagicMock(return_value=mock_session)

        pr_id = str(uuid.uuid4())
        result = analyze_pr_task(pr_id, commit_sha="sha123")

        assert result["status"] == "success"
        assert result["results"] == {"error": "PR not found"}
