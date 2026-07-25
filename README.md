# PRScope 🔍

[![CI](https://github.com/doniljaison/PRScope/actions/workflows/ci.yml/badge.svg)](https://github.com/doniljaison/PRScope/actions/workflows/ci.yml)
![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)
![Tests](https://img.shields.io/badge/tests-76%20passed-brightgreen.svg)

> AI-powered GitHub PR review engine — event-driven webhook pipeline built with FastAPI.

When a developer opens a pull request, PRScope automatically fetches the diff, queues an async analysis job via Celery, runs an AI code review using Claude, and stores the results with optional GitHub comment posting. Real-time job status is streamed via WebSockets.

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

1. GitHub sends `POST /webhooks/github` (HMAC-SHA256 signed)
2. FastAPI verifies signature, checks idempotency via Redis `SET NX`
3. Repository and PullRequest records are upserted in PostgreSQL
4. Celery task is dispatched to Redis queue
5. Worker fetches PR diff from GitHub API (cached in Redis)
6. Worker sends diff to Claude for AI code review
7. AnalysisJob + ReviewComment records are written to the database
8. Status updates are published via Redis Pub/Sub → WebSocket clients
9. If `ENABLE_GITHUB_POSTING=True`, comments are posted back to GitHub

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI (async, ASGI) |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 (async) + Alembic |
| Cache / Broker | Redis 7 (hiredis) |
| Task Queue | Celery 5 with DLQ and exponential backoff |
| AI Code Review | Anthropic Claude (Sonnet) |
| Real-time | WebSockets (native FastAPI) + Redis Pub/Sub |
| HTTP Client | httpx + tenacity (retries with exponential backoff) |
| Auth | JWT (python-jose) + bcrypt + GitHub OAuth |
| Rate Limiting | slowapi (Redis-backed) |
| Logging | structlog (structured JSON) |
| CI/CD | GitHub Actions (lint + test) |
| Deployment | Docker + Render.com |
| Testing | pytest + pytest-asyncio + respx (76 tests) |

---

## Project Structure

```
PRScope/
├── app/
│   ├── main.py                     # FastAPI app entry point
│   ├── config.py                   # Settings via pydantic-settings
│   ├── database.py                 # Async SQLAlchemy engine + session
│   ├── api/
│   │   ├── deps.py                 # Dependencies (auth, db, redis)
│   │   └── v1/endpoints/
│   │       ├── health.py           # GET /health, /health/detailed
│   │       ├── auth.py             # Register, login, refresh, logout
│   │       ├── github.py           # GitHub OAuth flow
│   │       ├── webhooks.py         # Webhook receiver with idempotency
│   │       ├── websockets.py       # WS /ws/jobs/{job_id}
│   │       └── analytics.py        # Repo stats and recent analyses
│   ├── models/                     # SQLAlchemy ORM models
│   ├── schemas/                    # Pydantic request/response models
│   ├── services/                   # Business logic layer
│   │   ├── github_client.py        # GitHub API (cached, retried)
│   │   ├── llm_client.py           # Claude API wrapper
│   │   ├── cache.py                # Redis cache-aside helper
│   │   └── websocket_manager.py    # WebSocket connection manager
│   ├── workers/
│   │   ├── celery_app.py           # Celery config
│   │   └── tasks.py                # Analysis task + DLQ handler
│   └── core/
│       ├── security.py             # JWT + bcrypt
│       ├── encryption.py           # Fernet for GitHub tokens
│       ├── exceptions.py           # Exception hierarchy + handlers
│       ├── middleware.py           # X-Request-ID tracing
│       └── rate_limit.py           # slowapi config
├── alembic/                        # DB migrations
├── tests/                          # 76 tests (unit, integration, edge)
├── docker/Dockerfile
├── Dockerfile.prod                 # Multi-stage production build
├── docker-compose.yml              # api + worker + db + redis
├── render.yaml                     # One-click Render deployment
├── .github/workflows/ci.yml       # GitHub Actions CI
├── SYSTEM_DESIGN.md                # Architecture decisions
├── BUGS.md                         # Bug journal with solutions
└── everyday_documentation/         # Daily progress reports
```

---

## Getting Started

### Prerequisites
- Docker Desktop installed and running
- Git

### Setup

```bash
# Clone and configure
git clone https://github.com/doniljaison/PRScope.git
cd PRScope
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, GITHUB_WEBHOOK_SECRET, SECRET_KEY

# Start all services
docker compose up --build

# Run database migrations
docker compose exec api alembic upgrade head

# Visit the API docs
open http://localhost:8000/docs
```

### Verify

```bash
curl http://localhost:8000/api/v1/health
# → {"status": "ok", "app": "PRScope", ...}

curl http://localhost:8000/api/v1/health/detailed
# → {"status":"ok","checks":{"redis":"ok","database":"ok"}, ...}
```

---

## Development

```bash
docker compose logs -f api          # View logs
docker compose exec api pytest -v   # Run tests
docker compose exec db psql -U prscope -d prscope  # DB shell
docker compose exec redis redis-cli                 # Redis shell
docker compose exec api alembic upgrade head         # Run migrations
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | App info |
| `GET` | `/api/v1/health` | Basic health check |
| `GET` | `/api/v1/health/detailed` | DB + Redis connectivity |
| `POST` | `/api/v1/auth/register` | Create account |
| `POST` | `/api/v1/auth/login` | Get JWT tokens |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `POST` | `/api/v1/auth/logout` | Revoke refresh token |
| `GET` | `/api/v1/auth/me` | Current user profile |
| `GET` | `/api/v1/auth/github` | Start GitHub OAuth |
| `GET` | `/api/v1/auth/github/callback` | OAuth callback |
| `POST` | `/api/v1/webhooks/github` | Webhook receiver (HMAC) |
| `GET` | `/api/v1/repos/{id}/stats` | Repository analytics |
| `GET` | `/api/v1/repos/{id}/recent` | Recent analysis jobs |
| `WS` | `/api/v1/ws/jobs/{job_id}` | Real-time job status |

Interactive docs with examples at `/docs` when running locally.

---

## Environment Variables

| Variable | Description |
|---|---|
| `POSTGRES_*` | Database connection details |
| `REDIS_URL` | Redis connection string |
| `SECRET_KEY` | JWT signing key (`openssl rand -hex 32`) |
| `ANTHROPIC_API_KEY` | Claude API key for code review |
| `GITHUB_CLIENT_ID` | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth App client secret |
| `GITHUB_WEBHOOK_SECRET` | Secret for webhook HMAC verification |
| `ENCRYPTION_KEY` | Fernet key for GitHub token encryption |
| `ENABLE_GITHUB_POSTING` | `true` to post comments to GitHub (default: `false`) |

---

## Design Decisions

See [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md) for the full architecture document.

Key highlights:

- **Event-driven over polling** — GitHub pushes events to us, no wasted API calls
- **Celery over background threads** — retries, DLQ, priority routing, horizontal scaling
- **Redis as multi-purpose infra** — queue, cache, pub/sub, idempotency, session store
- **Webhook idempotency** — Redis `SET NX` prevents duplicate analysis from GitHub retries
- **Commit SHA deduplication** — skip LLM calls for already-analyzed commits
- **Safety-first posting** — `ENABLE_GITHUB_POSTING` flag gates real GitHub comment posting

---

## BUGS.md

See [BUGS.md](./BUGS.md) — a journal of hard bugs encountered and how they were fixed.
