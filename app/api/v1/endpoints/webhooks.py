import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request

from app.config import settings
from app.workers.tasks import analyze_pr_task

# We might want to use a Redis client to check idempotency here
# Since we use fastapi Depends, we could inject redis, but for simplicity we can
# just connect to redis directly, or pass it as a dependency.
# In a real app we'd have a `get_redis` dependency. Let's assume we can add that later,
# or for now just skip idempotency if Redis isn't easily accessible without a dep.
# Let's add a simple check using our existing redis dependency if we have one. We don't have one yet.
# We'll just implement the skeleton for idempotency and the real Celery task enqueuing.

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks")

async def verify_github_signature(request: Request, x_hub_signature_256: str = Header(None)):
    """
    Verify the HMAC-SHA256 signature sent by GitHub to ensure the webhook is legitimate.
    """
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature-256 header")

    # Read the raw body
    payload = await request.body()
    
    # Calculate the expected signature
    secret = settings.GITHUB_WEBHOOK_SECRET.encode("utf-8")
    expected_hash = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    expected_signature = f"sha256={expected_hash}"

    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(x_hub_signature_256, expected_signature):
        logger.warning("Invalid GitHub webhook signature received.")
        raise HTTPException(status_code=401, detail="Invalid signature")

@router.post("/github", status_code=202)
async def github_webhook(
    request: Request,
    x_github_event: str = Header(None),
    x_github_delivery: str = Header(None),
    _ = Depends(verify_github_signature)
):
    """
    Receive webhook events from GitHub.
    Returns 202 Accepted immediately to prevent blocking GitHub.
    """
    if not x_github_event or not x_github_delivery:
        raise HTTPException(status_code=400, detail="Missing GitHub headers")

    # In a production app, check Redis using `x_github_delivery` to prevent processing the same webhook twice.
    # redis.set(f"webhook_delivery:{x_github_delivery}", "1", nx=True, ex=3600)
    # If it returns False (already exists), return 202 immediately.

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # We only care about pull requests for PRScope
    if x_github_event == "pull_request":
        action = payload.get("action")
        # We might only want to trigger analysis on 'opened' or 'synchronize' (new commits)
        if action in ["opened", "synchronize"]:
            pr_data = payload.get("pull_request", {})
            pr_url = pr_data.get("html_url", "unknown")
            logger.info(f"Received webhook for PR {action}: {pr_url}")
            
            # TODO: We need to write the PR to our database first, then queue the task.
            # But for Day 12, the goal is just to queue the Celery task.
            # Assuming we had the DB PR ID:
            fake_pr_uuid = "00000000-0000-0000-0000-000000000000"
            
            # Enqueue the Celery task (this is non-blocking)
            analyze_pr_task.delay(fake_pr_uuid)
            
            return {"status": "accepted", "message": "PR analysis queued"}

    # For any other event or unsupported PR action, just return 202
    return {"status": "ignored", "message": f"Event {x_github_event} ignored"}
