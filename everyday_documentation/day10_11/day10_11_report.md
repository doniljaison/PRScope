# Day 10-11 Report

## What we did:
- **Celery Configuration**: Configured the Celery application in `app/workers/celery_app.py` using Redis as the message broker.
- **Task Definition**: Created our first background task `analyze_pr_task` to simulate the analysis processing.
- **Routing**: Set up queue routing in Celery so the `analyze_pr_task` explicitly goes to a `high_priority` queue.
- **Docker Worker**: Enabled the Celery worker service in `docker-compose.yml` to process jobs concurrently.
- **Testing**: Added synchronous unit tests for the Celery tasks by mocking background behaviors.
