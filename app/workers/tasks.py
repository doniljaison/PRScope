import asyncio
import json
import logging
import uuid
import redis

from app.workers.celery_app import celery_app
from app.services.github_client import GitHubClient
from app.services.llm_client import LLMClient
from app.config import settings

logger = logging.getLogger(__name__)

# To publish synchronously to Redis from the Celery worker
sync_redis = redis.Redis.from_url(settings.REDIS_URL)

def publish_status(job_id: str, status: str, message: str = ""):
    """Helper to publish status updates to Redis pub/sub."""
    data = {
        "job_id": job_id,
        "status": status,
        "message": message
    }
    sync_redis.publish("job_updates", json.dumps(data))

# To call async code from Celery (which is sync), we need an event loop helper.
def async_to_sync(coro):
    """Utility to run an async coroutine inside a sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    name="app.workers.tasks.analyze_pr_task"
)
def analyze_pr_task(self, pr_id_str: str):
    """
    Background task to analyze a PR.
    This runs asynchronously in the Celery worker process.
    """
    logger.info(f"Starting analysis for PR: {pr_id_str}")
    publish_status(pr_id_str, "started", "Analysis job started")
    
    async def run_analysis():
        # In a real app, we'd get the GitHub token and repo details from the DB using pr_id_str.
        # For now, we mock the inputs to demonstrate the LLM and websocket flow.
        github = GitHubClient(access_token="fake_token")
        llm = LLMClient()
        
        repo = "octocat/Hello-World"
        pr_number = 1
        
        publish_status(pr_id_str, "fetching_diff", "Fetching PR diff from GitHub")
        try:
            diff_text = await github.get_pr_diff(repo, pr_number)
        except Exception as e:
            logger.warning(f"Failed to fetch diff, using mock diff. Error: {e}")
            diff_text = "--- a/test.py\n+++ b/test.py\n@@ -1,1 +1,2 @@\n-print('hello')\n+print('world')\n+import os"
            
        publish_status(pr_id_str, "analyzing", "Analyzing diff with Claude AI")
        comments = await llm.analyze_diff(diff_text)
        
        publish_status(pr_id_str, "posting_comments", f"Posting {len(comments)} comments to GitHub")
        # In the future: await github.post_review_comment(...)
        
        return comments
        
    try:
        results = async_to_sync(run_analysis())
        publish_status(pr_id_str, "completed", "Analysis completed successfully")
        logger.info(f"Completed analysis for PR: {pr_id_str}")
        return {"status": "success", "pr_id": pr_id_str, "results": results}
    except Exception as e:
        publish_status(pr_id_str, "failed", f"Error: {str(e)}")
        logger.error(f"Task failed: {e}")
        raise e
