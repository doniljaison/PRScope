"""
analysis_job.py — The AnalysisJob table.

Represents a single code review job triggered for a pull request.
A PR can have multiple analysis jobs (e.g., re-triggered after new
commits, or manual re-analysis).

The `status` field follows a state machine:
  pending → running → completed
                   ↘ failed

Relationships:
  - AnalysisJob.pull_request → PullRequest (many-to-one)
  - AnalysisJob.triggered_by → User (many-to-one)
  - AnalysisJob.comments → [ReviewComment] (one-to-many)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class AnalysisJob(Base, TimestampMixin):
    __tablename__ = "analysis_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # State machine: pending → running → completed | failed
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True, nullable=False
    )
    # The exact commit SHA being analyzed — if the same SHA was already
    # analyzed, we can skip (idempotency at the job level)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    # Which LLM model was used (e.g., "gpt-4", "claude-3-opus")
    llm_model_used: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    # High-level summary of the analysis result
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # If status=failed, what went wrong
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Timing — useful for performance monitoring
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # FK to the PR being analyzed
    pull_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pull_requests.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # FK to the user who triggered this analysis (nullable = webhook-triggered)
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    pull_request: Mapped["PullRequest"] = relationship(  # noqa: F821
        back_populates="analysis_jobs",
    )
    triggered_by: Mapped["User | None"] = relationship(  # noqa: F821
        lazy="selectin",
    )
    comments: Mapped[list["ReviewComment"]] = relationship(  # noqa: F821
        back_populates="analysis_job",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AnalysisJob id={self.id} status={self.status}>"
