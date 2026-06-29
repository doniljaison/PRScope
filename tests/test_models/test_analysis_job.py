"""
test_analysis_job.py — Tests for the AnalysisJob and ReviewComment ORM models.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.analysis_job import AnalysisJob
from app.models.review_comment import ReviewComment


async def _create_full_chain(db_session: AsyncSession):
    """Helper — creates user → repo → PR, returns (user, repo, pr)."""
    user = User(email=f"job-{uuid.uuid4().hex[:8]}@test.com", hashed_password="hash")
    db_session.add(user)
    await db_session.flush()

    repo = Repository(
        github_id=int(uuid.uuid4().int % 10**9),
        full_name=f"user/repo-{uuid.uuid4().hex[:8]}",
        owner_id=user.id,
    )
    db_session.add(repo)
    await db_session.flush()

    pr = PullRequest(
        github_id=int(uuid.uuid4().int % 10**9),
        pr_number=1,
        title="Test PR",
        author_github_username="dev",
        head_sha="d" * 40,
        base_branch="main",
        head_branch="feature/test",
        repo_id=repo.id,
    )
    db_session.add(pr)
    await db_session.flush()
    return user, repo, pr


@pytest.mark.asyncio
async def test_create_analysis_job(db_session: AsyncSession):
    """Creating an AnalysisJob with valid FKs should work."""
    user, _, pr = await _create_full_chain(db_session)

    job = AnalysisJob(
        commit_sha="e" * 40,
        status="pending",
        pull_request_id=pr.id,
        triggered_by_id=user.id,
    )
    db_session.add(job)
    await db_session.flush()

    assert isinstance(job.id, uuid.UUID)
    assert job.status == "pending"
    assert job.started_at is None
    assert job.completed_at is None


@pytest.mark.asyncio
async def test_analysis_job_status_update(db_session: AsyncSession):
    """Status should be updatable to track job progress."""
    user, _, pr = await _create_full_chain(db_session)

    job = AnalysisJob(
        commit_sha="f" * 40,
        pull_request_id=pr.id,
        triggered_by_id=user.id,
    )
    db_session.add(job)
    await db_session.flush()

    # Simulate state transitions
    job.status = "running"
    await db_session.flush()
    assert job.status == "running"

    job.status = "completed"
    job.result_summary = "No issues found"
    job.llm_model_used = "gpt-4"
    await db_session.flush()
    assert job.status == "completed"


@pytest.mark.asyncio
async def test_create_review_comment(db_session: AsyncSession):
    """ReviewComment should link to an AnalysisJob."""
    user, _, pr = await _create_full_chain(db_session)

    job = AnalysisJob(
        commit_sha="a1" * 20,
        pull_request_id=pr.id,
    )
    db_session.add(job)
    await db_session.flush()

    comment = ReviewComment(
        file_path="src/main.py",
        line_number=42,
        comment_body="Consider using a context manager here.",
        severity="warning",
        analysis_job_id=job.id,
    )
    db_session.add(comment)
    await db_session.flush()

    assert isinstance(comment.id, uuid.UUID)
    assert comment.severity == "warning"
    assert comment.github_comment_id is None  # not posted to GitHub yet
