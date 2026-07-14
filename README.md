# PRScope 🔍

> AI-powered GitHub PR review engine — event-driven webhook pipeline built with FastAPI.

When a developer opens a pull request, PRScope automatically fetches the diff, queues an async analysis job via Celery, runs an AI code review using Claude, and posts inline comments back to GitHub. Real-time job status is streamed via WebSockets.

---

## Architecture

```
                    ┌──────────────────────────────────────────────────┐
                    │                  PRScope                        │
                    │                                                  │
 GitHub ──webhook──▶│ FastAPI ──▶ Redis Queue ──▶ Celery Worker       │
                    │    │                           │    │            │
                    │    ▼                           ▼    ▼            │
                    │ PostgreSQL              Claude API  GitHub API   │
                    │    │                         (review) (comment)  │
                    │    ▼                                             │
                    │ WebSocket Hub ──▶ Connected clients (real-time)  │
                    └──────────────────────────────────────────────────┘
```

### Request Flow

```
1. GitHub sends POST /webhooks/github (HMAC-SHA256 signed)
2. FastAPI verifies signature, checks idempotency (Redis)
3. Celery task is dispatched to Redis queue
4. Worker fetches PR diff from GitHub API (cached in Redis)
5. Worker sends diff to Claude for code review
6. Worker publishes status updates via Redis Pub/Sub → WebSocket clients
7. Results stored in PostgreSQL
```

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI (async, ASGI) |
| Database | PostgreSQL 15 + SQLAlchemy 2.0 (async) + Alembic |
| Cache / Broker | Redis 7 (hiredis) |
| Task Queue | Celery 5 |
| AI Code Review | Anthropic Claude 3.5 Sonnet |
| Real-time | WebSockets (native FastAPI) + Redis Pub/Sub |
| HTTP Client | httpx + tenacity (retries with exponential backoff) |
| Auth | JWT (python-jose) + bcrypt + GitHub OAuth |
| Rate Limiting | slowapi (Redis-backed) |
| Logging | structlog (structured JSON) |
| Containerization | Docker + Docker Compose |
| Testing | pytest + pytest-asyncio + respx |

---

## Project Structure

```
PRScope/
├── app/
│   ├── main.py                     # FastAPI app — entry point
│   ├── config.py                   # All settings via pydantic-settings
│   ├── database.py                 # Async SQLAlchemy engine + session
│   ├── api/
│   │   ├── deps.py                 # Shared dependencies (auth, db session)
│   │   └── v1/endpoints/
│   │       ├── health.py           # GET /health, /health/detailed
│   │       ├── auth.py             # Register, login, refresh, logout, me
│   │       ├── github.py           # GitHub OAuth flow
│   │       ├── webhooks.py         # POST /webhooks/github
│   │       ├── websockets.py       # WS /ws/jobs/{job_id}
│   │       └── analytics.py        # GET /repos/{id}/stats, /repos/{id}/recent
│   ├── models/                     # SQLAlchemy ORM models
│   │   ├── user.py                 # User (email + GitHub OAuth)
│   │   ├── repository.py           # Connected GitHub repos
│   │   ├── pull_request.py         # PR records from webhooks
│   │   ├── analysis_job.py         # Analysis job state machine
│   │   └── review_comment.py       # AI-generated review comments
│   ├── schemas/                    # Pydantic request/response models
│   │   ├── user.py, auth.py        # Auth shapes
│   │   ├── repository.py           # Repo shapes
│   │   ├── pull_request.py         # PR shapes
│   │   ├── analysis.py             # Analysis + comment shapes
│   │   └── analytics.py            # Stats + dashboard shapes
│   ├── services/                   # Business logic
│   │   ├── github_client.py        # GitHub REST API (cached, retried)
│   │   ├── llm_client.py           # Claude API wrapper
│   │   ├── cache.py                # Redis cache-aside helper
│   │   ├── websocket_manager.py    # WebSocket connection manager
│   │   ├── auth_service.py         # Token storage helpers
│   │   └── github_oauth.py         # OAuth token exchange
│   ├── workers/
│   │   ├── celery_app.py           # Celery instance + config
│   │   └── tasks.py                # analyze_pr_task + DLQ handler
│   └── core/
│       ├── security.py             # JWT, password hashing
│       ├── encryption.py           # Fernet encryption for GitHub tokens
│       ├── exceptions.py           # Exception hierarchy + handlers
│       ├── middleware.py           # X-Request-ID tracing
│       └── rate_limit.py           # slowapi limiter config
├── alembic/                        # DB migrations
├── tests/                          # 70+ tests (unit, integration, edge cases)
├── docker/Dockerfile
├── docker-compose.yml              # api + worker + db + redis
├── pyproject.toml                  # Dependencies + tool config
├── BUGS.md                         # Hard bugs documented with solutions
└── everyday_documentation/         # Daily progress reports
```

---

## Getting Started

### Prerequisites
- Docker Desktop installed and running
- Git

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/doniljaison/PRScope.git
cd PRScope

# 2. Copy env file and fill in values
cp .env.example .env
# Required: ANTHROPIC_API_KEY, GITHUB_WEBHOOK_SECRET, SECRET_KEY

# 3. Start all services
docker compose up --build

# 4. Run database migrations
docker compose exec api alembic upgrade head

# 5. Visit the API docs
open http://localhost:8000/docs
```

### Verify everything is running
```bash
# Basic health check
curl http://localhost:8000/api/v1/health
# → {"status": "ok", "app": "PRScope", ...}

# Detailed health (DB + Redis connectivity)
curl http://localhost:8000/api/v1/health/detailed
# → {"status":"ok","checks":{"redis":"ok","database":"ok"}, ...}
```

---

## Development

```bash
# View logs
docker compose logs -f api

# Run tests
docker compose exec api pytest tests/ -v

# Open a DB shell
docker compose exec db psql -U prscope -d prscope

# Open a Redis shell
docker compose exec redis redis-cli

# Run a migration
docker compose exec api alembic upgrade head

# Create a new migration
docker compose exec api alembic revision --autogenerate -m "describe the change"
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `POSTGRES_*` | Database connection details |
| `REDIS_URL` | Redis connection string |
| `SECRET_KEY` | JWT signing key (`openssl rand -hex 32`) |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key for code review |
| `GITHUB_CLIENT_ID` | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth App client secret |
| `GITHUB_WEBHOOK_SECRET` | Random secret for webhook HMAC verification |
| `ENCRYPTION_KEY` | Fernet key for encrypting GitHub tokens in DB |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | App info |
| GET | `/api/v1/health` | Basic health check |
| GET | `/api/v1/health/detailed` | DB + Redis connectivity check |
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Get JWT tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/logout` | Revoke refresh token |
| GET | `/api/v1/auth/me` | Get current user profile |
| GET | `/api/v1/auth/github` | Start GitHub OAuth flow |
| GET | `/api/v1/auth/github/callback` | GitHub OAuth callback |
| POST | `/api/v1/webhooks/github` | GitHub webhook receiver (HMAC verified) |
| GET | `/api/v1/repos/{id}/stats` | Repository analytics |
| GET | `/api/v1/repos/{id}/recent` | Recent analysis jobs |
| WS | `/api/v1/ws/jobs/{job_id}` | Real-time job status stream |

Full interactive docs with examples at `/docs` when running locally.

---

## System Design Decisions

- **Event-driven (webhooks) over polling**: GitHub pushes events to us. No wasted API calls.
- **Celery over background threads**: Celery gives us retries, dead letter queues, priority routing, and horizontal scaling. A background thread gives you none of that.
- **Redis for both cache and broker**: One less service to manage. Redis handles Pub/Sub, caching, rate limiting, and Celery brokering.
- **Cache-aside with short TTLs**: We can't guarantee GitHub data stays in sync, so short TTLs (5-10 min) are the pragmatic choice.
- **Commit SHA deduplication**: If the same commit was already analyzed, skip the LLM call entirely (saves money and time).
- **Custom exception hierarchy**: Every error returns a consistent JSON envelope with error code, message, and request ID for debugging.

---

## BUGS.md

See [BUGS.md](./BUGS.md) — a running log of hard bugs encountered and how they were fixed. This is intentional: debugging is the job.
