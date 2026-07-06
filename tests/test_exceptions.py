"""
test_exceptions.py — Tests for the global exception handlers.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.exceptions import (
    PRScopeError,
    AuthenticationError,
    NotFoundError,
    GitHubAPIError,
    LLMParseError,
)


@pytest.fixture
async def test_client():
    """A minimal async client for testing exception handlers."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_error_response_has_consistent_format(test_client):
    """
    Hit a non-existent endpoint to verify FastAPI's built-in 404 handling.
    (Our custom handler only catches PRScopeError subclasses, not FastAPI HTTPExceptions.)
    """
    response = await test_client.get("/api/v1/this-does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500():
    """
    Verify that the unhandled exception handler returns a clean JSON 500
    instead of an HTML error page.
    """
    from app.core.exceptions import unhandled_exception_handler
    from unittest.mock import MagicMock

    # Create a mock request with a state object
    mock_request = MagicMock()
    mock_request.state.request_id = "test-req-123"

    response = await unhandled_exception_handler(
        mock_request, ValueError("something broke")
    )

    assert response.status_code == 500
    import json
    body = json.loads(response.body)
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert body["error"]["request_id"] == "test-req-123"
    assert "something broke" not in body["error"]["message"]  # Never leak internal details


@pytest.mark.asyncio
async def test_prscope_exception_handler():
    """Verify the PRScopeError handler returns the correct error envelope."""
    from app.core.exceptions import prscope_exception_handler
    from unittest.mock import MagicMock

    mock_request = MagicMock()
    mock_request.state.request_id = "req-456"

    exc = NotFoundError(message="Pull request not found", details={"pr_id": "abc"})
    response = await prscope_exception_handler(mock_request, exc)

    assert response.status_code == 404
    import json
    body = json.loads(response.body)
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "Pull request not found"
    assert body["error"]["details"] == {"pr_id": "abc"}
    assert body["error"]["request_id"] == "req-456"


@pytest.mark.asyncio
async def test_github_api_error_returns_502():
    """Verify GitHubAPIError is mapped to 502."""
    from app.core.exceptions import prscope_exception_handler
    from unittest.mock import MagicMock

    mock_request = MagicMock()
    mock_request.state.request_id = "req-789"

    exc = GitHubAPIError(message="GitHub returned 500")
    response = await prscope_exception_handler(mock_request, exc)

    assert response.status_code == 502
    import json
    body = json.loads(response.body)
    assert body["error"]["code"] == "GITHUB_API_ERROR"


@pytest.mark.asyncio
async def test_llm_parse_error_returns_502():
    """Verify LLMParseError is mapped to 502."""
    from app.core.exceptions import prscope_exception_handler
    from unittest.mock import MagicMock

    mock_request = MagicMock()
    mock_request.state.request_id = "req-llm"

    exc = LLMParseError(message="Invalid JSON from LLM")
    response = await prscope_exception_handler(mock_request, exc)

    assert response.status_code == 502
    import json
    body = json.loads(response.body)
    assert body["error"]["code"] == "LLM_PARSE_ERROR"
