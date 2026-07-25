# System Design — PRScope

## Overview

PRScope is an AI-powered GitHub PR review engine. When a developer opens a pull request, PRScope automatically fetches the diff, runs an AI code review, and stores the results — with optional posting of inline comments back to GitHub.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   GitHub      │     │   FastAPI    │     │   Celery     │
│   Webhook     │────▶│   API        │────▶│   Worker     │
│   (POST)      │     │   (async)    │     │   (async)    │
└──────────────┘     └──────┬───────┘     └──────┬───────┘
                            │                     │
                     ┌──────▼───────┐      ┌──────▼───────┐
                     │  PostgreSQL  │      │  Claude LLM  │
                     │  (data)      │      │  (analysis)  │
                     └──────────────┘      └──────────────┘
                     ┌──────────────┐
                     │    Redis     │
                     │  (queue,     │
                     │   cache,     │
                     │   pub/sub)   │
                     └──────────────┘
```

## Data Flow

1. **Webhook Ingestion**: GitHub sends a `pull_request` event to `POST /api/v1/webhooks/github`
2. **Signature Verification**: HMAC-SHA256 validates the payload authenticity
3. **Idempotency Check**: Redis `SET NX` with the `X-GitHub-Delivery` header prevents duplicate processing
4. **DB Upsert**: Repository and PullRequest records are created or updated
5. **Task Dispatch**: A Celery task is enqueued with the real PR ID and commit SHA
6. **Diff Fetching**: The worker fetches the PR diff from GitHub's API (cached in Redis)
7. **LLM Analysis**: The diff is sent to Claude for code review
8. **Result Storage**: ReviewComment records are saved to PostgreSQL
9. **Optional Posting**: If `ENABLE_GITHUB_POSTING=True`, comments are posted to GitHub
10. **Real-time Updates**: WebSocket clients receive status updates via Redis pub/sub

## Key Design Decisions

### Event-Driven Architecture
- **Why**: Decouples webhook reception from analysis processing. GitHub requires fast webhook responses (< 10s), but LLM analysis takes 30-60s.
- **How**: FastAPI handles HTTP and returns 202 immediately. Celery workers process jobs asynchronously.

### Redis as Multi-Purpose Infrastructure
- **Message Queue**: Celery broker for task distribution
- **Cache**: API response caching to reduce GitHub rate limit consumption
- **Pub/Sub**: Real-time job status updates to WebSocket clients
- **Idempotency Store**: `SET NX` prevents duplicate webhook processing
- **Session Store**: Refresh tokens stored with TTL for revocation

### Async All the Way
- **FastAPI**: Async request handling with `asyncpg` for non-blocking DB access
- **Celery Worker**: Uses `async_to_sync` bridge to run async code (GitHub API, LLM calls) inside sync Celery tasks
- **SQLAlchemy**: Async engine with connection pooling (`pool_size=5`, `max_overflow=10`)

### Cache-Aside Pattern
- GitHub API responses are cached in Redis with short TTLs (5-10 min)
- LLM analysis results are cached by commit SHA (1 hour)
- Cache failures never break the app — they degrade to direct API calls

### Safety-First Deployment
- `ENABLE_GITHUB_POSTING` flag gates real GitHub comment posting
- Dead Letter Queue captures permanently failed tasks for manual inspection
- Exponential backoff with jitter on GitHub API retries (tenacity)

## Database Schema

```
users
├── id (UUID PK)
├── email (unique)
├── hashed_password
├── github_id (nullable, for OAuth)
├── github_access_token (encrypted)
└── is_active

repositories
├── id (UUID PK)
├── github_id (unique)
├── full_name (unique, e.g. "owner/repo")
├── owner_id (FK → users, nullable)
└── is_active

pull_requests
├── id (UUID PK)
├── github_id (unique)
├── pr_number
├── title, author, head_sha, branches
├── repo_id (FK → repositories)
└── UNIQUE(repo_id, pr_number)

analysis_jobs
├── id (UUID PK)
├── status (pending → running → completed | failed)
├── commit_sha (indexed for dedup)
├── llm_model_used
├── pull_request_id (FK → pull_requests)
└── started_at, completed_at

review_comments
├── id (UUID PK)
├── file_path, line_number
├── comment_body, severity
├── github_comment_id (nullable, set after posting)
└── analysis_job_id (FK → analysis_jobs)
```

## Security

- **Webhook Auth**: HMAC-SHA256 signature verification with constant-time comparison
- **User Auth**: JWT access tokens (30 min) + refresh tokens (7 days, stored in Redis)
- **Password Storage**: bcrypt via passlib
- **Token Encryption**: GitHub OAuth tokens encrypted at rest with Fernet
- **Rate Limiting**: slowapi with per-endpoint limits (e.g., 30 webhooks/min)
- **CORS**: Configurable origins (currently wildcard for development)

## Performance Indexes

```sql
-- Dashboard PR listing
CREATE INDEX ix_pull_requests_repo_id_created_at
ON pull_requests (repo_id, created_at DESC);

-- Job status filtering
CREATE INDEX ix_analysis_jobs_pr_id_status
ON analysis_jobs (pull_request_id, status);

-- Commit SHA deduplication
CREATE INDEX ix_analysis_jobs_commit_sha
ON analysis_jobs (commit_sha);
```

## Infrastructure

| Component     | Technology        | Purpose                    |
|---------------|-------------------|----------------------------|
| API Server    | FastAPI + Uvicorn | HTTP/WebSocket handling    |
| Task Queue    | Celery + Redis    | Async job processing       |
| Database      | PostgreSQL 16     | Persistent data storage    |
| Cache/Broker  | Redis 7           | Cache, queue, pub/sub      |
| LLM           | Claude (Anthropic)| AI code review             |
| Migrations    | Alembic           | Schema version control     |
| CI/CD         | GitHub Actions    | Lint + test on every push  |
| Deployment    | Docker + Render   | Production hosting         |

## Testing Strategy

- **76 tests** across unit, integration, and edge case suites
- **Unit tests**: Models, services (cache, GitHub client, LLM), auth
- **Integration tests**: Full webhook→task→DB pipeline with mocked externals
- **Edge case tests**: Malformed payloads, missing fields, expired tokens, invalid UUIDs
- **CI**: GitHub Actions runs `ruff` lint + `pytest` with Postgres/Redis services
