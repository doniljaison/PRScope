"""
analysis.py — Pydantic schemas for AnalysisJob and ReviewComment API shapes.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReviewCommentRead(BaseModel):
    """Shape of data returned when reading a review comment."""
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "d4e5f6a7-b8c9-0123-defg-234567890123",
                "file_path": "app/services/github_client.py",
                "line_number": 42,
                "comment_body": "Consider using a constant for the timeout value.",
                "severity": "warning",
                "github_comment_id": 1234567890,
                "analysis_job_id": "e5f6a7b8-c9d0-1234-efgh-345678901234",
                "created_at": "2026-07-14T10:31:00Z",
                "updated_at": "2026-07-14T10:31:00Z",
            }
        },
    )

    id: uuid.UUID
    file_path: str
    line_number: int
    comment_body: str
    severity: str
    github_comment_id: int | None
    analysis_job_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AnalysisJobRead(BaseModel):
    """Shape of data returned when reading an analysis job."""
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "e5f6a7b8-c9d0-1234-efgh-345678901234",
                "status": "completed",
                "commit_sha": "abc123def456789",
                "llm_model_used": "claude-3-5-sonnet-20240620",
                "result_summary": "Found 3 issues: 1 warning, 2 suggestions",
                "error_message": None,
                "started_at": "2026-07-14T10:30:00Z",
                "completed_at": "2026-07-14T10:30:45Z",
                "pull_request_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                "triggered_by_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "comments": [],
                "created_at": "2026-07-14T10:30:00Z",
                "updated_at": "2026-07-14T10:30:45Z",
            }
        },
    )

    id: uuid.UUID
    status: str
    commit_sha: str
    llm_model_used: str | None
    result_summary: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    pull_request_id: uuid.UUID
    triggered_by_id: uuid.UUID | None
    comments: list[ReviewCommentRead] = []
    created_at: datetime
    updated_at: datetime
