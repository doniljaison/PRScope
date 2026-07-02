import uuid
import pytest

from app.workers.tasks import analyze_pr_task

def test_analyze_pr_task(mocker):
    # Mock GitHub Client and LLM Client to avoid actual network calls in tests
    mock_github = mocker.patch("app.workers.tasks.GitHubClient")
    mock_llm = mocker.patch("app.workers.tasks.LLMClient")
    
    # Mock the Redis publisher so it doesn't try to connect
    mocker.patch("app.workers.tasks.publish_status")
    
    from unittest.mock import AsyncMock
    
    # Setup async mock returns
    mock_github_instance = mock_github.return_value
    mock_github_instance.get_pr_diff = AsyncMock(return_value="fake diff")
    
    mock_llm_instance = mock_llm.return_value
    mock_llm_instance.analyze_diff = AsyncMock(return_value=[{"path": "file.py", "line": 1, "body": "test"}])
    
    pr_id = str(uuid.uuid4())
    result = analyze_pr_task(pr_id)
    
    # Assert the returned dictionary
    assert result["status"] == "success"
    assert result["pr_id"] == pr_id
    assert len(result["results"]) == 1
