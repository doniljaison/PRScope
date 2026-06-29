"""
analysis.py — Pydantic schemas for AnalysisJob and ReviewComment API shapes.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReviewCommentRead(BaseModel):
    """Shape of data returned when reading a review comment."""
    model_config = ConfigDict(from_attributes=True)

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
    model_config = ConfigDict(from_attributes=True)

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
