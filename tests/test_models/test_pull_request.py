"""
test_pull_request.py — Tests for the PullRequest ORM model.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.repository import Repository
from app.models.pull_request import PullRequest


async def _create_user_and_repo(db_session: AsyncSession):
    """Helper — creates a user and repo, returns (user, repo)."""
    user = User(email=f"pr-test-{uuid.uuid4().hex[:8]}@test.com", hashed_password="hash")
    db_session.add(user)
    await db_session.flush()

    repo = Repository(
        github_id=int(uuid.uuid4().int % 10**9),
        full_name=f"user/repo-{uuid.uuid4().hex[:8]}",
        owner_id=user.id,
    )
    db_session.add(repo)
    await db_session.flush()
    return user, repo


@pytest.mark.asyncio
async def test_create_pull_request(db_session: AsyncSession):
    """Creating a PullRequest with valid FK should work."""
    _, repo = await _create_user_and_repo(db_session)

    pr = PullRequest(
        github_id=100200300,
        pr_number=42,
        title="feat: add login page",
        author_github_username="contributor",
        head_sha="a" * 40,
        base_branch="main",
        head_branch="feature/login",
        repo_id=repo.id,
    )
    db_session.add(pr)
    await db_session.flush()

    assert isinstance(pr.id, uuid.UUID)
    assert pr.state == "open"  # default
    assert pr.created_at is not None


@pytest.mark.asyncio
async def test_pr_number_unique_per_repo(db_session: AsyncSession):
    """Two PRs with the same number in the same repo should fail."""
    _, repo = await _create_user_and_repo(db_session)

    pr1 = PullRequest(
        github_id=111111111,
        pr_number=1,
        title="First PR",
        author_github_username="dev1",
        head_sha="b" * 40,
        base_branch="main",
        head_branch="fix/one",
        repo_id=repo.id,
    )
    db_session.add(pr1)
    await db_session.flush()

    pr2 = PullRequest(
        github_id=222222222,
        pr_number=1,  # same number, same repo!
        title="Duplicate PR number",
        author_github_username="dev2",
        head_sha="c" * 40,
        base_branch="main",
        head_branch="fix/two",
        repo_id=repo.id,
    )
    db_session.add(pr2)

    with pytest.raises(IntegrityError):
        await db_session.flush()
