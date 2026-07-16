"""
tasks.py — Celery background tasks.

The main task is `analyze_pr_task`, which:
  1. Looks up the PullRequest in the database
  2. Creates an AnalysisJob record (status: running)
  3. Fetches the PR diff from GitHub
  4. Sends the diff to Claude for AI review
  5. Saves ReviewComment records to the database
  6. Optionally posts comments to GitHub (gated by ENABLE_GITHUB_POSTING)
  7. Updates the AnalysisJob status to completed/failed

The entire flow uses real database records now — no more fake UUIDs.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import redis
from celery import Task
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.workers.celery_app import celery_app
from app.services.github_client import GitHubClient
from app.services.llm_client import LLMClient
from app.services.cache import cache_get, cache_set
from app.config import settings

logger = logging.getLogger(__name__)

# Sync Redis for pub/sub status updates (Celery is sync)
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


def _get_worker_db_session() -> async_sessionmaker:
    """
    Create a DB session factory for the worker process.

    We can't share the FastAPI app's session factory because the worker
    runs in a separate process with its own event loop. Each worker
    gets its own engine and session factory.
    """
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=5,
        pool_recycle=3600,
    )
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


# Lazy-init the session factory (created on first use)
_WorkerSessionLocal = None


def get_worker_session_factory():
    global _WorkerSessionLocal
    if _WorkerSessionLocal is None:
        _WorkerSessionLocal = _get_worker_db_session()
    return _WorkerSessionLocal


@celery_app.task(name="app.workers.tasks.dlq_handler", queue="dead_letter")
def dlq_handler(task_id: str, task_name: str, args: list, kwargs: dict, exc: str):
    """
    Dead Letter Queue handler.
    Logs permanently failed task details for manual inspection.
    """
    logger.critical(
        f"DLQ Alert: Task {task_name} [{task_id}] failed permanently. "
        f"Args: {args}, Kwargs: {kwargs}. Exception: {exc}"
    )


class PRScopeTask(Task):
    """Custom base task that routes permanently failed tasks to the DLQ."""
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {self.name} [{task_id}] failed permanently, routing to DLQ.")
        dlq_handler.delay(task_id, self.name, list(args), dict(kwargs), str(exc))
        super().on_failure(exc, task_id, args, kwargs, einfo)


@celery_app.task(
    bind=True,
    base=PRScopeTask,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    name="app.workers.tasks.analyze_pr_task"
)
def analyze_pr_task(self, pr_id_str: str, commit_sha: str = ""):
    """
    Background task to analyze a PR.

    Args:
        pr_id_str: The UUID of the PullRequest record in our database.
        commit_sha: The head commit SHA — used for cache deduplication.
    """
    logger.info(f"Starting analysis for PR: {pr_id_str}")
    publish_status(pr_id_str, "started", "Analysis job started")

    async def run_analysis():
        # Import models inside the async function to avoid circular imports
        from app.models.pull_request import PullRequest
        from app.models.repository import Repository
        from app.models.user import User
        from app.models.analysis_job import AnalysisJob
        from app.models.review_comment import ReviewComment

        # ── Deduplication: skip if this commit SHA was already analyzed ────
        if commit_sha:
            cache_key = f"analysis:{commit_sha}"
            cached_result = await cache_get(cache_key)
            if cached_result is not None:
                logger.info(f"Analysis for commit {commit_sha} already cached, skipping LLM")
                publish_status(pr_id_str, "completed", "Analysis already cached for this commit SHA")
                return cached_result

        SessionLocal = get_worker_session_factory()

        async with SessionLocal() as db:
            # ── Load the PR and its repository from the database ──────────
            pr_id = uuid.UUID(pr_id_str)
            result = await db.execute(
                select(PullRequest).where(PullRequest.id == pr_id)
            )
            pr = result.scalar_one_or_none()

            if pr is None:
                logger.error(f"PullRequest {pr_id_str} not found in database")
                publish_status(pr_id_str, "failed", "PR not found in database")
                return {"error": "PR not found"}

            # Load the repository
            repo_result = await db.execute(
                select(Repository).where(Repository.id == pr.repo_id)
            )
            repo = repo_result.scalar_one_or_none()
            repo_full_name = repo.full_name if repo else "unknown/unknown"

            # ── Create an AnalysisJob record ──────────────────────────────
            job = AnalysisJob(
                status="running",
                commit_sha=commit_sha or pr.head_sha,
                pull_request_id=pr.id,
                started_at=datetime.now(timezone.utc),
                llm_model_used="claude-sonnet-4-20250514",
            )
            db.add(job)
            await db.flush()
            job_id = str(job.id)

            publish_status(job_id, "fetching_diff", "Fetching PR diff from GitHub")

            # ── Fetch the diff ────────────────────────────────────────────
            # Try to get the owner's GitHub token for authenticated API access.
            # Fall back to unauthenticated if no token is available.
            access_token = "fake_token"
            if repo and repo.owner_id:
                owner_result = await db.execute(
                    select(User).where(User.id == repo.owner_id)
                )
                owner = owner_result.scalar_one_or_none()
                if owner and owner.github_access_token:
                    access_token = owner.github_access_token

            github = GitHubClient(access_token=access_token)
            llm = LLMClient()

            try:
                diff_text = await github.get_pr_diff(repo_full_name, pr.pr_number)
            except Exception as e:
                logger.warning(f"Failed to fetch diff from GitHub: {e}")
                job.status = "failed"
                job.error_message = f"Failed to fetch diff: {str(e)}"
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                publish_status(job_id, "failed", str(e))
                raise

            # ── Run Claude analysis ───────────────────────────────────────
            publish_status(job_id, "analyzing", "Analyzing diff with Claude AI")

            try:
                comments_data = await llm.analyze_diff(diff_text)
            except Exception as e:
                logger.error(f"LLM analysis failed: {e}")
                job.status = "failed"
                job.error_message = f"LLM analysis failed: {str(e)}"
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                publish_status(job_id, "failed", str(e))
                raise

            # ── Save ReviewComment records to the database ────────────────
            for comment in comments_data:
                review_comment = ReviewComment(
                    file_path=comment.get("path", "unknown"),
                    line_number=comment.get("line", 0),
                    comment_body=comment.get("body", ""),
                    severity=comment.get("severity", "info"),
                    analysis_job_id=job.id,
                )
                db.add(review_comment)

            # ── Optionally post comments to GitHub ────────────────────────
            if settings.ENABLE_GITHUB_POSTING:
                publish_status(job_id, "posting_comments", f"Posting {len(comments_data)} comments to GitHub")
                for comment in comments_data:
                    try:
                        await github.post_review_comment(
                            repo_full_name,
                            pr.pr_number,
                            comment.get("body", ""),
                        )
                    except Exception as e:
                        logger.warning(f"Failed to post comment to GitHub: {e}")
                        # Don't fail the whole job for a comment posting failure
            else:
                logger.info("ENABLE_GITHUB_POSTING is False, skipping GitHub comment posting")

            # ── Mark job as completed ─────────────────────────────────────
            job.status = "completed"
            job.result_summary = f"Found {len(comments_data)} issues"
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Cache results by commit SHA
            if commit_sha:
                await cache_set(f"analysis:{commit_sha}", comments_data, ttl_seconds=3600)

            publish_status(job_id, "completed", f"Analysis completed: {len(comments_data)} comments")
            return comments_data

    try:
        results = async_to_sync(run_analysis())
        logger.info(f"Completed analysis for PR: {pr_id_str}")
        return {"status": "success", "pr_id": pr_id_str, "results": results}
    except Exception as e:
        publish_status(pr_id_str, "failed", f"Error: {str(e)}")
        logger.error(f"Task failed: {e}")
        raise e
