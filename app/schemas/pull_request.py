"""
pull_request.py — Pydantic schemas for PullRequest API shapes.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PullRequestRead(BaseModel):
    """Shape of data returned when reading a pull request."""
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                "github_id": 987654321,
                "pr_number": 42,
                "title": "Fix race condition in webhook handler",
                "author_github_username": "octocat",
                "head_sha": "abc123def456789",
                "base_branch": "main",
                "head_branch": "fix/race-condition",
                "state": "open",
                "repo_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "created_at": "2026-07-14T10:00:00Z",
                "updated_at": "2026-07-14T10:30:00Z",
            }
        },
    )

    id: uuid.UUID
    github_id: int
    pr_number: int
    title: str
    author_github_username: str
    head_sha: str
    base_branch: str
    head_branch: str
    state: str
    repo_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
