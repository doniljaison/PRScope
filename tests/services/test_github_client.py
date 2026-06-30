import httpx
import pytest
import respx
from tenacity import RetryError

from app.services.github_client import GitHubAPIError, GitHubClient, GitHubRateLimitError

@pytest.fixture
def github_client():
    client = GitHubClient(access_token="fake_token")
    yield client
    # The actual code closes the client, but for testing we can just let it go out of scope,
    # or explicitly close it if we want strict resource management.

@pytest.mark.asyncio
async def test_get_pull_request_success(github_client):
    repo = "octocat/Hello-World"
    pr_number = 1
    
    with respx.mock(base_url="https://api.github.com") as respx_mock:
        route = respx_mock.get(f"/repos/{repo}/pulls/{pr_number}").mock(
            return_value=httpx.Response(200, json={"id": 12345, "title": "Test PR"})
        )
        
        pr_data = await github_client.get_pull_request(repo, pr_number)
        
        assert route.called
        assert pr_data["id"] == 12345
        assert pr_data["title"] == "Test PR"

@pytest.mark.asyncio
async def test_get_pr_diff_success(github_client):
    repo = "octocat/Hello-World"
    pr_number = 1
    
    with respx.mock(base_url="https://api.github.com") as respx_mock:
        route = respx_mock.get(f"/repos/{repo}/pulls/{pr_number}").mock(
            return_value=httpx.Response(200, text="--- a/file.txt\n+++ b/file.txt\n@@ -1,1 +1,2 @@")
        )
        
        diff = await github_client.get_pr_diff(repo, pr_number)
        
        assert route.called
        assert "--- a/file.txt" in diff
        # Verify the custom Accept header was sent
        request = route.calls.last.request
        assert request.headers["accept"] == "application/vnd.github.v3.diff"

@pytest.mark.asyncio
async def test_github_rate_limit_error(github_client):
    repo = "octocat/Hello-World"
    pr_number = 1
    
    with respx.mock(base_url="https://api.github.com") as respx_mock:
        respx_mock.get(f"/repos/{repo}/pulls/{pr_number}").mock(
            return_value=httpx.Response(
                403, 
                headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1234567890"},
                json={"message": "API rate limit exceeded"}
            )
        )
        
        with pytest.raises(GitHubRateLimitError):
            await github_client.get_pull_request(repo, pr_number)

@pytest.mark.asyncio
async def test_github_retry_on_503(github_client):
    repo = "octocat/Hello-World"
    pr_number = 1
    
    with respx.mock(base_url="https://api.github.com") as respx_mock:
        # Fail first two times with 503, succeed on the third
        route = respx_mock.get(f"/repos/{repo}/pulls/{pr_number}")
        route.side_effect = [
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, json={"id": 12345}),
        ]
        
        pr_data = await github_client.get_pull_request(repo, pr_number)
        
        assert route.call_count == 3
        assert pr_data["id"] == 12345

@pytest.mark.asyncio
async def test_github_api_error_no_retry(github_client):
    repo = "octocat/Hello-World"
    pr_number = 1
    
    with respx.mock(base_url="https://api.github.com") as respx_mock:
        # A 404 should NOT trigger a retry, it should fail immediately
        route = respx_mock.get(f"/repos/{repo}/pulls/{pr_number}").mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )
        
        with pytest.raises(GitHubAPIError):
            await github_client.get_pull_request(repo, pr_number)
            
        assert route.call_count == 1
