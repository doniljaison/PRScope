"""Repository analytics — aggregate stats and recent analysis jobs."""

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
async def get_repo_stats(repo_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Aggregate statistics for a repository."""
    repo_result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = repo_result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository {repo_id} not found")

    pr_count_result = await db.execute(
        select(func.count(PullRequest.id)).where(PullRequest.repo_id == repo_id)
    )
    total_prs = pr_count_result.scalar() or 0

    analysis_base = (
        select(func.count(AnalysisJob.id))
        .join(PullRequest, AnalysisJob.pull_request_id == PullRequest.id)
        .where(PullRequest.repo_id == repo_id)
    )

    total_analyses = (await db.execute(analysis_base)).scalar() or 0
    completed_analyses = (await db.execute(analysis_base.where(AnalysisJob.status == "completed"))).scalar() or 0
    failed_analyses = (await db.execute(analysis_base.where(AnalysisJob.status == "failed"))).scalar() or 0

    comment_count_result = await db.execute(
        select(func.count(ReviewComment.id))
        .join(AnalysisJob, ReviewComment.analysis_job_id == AnalysisJob.id)
        .join(PullRequest, AnalysisJob.pull_request_id == PullRequest.id)
        .where(PullRequest.repo_id == repo_id)
    )
    total_comments = comment_count_result.scalar() or 0
    avg_comments = total_comments / completed_analyses if completed_analyses > 0 else 0.0

    return RepoStatsResponse(
        repo_id=repo.id, full_name=repo.full_name,
        total_prs=total_prs, total_analyses=total_analyses,
        completed_analyses=completed_analyses, failed_analyses=failed_analyses,
        total_comments=total_comments, avg_comments_per_analysis=round(avg_comments, 2),
    )


@router.get("/{repo_id}/recent", response_model=list[RecentAnalysisResponse])
async def get_recent_analyses(
    repo_id: uuid.UUID, limit: int = 10, db: AsyncSession = Depends(get_db),
):
    """Most recent analysis jobs for a repository (with eager-loaded relationships)."""
    repo_result = await db.execute(select(Repository).where(Repository.id == repo_id))
    if repo_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository {repo_id} not found")

    jobs_result = await db.execute(
        select(AnalysisJob)
        .join(PullRequest, AnalysisJob.pull_request_id == PullRequest.id)
        .where(PullRequest.repo_id == repo_id)
        .options(selectinload(AnalysisJob.pull_request), selectinload(AnalysisJob.comments))
        .order_by(AnalysisJob.created_at.desc())
        .limit(limit)
    )
    jobs = jobs_result.scalars().all()

    return [
        RecentAnalysisResponse(
            job_id=job.id, pr_number=job.pull_request.pr_number,
            pr_title=job.pull_request.title, status=job.status,
            commit_sha=job.commit_sha, comments_count=len(job.comments),
            started_at=job.started_at, completed_at=job.completed_at,
        )
        for job in jobs
    ]
