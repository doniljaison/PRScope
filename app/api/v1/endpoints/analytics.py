"""
analytics.py — Repository analytics and statistics endpoints.

GET /api/v1/repos/{repo_id}/stats  — aggregate stats for a repository
GET /api/v1/repos/{repo_id}/recent — most recent analysis jobs

These endpoints demonstrate:
  - Efficient aggregate queries (COUNT, AVG) instead of loading all objects
  - selectinload for avoiding N+1 when we do need related objects
  - The composite indexes we added in the Day 21 migration
"""

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.analysis_job import AnalysisJob
from app.models.review_comment import ReviewComment
from app.schemas.analytics import RepoStatsResponse, RecentAnalysisResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repos")


@router.get("/{repo_id}/stats", response_model=RepoStatsResponse)
async def get_repo_stats(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get aggregate statistics for a repository.

    Uses efficient COUNT/AVG queries instead of loading all objects into memory.
    This hits the composite indexes we added in the Day 21 migration.
    """
    # First verify the repo exists
    repo_result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = repo_result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repo_id} not found",
        )

    # Count PRs for this repo (uses ix_pull_requests_repo_id_created_at)
    pr_count_result = await db.execute(
        select(func.count(PullRequest.id)).where(PullRequest.repo_id == repo_id)
    )
    total_prs = pr_count_result.scalar() or 0

    # Count analyses by status (uses ix_analysis_jobs_pr_id_status)
    # We join through PullRequest to filter by repo_id
    analysis_base = (
        select(func.count(AnalysisJob.id))
        .join(PullRequest, AnalysisJob.pull_request_id == PullRequest.id)
        .where(PullRequest.repo_id == repo_id)
    )

    total_result = await db.execute(analysis_base)
    total_analyses = total_result.scalar() or 0

    completed_result = await db.execute(
        analysis_base.where(AnalysisJob.status == "completed")
    )
    completed_analyses = completed_result.scalar() or 0

    failed_result = await db.execute(
        analysis_base.where(AnalysisJob.status == "failed")
    )
    failed_analyses = failed_result.scalar() or 0

    # Count total review comments
    comment_count_result = await db.execute(
        select(func.count(ReviewComment.id))
        .join(AnalysisJob, ReviewComment.analysis_job_id == AnalysisJob.id)
        .join(PullRequest, AnalysisJob.pull_request_id == PullRequest.id)
        .where(PullRequest.repo_id == repo_id)
    )
    total_comments = comment_count_result.scalar() or 0

    avg_comments = (
        total_comments / completed_analyses if completed_analyses > 0 else 0.0
    )

    return RepoStatsResponse(
        repo_id=repo.id,
        full_name=repo.full_name,
        total_prs=total_prs,
        total_analyses=total_analyses,
        completed_analyses=completed_analyses,
        failed_analyses=failed_analyses,
        total_comments=total_comments,
        avg_comments_per_analysis=round(avg_comments, 2),
    )


@router.get("/{repo_id}/recent", response_model=list[RecentAnalysisResponse])
async def get_recent_analyses(
    repo_id: uuid.UUID,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the most recent analysis jobs for a repository.

    Uses selectinload to eagerly load comments and the parent PR
    in a single query, avoiding the N+1 problem:
      BAD:  1 query for jobs + N queries for each job's PR = N+1
      GOOD: 1 query for jobs + 1 batch query for all related PRs = 2
    """
    # Verify repo exists
    repo_result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    if repo_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repo_id} not found",
        )

    # Fetch recent analysis jobs with eager-loaded relationships
    # selectinload runs a separate IN query for related objects instead
    # of N individual queries — this is the fix for N+1
    jobs_result = await db.execute(
        select(AnalysisJob)
        .join(PullRequest, AnalysisJob.pull_request_id == PullRequest.id)
        .where(PullRequest.repo_id == repo_id)
        .options(
            selectinload(AnalysisJob.pull_request),
            selectinload(AnalysisJob.comments),
        )
        .order_by(AnalysisJob.created_at.desc())
        .limit(limit)
    )
    jobs = jobs_result.scalars().all()

    return [
        RecentAnalysisResponse(
            job_id=job.id,
            pr_number=job.pull_request.pr_number,
            pr_title=job.pull_request.title,
            status=job.status,
            commit_sha=job.commit_sha,
            comments_count=len(job.comments),
            started_at=job.started_at,
            completed_at=job.completed_at,
        )
        for job in jobs
    ]
