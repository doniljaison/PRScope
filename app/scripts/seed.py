"""
seed.py — Populate the database with sample data for development.

Run with:
  docker compose exec api python -m app.scripts.seed

This script is idempotent — it checks for existing data before inserting.
"""

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.analysis_job import AnalysisJob
from app.models.review_comment import ReviewComment


async def seed():
    async with AsyncSessionLocal() as session:
        # Check if data already exists
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            print("Database already has data — skipping seed.")
            return

        # ── Create a test user ───────────────────────────────────────────────
        user = User(
            email="dev@prscope.io",
            hashed_password="$2b$12$placeholder_hash_for_seed_data",
            github_username="prscope-dev",
        )
        session.add(user)
        await session.flush()
        print(f"Created user: {user.email} (id={user.id})")

        # ── Create a sample repository ───────────────────────────────────────
        repo = Repository(
            github_id=123456789,
            full_name="prscope-dev/hello-world",
            default_branch="main",
            owner_id=user.id,
        )
        session.add(repo)
        await session.flush()
        print(f"Created repo: {repo.full_name} (id={repo.id})")

        # ── Create a sample pull request ─────────────────────────────────────
        pr = PullRequest(
            github_id=987654321,
            pr_number=1,
            title="feat: add initial README",
            author_github_username="prscope-dev",
            head_sha="abc123def456789012345678901234567890abcd",
            base_branch="main",
            head_branch="feature/readme",
            state="open",
            repo_id=repo.id,
        )
        session.add(pr)
        await session.flush()
        print(f"Created PR: #{pr.pr_number} {pr.title} (id={pr.id})")

        # ── Create a sample analysis job ─────────────────────────────────────
        job = AnalysisJob(
            commit_sha="abc123def456789012345678901234567890abcd",
            status="completed",
            llm_model_used="gpt-4",
            result_summary="Found 2 issues: 1 warning, 1 info",
            pull_request_id=pr.id,
            triggered_by_id=user.id,
        )
        session.add(job)
        await session.flush()
        print(f"Created analysis job: {job.status} (id={job.id})")

        # ── Create sample review comments ────────────────────────────────────
        comments = [
            ReviewComment(
                file_path="README.md",
                line_number=5,
                comment_body="Consider adding a license section.",
                severity="info",
                analysis_job_id=job.id,
            ),
            ReviewComment(
                file_path="README.md",
                line_number=12,
                comment_body="Typo: 'teh' should be 'the'.",
                severity="warning",
                analysis_job_id=job.id,
            ),
        ]
        session.add_all(comments)
        await session.flush()
        print(f"Created {len(comments)} review comments")

        await session.commit()
        print("\nSeed complete!")


if __name__ == "__main__":
    asyncio.run(seed())
