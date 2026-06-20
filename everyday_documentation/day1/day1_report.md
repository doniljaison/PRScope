# Day 1 Report — Environment, Docker, and First Running API

**Date:** 2026-06-20
**Project:** PRScope — AI-powered GitHub PR review engine

---

## Summary

Day 1 focused on setting up the foundational development environment for the PRScope backend. The goal was to get a fully containerized multi-service stack running locally (FastAPI + PostgreSQL + Redis), create the first working API endpoint, write tests, and push clean commits to GitHub.

---

## What Was Accomplished

### 1. Project Scaffolding
- Initialized the Git repository
- Set up the full project directory structure following best practices:
  - `app/` — FastAPI application code (config, main, API endpoints)
  - `app/api/v1/endpoints/` — Versioned API endpoint modules
  - `app/models/` — SQLAlchemy ORM models (empty, ready for Day 2+)
  - `app/schemas/` — Pydantic request/response models (empty, ready for Day 2+)
  - `app/services/` — Business logic layer (empty, ready for future features)
  - `app/workers/` — Celery background workers (empty, ready for Week 2)
  - `app/core/` — Security, exceptions, shared utilities (empty, ready for future)
  - `tests/` — Test suite with pytest + pytest-asyncio
  - `alembic/` — Database migration infrastructure
  - `docker/` — Dockerfile for containerized builds
- Created all necessary `__init__.py` files for Python package structure
- Created `.gitkeep` in `alembic/versions/` for empty directory tracking

### 2. Docker Containerization
- **docker-compose.yml** — Defines 3 services:
  - `api` (FastAPI with hot-reload via bind mount)
  - `db` (PostgreSQL 15 Alpine with health checks)
  - `redis` (Redis 7 Alpine with health checks)
- **docker/Dockerfile** — Multi-layer build using `python:3.11-slim` + `uv` package manager
  - Leverages Docker layer caching (install deps before copying source)
- Verified `docker compose up --build` starts all services cleanly

### 3. Configuration Management
- **app/config.py** — Centralized settings using `pydantic-settings`:
  - Type-checked environment variables (no scattered `os.getenv()`)
  - Computed fields for `DATABASE_URL` (async) and `DATABASE_URL_SYNC` (Alembic)
  - Singleton pattern via `@lru_cache()`
- **.env.example** — Template with all required environment variables
- **.env** — Local copy (excluded from Git via `.gitignore`)

### 4. FastAPI Application
- **app/main.py** — Application factory with:
  - Modern `lifespan` context manager for startup/shutdown
  - CORS middleware configured
  - Router-based endpoint organization (`include_router`)
  - Root endpoint (`GET /`) returning app info
- **Swagger UI** auto-generated at `/docs`
- **ReDoc** available at `/redoc`

### 5. Health Check Endpoints
- **GET /api/v1/health** — Fast, no-I/O health check
  - Returns `status`, `app`, `version`, `uptime_seconds`
  - Used by load balancers and Docker health checks
- **GET /api/v1/health/detailed** — Deep check with Redis connectivity
  - Gracefully handles Redis being down (returns `"degraded"` status)
  - Database check placeholder for Day 3

### 6. Testing
- **tests/api/test_health.py** — 2 async tests using `httpx.AsyncClient`:
  - `test_health_returns_ok` — verifies `/api/v1/health` response shape
  - `test_root_endpoint` — verifies root endpoint returns app name and docs URL
- Tests run inside Docker container: `docker compose exec api pytest tests/ -v`
- **Result:** All tests passing ✅

### 7. Git History & GitHub
- 4 clean commits following Conventional Commits standard:
  1. `chore: scaffold project with Docker, FastAPI, and Postgres config`
  2. `feat: add FastAPI app factory with settings, CORS, and router setup`
  3. `feat(health): add /health and /health/detailed endpoints with Redis check`
  4. `test: add health endpoint tests using httpx AsyncClient`
- `.gitignore` properly excludes `.env`, `__pycache__/`, `documentation/`, IDE files, etc.
- `documentation/` folder excluded from Git (internal guides only)

---

## Key Technical Decisions

| Decision | Rationale |
|---|---|
| `pydantic-settings` over `os.getenv()` | Type safety, validation at startup, centralized config |
| `async def` endpoints | FastAPI is ASGI-based; async enables concurrent I/O at scale |
| Two health endpoints | `/health` stays fast for LBs; `/detailed` for debugging |
| `uv` over `pip` | 10-100x faster installs, lock file support |
| Docker layer caching | `COPY pyproject.toml` before `COPY .` speeds up rebuilds |
| `structlog` for logging | Structured JSON logs for production observability |
| `APIRouter` for endpoints | Separation of concerns; main.py stays clean as the app grows |

---

## Bugs Encountered

See [BUGS.md](../../BUGS.md) for detailed bug reports with root cause analysis.

---

## Day 1 Checklist Status

- [x] `docker compose up --build` runs without errors
- [x] `curl http://localhost:8000/api/v1/health` returns `{"status": "ok"}`
- [x] `curl http://localhost:8000/api/v1/health/detailed` returns `{"checks": {"redis": "ok"}}`
- [x] http://localhost:8000/docs shows Swagger UI with both endpoints
- [x] `docker compose exec api pytest tests/ -v` → 2 tests pass
- [x] BUGS.md exists in the repo
- [x] No `.env` file on GitHub (in .gitignore)
- [x] Clean commit history with 4 conventional commits

---

## What's Next (Day 2 Preview)

- SQLAlchemy async engine and session factory
- First model: `User`
- Alembic migration to create `users` table
- `/health/detailed` will check real DB connectivity
- Expected: first async SQLAlchemy bug (to be logged in BUGS.md)

---

*Day 1 complete. Foundation is solid. Ready to build.*
