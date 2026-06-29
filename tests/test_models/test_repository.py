"""
test_repository.py — Tests for the Repository ORM model.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.repository import Repository


@pytest.mark.asyncio
async def test_create_repository(db_session: AsyncSession):
    """Creating a Repository with a valid owner should work."""
    user = User(email="repo-owner@test.com", hashed_password="hash")
    db_session.add(user)
    await db_session.flush()

    repo = Repository(
        github_id=111222333,
        full_name="testuser/testrepo",
        default_branch="main",
        owner_id=user.id,
    )
    db_session.add(repo)
    await db_session.flush()

    assert isinstance(repo.id, uuid.UUID)
    assert repo.full_name == "testuser/testrepo"
    assert repo.is_active is True
    assert repo.created_at is not None


@pytest.mark.asyncio
async def test_repository_belongs_to_user(db_session: AsyncSession):
    """Repository.owner should point back to the creating User."""
    user = User(email="owner@test.com", hashed_password="hash")
    db_session.add(user)
    await db_session.flush()

    repo = Repository(
        github_id=444555666,
        full_name="owner/myrepo",
        owner_id=user.id,
    )
    db_session.add(repo)
    await db_session.flush()

    # Re-query to verify FK
    result = await db_session.execute(
        select(Repository).where(Repository.id == repo.id)
    )
    found = result.scalar_one()
    assert found.owner_id == user.id


@pytest.mark.asyncio
async def test_github_id_must_be_unique(db_session: AsyncSession):
    """Two repos with the same github_id should raise IntegrityError."""
    user = User(email="dup-repo@test.com", hashed_password="hash")
    db_session.add(user)
    await db_session.flush()

    repo1 = Repository(
        github_id=999888777,
        full_name="user/repo1",
        owner_id=user.id,
    )
    db_session.add(repo1)
    await db_session.flush()

    repo2 = Repository(
        github_id=999888777,  # duplicate!
        full_name="user/repo2",
        owner_id=user.id,
    )
    db_session.add(repo2)

    with pytest.raises(IntegrityError):
        await db_session.flush()
