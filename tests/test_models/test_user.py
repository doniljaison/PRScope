"""
test_user.py — Tests for the User ORM model.

This is your first test that actually touches the database, using the
`db_session` fixture from tests/conftest.py.

Key thing to notice: we use `await db_session.flush()`, NOT
`await db_session.commit()`. Read the comment on the `db_session` fixture
in conftest.py for why — short version: flush() makes the row visible to
queries within this test; the fixture's rollback() afterward means this
row never actually exists once the test finishes.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    """Creating a User and flushing should assign defaults correctly."""
    user = User(
        email="test@example.com",
        hashed_password="not_a_real_hash",
    )
    db_session.add(user)
    await db_session.flush()  # Sends the INSERT, does NOT commit

    # default=uuid.uuid4 on the model should have generated a real UUID
    assert isinstance(user.id, uuid.UUID)
    # is_active defaults to True per the column definition
    assert user.is_active is True
    # server_default=func.now() — Postgres set this, not Python
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_query_user_by_email(db_session: AsyncSession):
    """A flushed-but-uncommitted row should still be queryable in this session."""
    user = User(email="findme@example.com", hashed_password="hash123")
    db_session.add(user)
    await db_session.flush()

    result = await db_session.execute(select(User).where(User.email == "findme@example.com"))
    found = result.scalar_one()

    assert found.id == user.id
    assert found.email == "findme@example.com"


@pytest.mark.asyncio
async def test_email_must_be_unique(db_session: AsyncSession):
    """The unique constraint on email should reject a duplicate."""
    from sqlalchemy.exc import IntegrityError

    user1 = User(email="dup@example.com", hashed_password="hash1")
    db_session.add(user1)
    await db_session.flush()

    user2 = User(email="dup@example.com", hashed_password="hash2")
    db_session.add(user2)

    with pytest.raises(IntegrityError):
        await db_session.flush()
