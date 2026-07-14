"""
analytics.py — Analytics and statistics endpoints.

Provides aggregate views over repository data — analysis counts,
average comments per PR, most recent analyses, etc.

These endpoints demonstrate:
  - Efficient queries with selectinload to avoid N+1 problems
  - Aggregate queries using func.count, func.avg
  - The composite indexes we added in the Day 21 migration
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RepoStatsResponse(BaseModel):
    """Aggregate statistics for a single repository."""
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "repo_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "full_name": "octocat/Hello-World",
                "total_prs": 42,
                "total_analyses": 87,
                "completed_analyses": 80,
                "failed_analyses": 7,
                "total_comments": 156,
                "avg_comments_per_analysis": 1.95,
            }
        },
    )

    repo_id: uuid.UUID
    full_name: str
    total_prs: int
    total_analyses: int
    completed_analyses: int
    failed_analyses: int
    total_comments: int
    avg_comments_per_analysis: float


class RecentAnalysisResponse(BaseModel):
    """A recent analysis job for display in a dashboard."""
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "job_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "pr_number": 42,
                "pr_title": "Fix race condition in webhook handler",
                "status": "completed",
                "commit_sha": "abc123def456",
                "comments_count": 3,
                "started_at": "2026-07-14T10:30:00Z",
                "completed_at": "2026-07-14T10:30:45Z",
            }
        },
    )

    job_id: uuid.UUID
    pr_number: int
    pr_title: str
    status: str
    commit_sha: str
    comments_count: int
    started_at: datetime | None
    completed_at: datetime | None
