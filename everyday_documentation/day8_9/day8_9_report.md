# Day 8-9 Report

## What we did:
- **GitHub Client**: Created `GitHubClient` in `app/services/github_client.py` using `httpx`.
- **API Methods**: Implemented methods to fetch PR details, fetch raw diffs, and post comments.
- **Robustness**: Integrated `tenacity` for exponential backoff on rate limits (429) and server errors (5xx).
- **Testing**: Added `respx` to mock external GitHub HTTP requests and verified the retry behavior and custom Accept headers.
