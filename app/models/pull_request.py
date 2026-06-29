"""
pull_request.py — The PullRequest table.

Represents a GitHub pull request that PRScope has seen (via webhook or
manual trigger). Each PR belongs to exactly one Repository.

Key design choice: we store `pr_number` (the human-readable #42) AND
`github_id` (GitHub's internal numeric ID). The pr_number is unique
per-repo, not globally — hence the composite unique constraint.

Relationships:
  - PullRequest.repository → Repository (many-to-one)
  - PullRequest.analysis_jobs → [AnalysisJob] (one-to-many)
"""

import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class PullRequest(Base, TimestampMixin):
    __tablename__ = "pull_requests"

    # Composite unique: a PR number is only unique within its repo
    __table_args__ = (
        UniqueConstraint("repo_id", "pr_number", name="uq_repo_pr_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    github_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    pr_number: Mapped[int] = mapped_column(
        Integer, index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author_github_username: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    # The commit SHA of the PR head — used to avoid re-analyzing the same commit
    head_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    head_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    # open, closed, or merged
    state: Mapped[str] = mapped_column(
        String(20), default="open", nullable=False
    )

    # FK to the repository this PR belongs to
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    repository: Mapped["Repository"] = relationship(  # noqa: F821
        back_populates="pull_requests",
    )
    analysis_jobs: Mapped[list["AnalysisJob"]] = relationship(  # noqa: F821
        back_populates="pull_request",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<PullRequest id={self.id} #{self.pr_number} {self.title[:30]}>"
