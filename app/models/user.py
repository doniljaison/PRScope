"""
user.py — The User table.

The first real domain model in PRScope. Represents an account that can
log in (Week 1, Day 5-6) and later connect GitHub repositories (Day 7).
"""

import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        # WHY UUID instead of an auto-incrementing integer?
        #   1. IDs aren't guessable/enumerable (security: /users/1, /users/2...)
        #   2. Generated client-side (in Python) BEFORE the insert — useful
        #      when you need the ID before committing (e.g. to queue a
        #      Celery task referencing this row, in the same request)
        #   3. Safe across distributed systems — no central counter needed
        # Tradeoff: UUIDs are 16 bytes vs 4-8 for an int, and don't sort
        # naturally by creation time. For a project this size, the benefits
        # outweigh that. You should know BOTH approaches exist.
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    github_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        # Without this, debugging prints <app.models.user.User object at 0x7f...>
        # which tells you nothing. Always define __repr__ on models.
        return f"<User id={self.id} email={self.email}>"
