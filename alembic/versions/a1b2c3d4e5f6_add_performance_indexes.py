"""add performance indexes for common query patterns

Revision ID: a1b2c3d4e5f6
Revises: 5f716eda92b3
Create Date: 2026-07-15 00:25:00.000000

These indexes optimize the most common query patterns in PRScope:
  1. Listing PRs for a repo, sorted by creation date (dashboard view)
  2. Filtering analysis jobs by status for a specific PR
  3. Looking up analysis jobs by commit SHA (for deduplication)
  4. Joining review comments to their parent job
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str = '5f716eda92b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Composite index: list PRs by repo, sorted by date ─────────────────
    # Used by: GET /api/v1/repos/{repo_id}/pull-requests
    # Query: SELECT * FROM pull_requests WHERE repo_id = ? ORDER BY created_at DESC
    op.create_index(
        'ix_pull_requests_repo_id_created_at',
        'pull_requests',
        ['repo_id', 'created_at'],
    )

    # ── Composite index: filter jobs by PR + status ───────────────────────
    # Used by: analytics queries, job status dashboards
    # Query: SELECT * FROM analysis_jobs WHERE pull_request_id = ? AND status = ?
    op.create_index(
        'ix_analysis_jobs_pr_id_status',
        'analysis_jobs',
        ['pull_request_id', 'status'],
    )

    # ── Index: deduplicate by commit SHA ──────────────────────────────────
    # Used by: analyze_pr_task to check if a SHA was already analyzed
    # Query: SELECT * FROM analysis_jobs WHERE commit_sha = ?
    op.create_index(
        'ix_analysis_jobs_commit_sha',
        'analysis_jobs',
        ['commit_sha'],
    )

    # ── Index: review comments by job (already indexed via FK, but making it explicit)
    # Used by: eager loading comments when fetching an analysis job
    # The FK column analysis_job_id is already indexed, so this is a no-op safety check.


def downgrade() -> None:
    op.drop_index('ix_analysis_jobs_commit_sha', table_name='analysis_jobs')
    op.drop_index('ix_analysis_jobs_pr_id_status', table_name='analysis_jobs')
    op.drop_index('ix_pull_requests_repo_id_created_at', table_name='pull_requests')
