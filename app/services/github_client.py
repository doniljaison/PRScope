"""GitHub API client with auth, rate-limit handling, retries, and response caching."""

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
        self.base_url = "https://api.github.com"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        self.client = httpx.AsyncClient(
            base_url=self.base_url, headers=headers, timeout=10.0,
        )

    async def close(self):
        await self.client.aclose()

    @retry(
        retry=retry_if_exception_type((httpx.RequestError, GitHubRateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        after=log_attempt_number, reraise=True,
    )
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Make an HTTP request with automatic retry on rate-limit and server errors."""
        try:
            response = await self.client.request(method, endpoint, **kwargs)
        except httpx.RequestError as e:
            logger.error(f"Network error calling GitHub API: {e}")
            raise

        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) == 0:
            raise GitHubRateLimitError("GitHub API rate limit exceeded.")

        if response.status_code == 429:
            raise GitHubRateLimitError("Received 429 Too Many Requests from GitHub.")
        elif response.status_code >= 500:
            raise httpx.RequestError(f"GitHub Server Error: {response.status_code}", request=response.request)

        if not response.is_success:
            raise GitHubAPIError(f"GitHub API returned {response.status_code}: {response.text}")

        return response

    async def get_pull_request(self, repo_full_name: str, pr_number: int) -> dict[str, Any]:
        """Fetch PR details (cached 5 min)."""
        cache_key = f"github:pr:{repo_full_name}:{pr_number}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        response = await self._make_request("GET", f"/repos/{repo_full_name}/pulls/{pr_number}")
        data = response.json()
        await cache_set(cache_key, data, ttl_seconds=300)
        return data

    async def get_pr_diff(self, repo_full_name: str, pr_number: int) -> str:
        """Fetch raw PR diff (cached 10 min)."""
        cache_key = f"github:diff:{repo_full_name}:{pr_number}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        headers = {"Accept": "application/vnd.github.v3.diff"}
        response = await self._make_request("GET", f"/repos/{repo_full_name}/pulls/{pr_number}", headers=headers)
        diff_text = response.text
        await cache_set(cache_key, diff_text, ttl_seconds=600)
        return diff_text

    async def post_review_comment(self, repo_full_name: str, pr_number: int, body: str) -> dict[str, Any]:
        """Post a general comment on a PR."""
        response = await self._make_request(
            "POST", f"/repos/{repo_full_name}/issues/{pr_number}/comments", json={"body": body},
        )
        return response.json()

    async def post_inline_comment(
        self, repo_full_name: str, pr_number: int,
        commit_id: str, path: str, line: int, body: str,
    ) -> dict[str, Any]:
        """Post an inline review comment on a specific line in the diff."""
        payload = {"body": body, "commit_id": commit_id, "path": path, "line": line, "side": "RIGHT"}
        response = await self._make_request(
            "POST", f"/repos/{repo_full_name}/pulls/{pr_number}/comments", json=payload,
        )
        return response.json()
