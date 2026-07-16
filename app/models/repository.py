"""
repository.py — The Repository table.

Represents a GitHub repository that a PRScope user has connected for
automated PR reviews. Each repository belongs to one user (the person
who installed/connected it), but in the future you could add a
many-to-many for team access.

Relationships:
  - Repository.owner → User (many-to-one)
  - Repository.pull_requests → [PullRequest] (one-to-many)
"""

import uuid

from sqlalchemy import BigInteger, Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class Repository(Base, TimestampMixin):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # GitHub's internal numeric ID — unique globally across all of GitHub.
    # We store it so we can match incoming webhooks (which carry github_id)
    # to our local record without needing a full_name lookup.
    github_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    # "owner/repo" format, e.g. "octocat/Hello-World"
    full_name: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    default_branch: Mapped[str] = mapped_column(
        String(255), default="main", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    # Per-repo webhook secret — each repo gets its own secret so a
    # compromised secret for one repo doesn't affect others.
    webhook_secret: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # FK to the user who connected this repo.
    # Nullable because webhook-registered repos don't have a known owner —
    # the webhook payload doesn't tell us which PRScope user owns the repo.
    # It gets filled in when a user explicitly connects the repo via OAuth.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    owner: Mapped["User | None"] = relationship(  # noqa: F821
        back_populates="repositories",
        lazy="selectin",
    )
    pull_requests: Mapped[list["PullRequest"]] = relationship(  # noqa: F821
        back_populates="repository",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Repository id={self.id} name={self.full_name}>"
