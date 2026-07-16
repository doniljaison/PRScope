"""
webhooks.py — GitHub webhook receiver.

This is the entry point for all GitHub events. When a developer opens or
updates a pull request, GitHub POSTs here. We:
  1. Verify the HMAC-SHA256 signature (is this really from GitHub?)
  2. Check idempotency via Redis SET NX (have we seen this delivery before?)
  3. Upsert Repository and PullRequest records in the database
  4. Dispatch a Celery task for async AI analysis
  5. Return 202 immediately — never block GitHub's webhook delivery

Idempotency is critical because GitHub retries failed webhooks. Without it,
a single PR open event could trigger 3 duplicate analyses.
"""

import hashlib
import hmac
import logging
import uuid
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis
from app.config import settings
from app.core.rate_limit import limiter
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.workers.tasks import analyze_pr_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks")


async def verify_github_signature(request: Request, x_hub_signature_256: str = Header(None)):
    """
    Verify the HMAC-SHA256 signature sent by GitHub to ensure the webhook is legitimate.
    """
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature-256 header")

    payload = await request.body()

    secret = settings.GITHUB_WEBHOOK_SECRET.encode("utf-8")
    expected_hash = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    expected_signature = f"sha256={expected_hash}"

    if not hmac.compare_digest(x_hub_signature_256, expected_signature):
        logger.warning("Invalid GitHub webhook signature received.")
        raise HTTPException(status_code=401, detail="Invalid signature")


async def _upsert_repository(db: AsyncSession, repo_payload: dict[str, Any]) -> Repository:
    """
    Find or create a Repository record from the webhook payload.

    GitHub webhooks always include repository data, so we upsert here
    instead of requiring the user to manually register repos.
    """
    github_id = repo_payload["id"]
    full_name = repo_payload["full_name"]

    result = await db.execute(
        select(Repository).where(Repository.github_id == github_id)
    )
    repo = result.scalar_one_or_none()

    if repo is None:
        # Auto-register the repo. We don't have an owner_id from the webhook,
        # so we create a "system" repository. In a full implementation,
        # you'd match this to the user who installed the GitHub App.
        repo = Repository(
            github_id=github_id,
            full_name=full_name,
            owner_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),  # placeholder
        )
        db.add(repo)
        await db.flush()
        logger.info(f"Auto-registered repository: {full_name}")
    else:
        # Update full_name if it changed (repo rename)
        if repo.full_name != full_name:
            repo.full_name = full_name
            await db.flush()

    return repo


async def _upsert_pull_request(
    db: AsyncSession,
    repo: Repository,
    pr_payload: dict[str, Any],
) -> PullRequest:
    """
    Find or create a PullRequest record from the webhook payload.

    On 'synchronize' events (new commits pushed), we update the head_sha
    so the analysis task knows which commit to review.
    """
    github_id = pr_payload.get("id", 0)
    pr_number = pr_payload["number"]
    title = pr_payload.get("title", "Untitled PR")
    author = pr_payload.get("user", {}).get("login", "unknown")
    head_sha = pr_payload.get("head", {}).get("sha", "unknown")
    base_branch = pr_payload.get("base", {}).get("ref", "main")
    head_branch = pr_payload.get("head", {}).get("ref", "unknown")

    result = await db.execute(
        select(PullRequest).where(
            PullRequest.repo_id == repo.id,
            PullRequest.pr_number == pr_number,
        )
    )
    pr = result.scalar_one_or_none()

    if pr is None:
        pr = PullRequest(
            github_id=github_id,
            pr_number=pr_number,
            title=title,
            author_github_username=author,
            head_sha=head_sha,
            base_branch=base_branch,
            head_branch=head_branch,
            repo_id=repo.id,
        )
        db.add(pr)
        await db.flush()
        logger.info(f"Created PullRequest #{pr_number} for {repo.full_name}")
    else:
        # Update mutable fields on synchronize events
        pr.head_sha = head_sha
        pr.title = title
        await db.flush()
        logger.info(f"Updated PullRequest #{pr_number} head_sha={head_sha[:8]}")

    return pr


@router.post("/github", status_code=202)
@limiter.limit("30/minute")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(None),
    x_github_delivery: str = Header(None),
    _=Depends(verify_github_signature),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Receive webhook events from GitHub.
    Returns 202 Accepted immediately to prevent blocking GitHub.
    """
    if not x_github_event or not x_github_delivery:
        raise HTTPException(status_code=400, detail="Missing GitHub headers")

    # ── Idempotency check ─────────────────────────────────────────────────
    # Redis SET NX (set-if-not-exists) with a 1 hour expiry.
    # If the key already exists, we've already processed this delivery.
    idempotency_key = f"webhook_delivery:{x_github_delivery}"
    is_new = await redis.set(idempotency_key, "1", nx=True, ex=3600)

    if not is_new:
        logger.info(f"Duplicate webhook delivery {x_github_delivery}, skipping")
        return {"status": "duplicate", "message": "Already processed this delivery"}

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # We only care about pull requests for PRScope
    if x_github_event == "pull_request":
        action = payload.get("action")
        if action in ["opened", "synchronize"]:
            pr_data = payload.get("pull_request", {})
            repo_data = payload.get("repository", {})
            pr_url = pr_data.get("html_url", "unknown")
            logger.info(f"Received webhook for PR {action}: {pr_url}")

            # ── Upsert DB records ─────────────────────────────────────────
            repo = await _upsert_repository(db, repo_data)
            pr = await _upsert_pull_request(db, repo, pr_data)

            # Commit the DB transaction so the worker can read these records
            await db.commit()

            # ── Dispatch Celery task with real PR ID and commit SHA ────────
            analyze_pr_task.delay(str(pr.id), pr.head_sha)

            return {"status": "accepted", "message": "PR analysis queued", "pr_id": str(pr.id)}

    # For any other event or unsupported PR action, just return 202
    return {"status": "ignored", "message": f"Event {x_github_event} ignored"}
