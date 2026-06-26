"""
base.py — Shared model mixin.

TimestampMixin adds created_at / updated_at columns to any model that
inherits it. Every table in this project will want these two columns —
this avoids retyping them in every model file.

This is a MIXIN, not a base class with __tablename__. It's combined with
Base (from app/database.py) like: `class User(Base, TimestampMixin):`
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        # server_default (not default=) means POSTGRES sets this value,
        # not Python. This matters: if you ever insert rows via raw SQL,
        # a migration script, or another service entirely, the timestamp
        # still gets set correctly — it doesn't depend on going through
        # your Python ORM code.
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        # onupdate=func.now() is different — it's a SQLAlchemy-side hook,
        # not a Postgres trigger. It only fires when you UPDATE a row
        # through the ORM. A raw SQL UPDATE would NOT touch this column.
        # (Day 21 query optimization section explains DB triggers as the
        # alternative if you ever need updated_at to be bulletproof.)
        nullable=False,
    )
