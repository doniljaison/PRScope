# PRScope 🔍

> AI-powered GitHub PR review engine — event-driven webhook pipeline built with FastAPI.

When a developer opens a pull request, PRScope automatically fetches the diff, queues an async analysis job, runs an AI code review, and posts inline comments back to GitHub. Real-time job status is streamed via WebSockets.

---

## Architecture

```
GitHub Webhook → FastAPI → Redis Queue → Celery Worker → GitHub API (post comments)
                    │                          │
                 PostgreSQL              OpenAI / Claude API
                    │
              WebSocket Hub → Connected clients (real-time status)
```

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI (async, ASGI) |
| Database | PostgreSQL 15 + SQLAlchemy (async) + Alembic |
| Cache / Broker | Redis 7 |
| Task Queue | Celery |
| Real-time | WebSockets (native FastAPI) |
| External APIs | GitHub REST API, OpenAI / Anthropic |
| Containerization | Docker + Docker Compose |
| Testing | pytest + pytest-asyncio |
| CI | GitHub Actions |

---

## Project Structure

```
prscope/
├── app/
│   ├── main.py                  # FastAPI app — entry point
│   ├── config.py                # All settings via pydantic-settings
│   ├── database.py              # Async SQLAlchemy engine + session
│   ├── api/
│   │   ├── deps.py              # Shared dependencies (auth, db session)
│   │   └── v1/
│   │       └── endpoints/
│   │           ├── health.py    # GET /health
│   │           ├── auth.py      # Register, login, refresh token
│   │           ├── webhooks.py  # POST /webhooks/github
│   │           ├── repos.py     # CRUD for connected repos
│   │           └── prs.py       # PR list, analysis results
│   ├── models/                  # SQLAlchemy ORM models (DB tables)
│   │   ├── user.py
│   │   ├── repository.py
│   │   ├── pull_request.py
│   │   └── analysis_job.py
│   ├── schemas/                 # Pydantic models (request/response shapes)
│   │   ├── user.py
│   │   ├── repository.py
│   │   ├── pull_request.py
│   │   └── analysis_job.py
│   ├── services/                # Business logic (no FastAPI deps here)
│   │   ├── github_client.py     # GitHub REST API wrapper
│   │   ├── llm_client.py        # OpenAI / Claude wrapper
│   │   └── cache.py             # Redis cache helpers
│   ├── workers/
│   │   ├── celery_app.py        # Celery instance + config
│   │   └── tasks/
│   │       └── analysis.py      # analyze_pr task
│   └── core/
│       ├── security.py          # JWT, password hashing
│       └── exceptions.py        # Custom exceptions + handlers
├── alembic/                     # DB migration files
│   └── versions/
├── tests/
│   ├── conftest.py              # Shared pytest fixtures
│   └── api/
│       └── test_health.py
├── docker/
│   └── Dockerfile
├── .env.example                 # Copy this to .env and fill in values
├── .gitignore
├── docker-compose.yml
├── pyproject.toml               # Dependencies + tool config
├── alembic.ini
└── BUGS.md                      # Document hard bugs as you hit them
```

---

## Getting Started

### Prerequisites
- Docker Desktop installed and running
- Git

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/prscope.git
cd prscope

# 2. Copy env file and fill in values
cp .env.example .env

# 3. Start all services
docker compose up --build

# 4. Visit the API
open http://localhost:8000/docs
```

### Verify everything is running
```bash
curl http://localhost:8000/api/v1/health
# → {"status": "ok", "app": "PRScope", ...}

curl http://localhost:8000/api/v1/health/detailed
# → checks DB + Redis connectivity
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
```

---

## Environment Variables

See `.env.example` for all required variables.

| Variable | Description |
|---|---|
| `POSTGRES_*` | Database connection details |
| `REDIS_URL` | Redis connection string |
| `SECRET_KEY` | JWT signing key (generate with `openssl rand -hex 32`) |
| `GITHUB_CLIENT_ID` | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth App client secret |
| `GITHUB_WEBHOOK_SECRET` | Random secret for signing webhooks |
| `OPENAI_API_KEY` | OpenAI API key for code review |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | App info |
| GET | `/api/v1/health` | Basic health check |
| GET | `/api/v1/health/detailed` | DB + Redis health check |
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Get JWT tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/github` | Start GitHub OAuth flow |
| POST | `/api/v1/webhooks/github` | GitHub webhook receiver |
| GET | `/api/v1/repos` | List connected repos |
| GET | `/api/v1/prs/{id}/analysis` | Get analysis result |
| WS | `/ws/jobs/{job_id}` | Real-time job status stream |

Full interactive docs at `/docs` when running locally.

---

## BUGS.md

See [BUGS.md](./BUGS.md) — a running log of hard bugs encountered and how they were fixed.
This is intentional: debugging is the job.
