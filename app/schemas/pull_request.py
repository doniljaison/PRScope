"""
pull_request.py — Pydantic schemas for PullRequest API shapes.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PullRequestRead(BaseModel):
    """Shape of data returned when reading a pull request."""
    model_config = ConfigDict(from_attributes=True)

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
