"""ReviewComment model — an AI-generated inline comment on a PR diff."""

import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class ReviewComment(Base, TimestampMixin):
    __tablename__ = "review_comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    comment_body: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    github_comment_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    analysis_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )

    # Relationships
    analysis_job: Mapped["AnalysisJob"] = relationship(back_populates="comments")  # noqa: F821

    def __repr__(self) -> str:
        return f"<ReviewComment id={self.id} {self.file_path}:{self.line_number} [{self.severity}]>"
