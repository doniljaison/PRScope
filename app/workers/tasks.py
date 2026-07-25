"""Celery background tasks — PR analysis pipeline with real DB writes."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import redis
from celery import Task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.workers.celery_app import celery_app
from app.services.github_client import GitHubClient
from app.services.llm_client import LLMClient
from app.services.cache import cache_get, cache_set
from app.config import settings

logger = logging.getLogger(__name__)
sync_redis = redis.Redis.from_url(settings.REDIS_URL)


def publish_status(job_id: str, status: str, message: str = ""):
    """Publish status updates to Redis pub/sub for WebSocket clients."""
    data = {"job_id": job_id, "status": status, "message": message}
    sync_redis.publish("job_updates", json.dumps(data))


def async_to_sync(coro):
    """Run an async coroutine inside a sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


_WorkerSessionLocal = None


def get_worker_session_factory():
    """Lazy-init a DB session factory for the worker process."""
    global _WorkerSessionLocal
    if _WorkerSessionLocal is None:
        engine = create_async_engine(
            settings.DATABASE_URL, echo=False,
            pool_pre_ping=True, pool_size=3, max_overflow=5, pool_recycle=3600,
        )
        _WorkerSessionLocal = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False,
        )
    return _WorkerSessionLocal


@celery_app.task(name="app.workers.tasks.dlq_handler", queue="dead_letter")
def dlq_handler(task_id: str, task_name: str, args: list, kwargs: dict, exc: str):
    """Dead Letter Queue handler — logs permanently failed tasks."""
    logger.critical(
        f"DLQ: Task {task_name} [{task_id}] failed permanently. "
        f"Args: {args}, Exception: {exc}"
    )


class PRScopeTask(Task):
    """Routes permanently failed tasks to the DLQ."""
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {self.name} [{task_id}] failed, routing to DLQ.")
        dlq_handler.delay(task_id, self.name, list(args), dict(kwargs), str(exc))
        super().on_failure(exc, task_id, args, kwargs, einfo)


@celery_app.task(
    bind=True, base=PRScopeTask,
    autoretry_for=(Exception,), retry_backoff=True, max_retries=3,
    name="app.workers.tasks.analyze_pr_task",
)
def analyze_pr_task(self, pr_id_str: str, commit_sha: str = ""):
    """Analyze a PR: fetch diff → run LLM → save comments → optionally post to GitHub."""
    logger.info(f"Starting analysis for PR: {pr_id_str}")
    publish_status(pr_id_str, "started", "Analysis job started")

    async def run_analysis():
        from app.models.pull_request import PullRequest
        from app.models.repository import Repository
        from app.models.user import User
        from app.models.analysis_job import AnalysisJob
        from app.models.review_comment import ReviewComment

        # Cache deduplication
        if commit_sha:
            cached = await cache_get(f"analysis:{commit_sha}")
            if cached is not None:
                logger.info(f"Cache hit for commit {commit_sha}, skipping LLM")
                publish_status(pr_id_str, "completed", "Cached result returned")
                return cached

        SessionLocal = get_worker_session_factory()

        async with SessionLocal() as db:
            pr_id = uuid.UUID(pr_id_str)
            result = await db.execute(select(PullRequest).where(PullRequest.id == pr_id))
            pr = result.scalar_one_or_none()

            if pr is None:
                logger.error(f"PullRequest {pr_id_str} not found in database")
                publish_status(pr_id_str, "failed", "PR not found")
                return {"error": "PR not found"}

            repo_result = await db.execute(select(Repository).where(Repository.id == pr.repo_id))
            repo = repo_result.scalar_one_or_none()
            repo_full_name = repo.full_name if repo else "unknown/unknown"

            # Create AnalysisJob
            job = AnalysisJob(
                status="running", commit_sha=commit_sha or pr.head_sha,
                pull_request_id=pr.id, started_at=datetime.now(timezone.utc),
                llm_model_used="claude-sonnet-4-20250514",
            )
            db.add(job)
            await db.flush()
            job_id = str(job.id)

            # Resolve GitHub token
            access_token = "fake_token"
            if repo and repo.owner_id:
                owner_result = await db.execute(select(User).where(User.id == repo.owner_id))
                owner = owner_result.scalar_one_or_none()
                if owner and owner.github_access_token:
                    access_token = owner.github_access_token

            github = GitHubClient(access_token=access_token)
            llm = LLMClient()

            # Fetch diff
            publish_status(job_id, "fetching_diff", "Fetching PR diff from GitHub")
            try:
                diff_text = await github.get_pr_diff(repo_full_name, pr.pr_number)
            except Exception as e:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                publish_status(job_id, "failed", str(e))
                raise

            # LLM analysis
            publish_status(job_id, "analyzing", "Analyzing diff with Claude AI")
            try:
                comments_data = await llm.analyze_diff(diff_text)
            except Exception as e:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                publish_status(job_id, "failed", str(e))
                raise

            # Save ReviewComments
            for comment in comments_data:
                db.add(ReviewComment(
                    file_path=comment.get("path", "unknown"),
                    line_number=comment.get("line", 0),
                    comment_body=comment.get("body", ""),
                    severity=comment.get("severity", "info"),
                    analysis_job_id=job.id,
                ))

            # Post to GitHub (gated)
            if settings.ENABLE_GITHUB_POSTING:
                publish_status(job_id, "posting_comments", f"Posting {len(comments_data)} comments")
                for comment in comments_data:
                    try:
                        await github.post_review_comment(
                            repo_full_name, pr.pr_number, comment.get("body", ""),
                        )
                    except Exception as e:
                        logger.warning(f"Failed to post comment to GitHub: {e}")

            job.status = "completed"
            job.result_summary = f"Found {len(comments_data)} issues"
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

            if commit_sha:
                await cache_set(f"analysis:{commit_sha}", comments_data, ttl_seconds=3600)

            publish_status(job_id, "completed", f"Analysis done: {len(comments_data)} comments")
            return comments_data

    try:
        results = async_to_sync(run_analysis())
        logger.info(f"Completed analysis for PR: {pr_id_str}")
        return {"status": "success", "pr_id": pr_id_str, "results": results}
    except Exception as e:
        publish_status(pr_id_str, "failed", f"Error: {str(e)}")
        logger.error(f"Task failed: {e}")
        raise e
