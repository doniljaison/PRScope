# PRScope — Full Context History

> Use this file to onboard any AI model mid-project. It contains the complete state, decisions made, and what's left.

---

## What Is PRScope?

An AI-powered GitHub PR review engine built with FastAPI. When a PR is opened, it fetches the diff, queues an async analysis job via Celery, runs AI code review via LLM, and posts inline comments back on the PR. Real-time status via WebSockets.

**Tech stack:** FastAPI, PostgreSQL (asyncpg), Redis, Celery, SQLAlchemy 2.0 (async), Alembic, python-jose (JWT), passlib (bcrypt), httpx, structlog, Docker Compose.

**30-day plan:** [documentation/project_idea.md](file:///c:/vscode/PRScope/documentation/project_idea.md)

---

## Project Structure

```
PRScope/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory, lifespan, routers
│   ├── config.py             # Pydantic Settings (all from .env)
│   ├── database.py           # Async engine, Base, AsyncSessionLocal
│   ├── api/
│   │   ├── deps.py           # get_db() dependency (yields session per request)
│   │   └── v1/endpoints/
│   │       └── health.py     # /health and /health/detailed
│   ├── models/
│   │   ├── base.py           # TimestampMixin (created_at, updated_at)
│   │   └── user.py           # User model (UUID pk, email, hashed_password)
│   ├── schemas/
│   │   └── user.py           # UserCreate, UserRead
│   ├── core/                 # (empty — __init__.py only)
│   ├── services/             # (empty — __init__.py only)
│   └── workers/              # (empty — __init__.py only)
├── tests/
│   ├── conftest.py           # client, db_session fixtures (test-scoped engine)
│   ├── api/test_health.py    # 3 health endpoint tests
│   └── test_models/test_user.py  # 3 user model tests
├── alembic/
│   ├── env.py                # Async migration runner, imports models
│   ├── script.py.mako
│   └── versions/
│       └── 7445ce4acc1a_create_users_table.py
├── docker/Dockerfile
├── docker-compose.yml        # api + db + redis, bind mounts for app/ and alembic/
├── pyproject.toml            # All deps declared, pytest asyncio_mode=auto
├── .env                      # Dev secrets (not in git)
├── .gitignore                # Excludes documentation/, fromclaude/, .env
├── BUGS.md                   # 2 bugs documented
├── README.md
├── documentation/            # (gitignored) planning docs
├── fromclaude/               # (gitignored) reference files from Claude
└── everyday_documentation/   # Daily reports (in git)
    ├── day1/day1_report.md
    └── day2/day2_report.md
```

---

## Completed Days

### Day 1 — Environment & Project Structure (5 commits)
- Docker Compose with FastAPI + PostgreSQL + Redis
- Project scaffold with all `__init__.py` files
- FastAPI app factory with CORS, structured logging
- `/health` and `/health/detailed` endpoints
- 2 tests passing
- **Bug #1:** Dockerfile editable install fails without source stub

### Day 2 — Database Layer (7 commits)
- Async SQLAlchemy engine with asyncpg + connection pooling
- `User` model with UUID pk, `TimestampMixin`, Pydantic schemas
- Alembic async migration config + first migration (users table)
- `/health/detailed` wired to real Postgres (SELECT 1)
- 6 tests passing (3 health + 3 user model)
- `./alembic:/app/alembic` bind mount fix
- **Bug #2:** Event loop mismatch — test engine must be test-scoped

---

## Current State (as of starting Day 3)
- **13 commits** on `master`, clean working tree
- **6 tests** passing
- **Tables:** `users`, `alembic_version`
- **Docker:** 3 containers (api, db, redis) — start with `docker compose up -d`
- **Docker path issue:** Docker not in PATH. Use: `$env:PATH = "C:\Program Files\Docker\Docker\resources\bin;" + $env:PATH`

---

## Key Patterns & Conventions

1. **All models** inherit from `Base` (from `app/database.py`) and `TimestampMixin`
2. **UUIDs** for all primary keys (not auto-increment ints)
4. **Test isolation:** test-scoped engine to avoid event loop mismatch, `flush()` not `commit()`, fixture does `rollback()`
5. **Comments:** extensive inline teaching comments in all files
6. **Commits:** conventional commit format (`feat:`, `test:`, `chore:`, `docs:`)
7. **Docker commands:** always prepend PATH fix, run tests via `docker compose exec api pytest tests/ -v`
8. **Alembic:** run inside container: `docker compose exec api alembic revision --autogenerate -m "..."`
9. **New models**

## What We've Accomplished So Far (Up to Day 7)

### Initial Setup (Days 1-2)
- Fast API factory pattern set up.
- Redis & Postgres configured in `docker-compose.yml` and `app/config.py`.
- Health endpoints and test database connections established.
- User ORM model & basic migrations implemented (Alembic working).

### Database Models & Authentication (Days 3-7)
- **Day 3-4 (Models):** `Repository`, `PullRequest`, `AnalysisJob`, and `ReviewComment` models created. Tested and seeded with mock data.
- **Day 5-6 (JWT Auth):** Full JWT authentication flow implemented (`login`, `register`, `refresh`, `logout`, `me`). Redis is used to store/revoke refresh tokens. Tests updated and `get_db` dependency overrides configured in Pytest to fix event loop mismatch.
- **Day 7 (GitHub OAuth):** `GET /auth/github` and `GET /auth/github/callback` implemented. Connected `passlib` bcrypt hashing for normal login. Set up `cryptography` Fernet encryption for GitHub tokens. Overcame bcrypt v4 incompatibility issue by pinning `bcrypt<4.0.0` in `pyproject.toml`.

## Important Tech Details / Gotchas Discovered
1. **Pytest Asyncio Mismatches:** If multiple tests hit the Fast API database endpoints without overriding the `get_db` dependency in the client fixture, you'll encounter a `RuntimeError: Task got Future attached to a different loop`.
2. **Docker Volumes:** Remember to map `./tests:/app/tests` inside `docker-compose.yml` so you can test quickly without rebuilding.
3. **Passlib & Bcrypt v4:** `passlib` v1.7.4 is incompatible with `bcrypt>=4.0.0` during the `_detect_wrap_bug` step. We pinned `bcrypt<4.0.0` in `pyproject.toml` to solve this.

## Next Step
- Once Docker finishes rebuilding, run tests `pytest` to confirm everything is green.
- Then, proceed to Day 8: Integrating GitHub Webhooks.

## GitHub OAuth Setup (for Day 7)
1. Go to https://github.com/settings/developers
2. Click "OAuth Apps" → "New OAuth App"
3. Fill in:
   - **Application name:** PRScope (Dev)
   - **Homepage URL:** http://localhost:8000
   - **Authorization callback URL:** http://localhost:8000/api/v1/auth/github/callback
4. Copy `Client ID` → paste into `.env` as `GITHUB_CLIENT_ID`
5. Generate a client secret → paste into `.env` as `GITHUB_CLIENT_SECRET`
6. Generate an encryption key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` → paste into `.env` as `ENCRYPTION_KEY`
