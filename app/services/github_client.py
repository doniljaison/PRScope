"""
github_client.py — A dedicated client for interacting with the GitHub API.
Handles authentication, rate-limit checking, retries using tenacity, and
Redis caching of responses to reduce API rate limit consumption.
"""
import logging
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.services.cache import cache_get, cache_set
from app.core.exceptions import GitHubAPIError, GitHubRateLimitError

logger = logging.getLogger(__name__)

def log_attempt_number(retry_state):
    logger.warning(f"Retrying GitHub API call: attempt {retry_state.attempt_number}")

class GitHubClient:
    def __init__(self, access_token: str | None = None):
        """
        Initialize the GitHub API client.
        
        Args:
            access_token (str | None): A GitHub OAuth token or personal access token.
                                     If none is provided, requests will be unauthenticated
                                     (and strictly rate-limited).
        """
        self.base_url = "https://api.github.com"
        
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
            
        # We create a persistent httpx AsyncClient for the lifetime of this GitHubClient instance.
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=10.0
        )

    async def close(self):
        """Close the underlying HTTPX client."""
        await self.client.aclose()

    # We use tenacity for automatic retries.
    # We retry only on HTTP 429 (Rate Limit), 500, 502, 503, 504.
    # wait_exponential gives us: 2^x * 1s (e.g. 2s, 4s, 8s...) + jitter to avoid thundering herd.
    @retry(
        retry=retry_if_exception_type((httpx.RequestError, GitHubRateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        after=log_attempt_number,
        reraise=True
    )
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """
        Internal method to make HTTP requests and handle GitHub rate-limiting/errors.
        """
        try:
            response = await self.client.request(method, endpoint, **kwargs)
        except httpx.RequestError as e:
            logger.error(f"Network error while calling GitHub API: {e}")
            raise

        # Check rate limits
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) == 0:
            reset_time = response.headers.get("X-RateLimit-Reset", "unknown")
            logger.error(f"GitHub Rate Limit Exceeded! Resets at {reset_time}")
            raise GitHubRateLimitError("GitHub API rate limit exceeded.")

        # If it's a 429 (Too Many Requests) or 5xx server error, we want tenacity to retry it.
        # We can either raise an exception for tenacity to catch, or return and let the caller handle.
        # It's better to raise an exception here so tenacity handles the backoff automatically.
        if response.status_code == 429:
            raise GitHubRateLimitError("Received 429 Too Many Requests from GitHub.")
        elif response.status_code >= 500:
            raise httpx.RequestError(f"GitHub Server Error: {response.status_code}", request=response.request)
            
        if not response.is_success:
            logger.error(f"GitHub API Error [{response.status_code}]: {response.text}")
            raise GitHubAPIError(f"GitHub API returned {response.status_code}: {response.text}")

        return response

    async def get_pull_request(self, repo_full_name: str, pr_number: int) -> dict[str, Any]:
        """
        Fetch details of a specific Pull Request.
        Results are cached in Redis for 5 minutes to reduce API rate limit consumption.
        """
        cache_key = f"github:pr:{repo_full_name}:{pr_number}"
        cached = await cache_get(cache_key)
        if cached is not None:
            logger.info(f"Returning cached PR data for {repo_full_name}#{pr_number}")
            return cached

        endpoint = f"/repos/{repo_full_name}/pulls/{pr_number}"
        response = await self._make_request("GET", endpoint)
        data = response.json()

        # Cache for 5 minutes — PR metadata doesn't change every second
        await cache_set(cache_key, data, ttl_seconds=300)
        return data

    async def get_pr_diff(self, repo_full_name: str, pr_number: int) -> str:
        """
        Fetch the raw diff of a Pull Request.
        Results are cached in Redis for 10 minutes. Diffs only change
        when new commits are pushed (which triggers a new webhook anyway).
        """
        cache_key = f"github:diff:{repo_full_name}:{pr_number}"
        cached = await cache_get(cache_key)
        if cached is not None:
            logger.info(f"Returning cached diff for {repo_full_name}#{pr_number}")
            return cached

        endpoint = f"/repos/{repo_full_name}/pulls/{pr_number}"
        # To get the diff, GitHub requires a specific Accept header
        headers = {"Accept": "application/vnd.github.v3.diff"}
        response = await self._make_request("GET", endpoint, headers=headers)
        diff_text = response.text

        # Cache for 10 minutes — diffs don't change unless new commits are pushed
        await cache_set(cache_key, diff_text, ttl_seconds=600)
        return diff_text

    async def post_review_comment(self, repo_full_name: str, pr_number: int, body: str) -> dict[str, Any]:
        """
        Post a general comment to a Pull Request.
        """
        endpoint = f"/repos/{repo_full_name}/issues/{pr_number}/comments"
        payload = {"body": body}
        response = await self._make_request("POST", endpoint, json=payload)
        return response.json()

    async def post_inline_comment(
        self, 
        repo_full_name: str, 
        pr_number: int, 
        commit_id: str, 
        path: str, 
        line: int, 
        body: str
    ) -> dict[str, Any]:
        """
        Post an inline review comment on a specific line of code in the PR.
        """
        endpoint = f"/repos/{repo_full_name}/pulls/{pr_number}/comments"
        payload = {
            "body": body,
            "commit_id": commit_id,
            "path": path,
            "line": line,
            "side": "RIGHT" # The line in the new/changed file
        }
        response = await self._make_request("POST", endpoint, json=payload)
        return response.json()
