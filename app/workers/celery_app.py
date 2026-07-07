"""
celery_app.py — Celery application configuration and initialization.
"""

from celery import Celery

from app.config import settings

# Initialize Celery application
# 'prscope' is the name of the main module
celery_app = Celery(
    "prscope",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"]  # where our tasks are located
)

# Optional configuration, see the application user guide.
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],  # Ignore other content
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Route certain tasks to specific queues
    task_routes={
        "app.workers.tasks.analyze_pr_task": {"queue": "high_priority"},
        "app.workers.tasks.dlq_handler": {"queue": "dead_letter"},
    },
    # Ensure idempotency by acknowledging tasks AFTER they are completed.
    # Actually, Celery by default acks before execution.
    # To enable late ack (ack after execution), set:
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
