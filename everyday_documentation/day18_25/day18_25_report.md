# Days 18-25 Report — CI/CD, Deployment, and Query Optimization

## Day 18-20: Testing Hardening & API Documentation

### What was done
- Fixed Celery event loop conflicts (`RuntimeError: no current event loop`)
- Added edge case tests: malformed JSON, missing fields, expired tokens, invalid UUIDs
- Added comprehensive exception handler tests (custom hierarchy → consistent JSON envelope)
- Reached 70+ test coverage across unit, integration, and edge case suites
- Configured FastAPI OpenAPI docs with Swagger examples on all schemas

### Key learnings
- Celery workers run in a separate process — they don't inherit the FastAPI event loop
- `async_to_sync` bridge needed to run async code inside sync Celery tasks
- `json_schema_extra` on Pydantic models = Swagger "Try it out" works out of the box

---

## Day 21-22: Database Optimization

### What was done
- Added composite indexes for common query patterns:
  - `ix_pull_requests_repo_id_created_at` (dashboard PR listing)
  - `ix_analysis_jobs_pr_id_status` (job status filtering)
  - `ix_analysis_jobs_commit_sha` (dedup lookups)
- Tuned connection pool: `pool_size=5`, `max_overflow=10`, `pool_recycle=3600`
- Used `selectinload` in analytics queries to avoid N+1 problem

### Key learnings
- `server_default=func.now()` → Postgres sets the timestamp (works even for raw SQL inserts)
- `onupdate=func.now()` → SQLAlchemy-side hook, only fires through ORM
- `pool_pre_ping=True` catches stale connections before they fail a query

---

## Day 23-24: GitHub Actions CI Pipeline

### What was done
- Created `.github/workflows/ci.yml` with lint and test jobs
- Services: PostgreSQL 15 + Redis 7 spun up as GitHub Actions services
- `ruff check` for linting, `pytest` with `--tb=short` for tests
- Added CI status badge and version badges to README

### Key learnings
- GitHub Actions services need explicit health checks before the test step
- `POSTGRES_HOST: localhost` in CI (services run on the same runner)
- CI environment uses `.env` created in the workflow, not the repo's `.env`

---

## Day 25: Deployment Configuration

### What was done
- Multi-stage production Dockerfile (builder + runtime = smaller image)
- `Procfile` for Render.com (web + worker processes)
- `render.yaml` IaC for one-click deployment
- `.env.example` with all required variables documented
- `.dockerignore` to keep build context small

### Key learnings
- Multi-stage builds: `pip install --target=/install` in builder, copy to runtime
- Render.com uses `render.yaml` for Infrastructure as Code
- `pool_pre_ping=True` is critical for managed Postgres (connections drop after idle)
