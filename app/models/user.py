"""
user.py — The User table.

The first real domain model in PRScope. Represents an account that can
log in (Week 1, Day 5-6) and later connect GitHub repositories (Day 7).

Supports two auth methods:
  1. Email + password (traditional registration)
  2. GitHub OAuth (no password — hashed_password is empty string)
"""

import uuid

from sqlalchemy import BigInteger, Boolean, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False, default=""
    )
    github_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── GitHub OAuth fields (Day 7) ──────────────────────────────────────────
    github_id: Mapped[int | None] = mapped_column(
        BigInteger, unique=True, nullable=True, index=True
    )
    github_access_token: Mapped[str | None] = mapped_column(
        Text, nullable=True
        # Stored ENCRYPTED via app/core/encryption.py — never plain text
    )
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Relationships ────────────────────────────────────────────────────────
    repositories: Mapped[list["Repository"]] = relationship(  # noqa: F821
        back_populates="owner",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
