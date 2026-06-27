# Day 2 Report — Database Layer: SQLAlchemy, Models, and First Migration

**Date:** 2026-06-26
**Focus:** Async database integration, ORM models, Alembic migrations

---

## What Was Done

### 1. Async SQLAlchemy Engine & Session Factory
- Created `app/database.py` with `create_async_engine` (asyncpg driver), connection pooling (`pool_size=5`, `max_overflow=10`), and `pool_pre_ping=True`
- Created `app/api/deps.py` with `get_db()` — a FastAPI dependency that yields a per-request session with auto commit/rollback

### 2. User Model & Schema
- Created `app/models/base.py` — `TimestampMixin` with `created_at`/`updated_at` using `server_default=func.now()`
- Created `app/models/user.py` — `User` ORM model with UUID primary key, email uniqueness constraint, indexed email column
- Created `app/schemas/user.py` — Pydantic schemas (`UserCreate`, `UserRead`) separating API contract from DB model

### 3. Alembic Configuration
- Created `alembic/env.py` — async migration runner using `async_engine_from_config`, imports all models for autogenerate
- Created `alembic/script.py.mako` — template for auto-generated migration files
- Updated `app/config.py` — removed unused sync DATABASE_URL, using single async URL for both app and Alembic

### 4. First Migration
- Generated migration `7445ce4acc1a_create_users_table.py` via `alembic revision --autogenerate`
- Applied with `alembic upgrade head` — creates `users` table and `ix_users_email` index
- Verified via `psql`: `\dt` shows `users` and `alembic_version`

### 5. Health Endpoint Wired to Real DB
- Updated `app/api/v1/endpoints/health.py` — `/health/detailed` now uses `Depends(get_db)` and runs `SELECT 1` against real Postgres
- Confirmed `"database": "ok"` in response

### 6. Tests (6 passing)
- `test_health_returns_ok` — basic health check
- `test_detailed_health_checks_database_and_redis` — real DB + Redis connectivity
- `test_root_endpoint` — app info endpoint
- `test_create_user` — ORM model defaults (UUID, is_active, created_at)
- `test_query_user_by_email` — flush-then-query within same session
- `test_email_must_be_unique` — IntegrityError on duplicate email

### 7. Infrastructure Fix
- Added `./alembic:/app/alembic` bind mount to `docker-compose.yml` — migration files generated inside Docker now persist to host filesystem

---

## Bugs Encountered

### Bug #2: `RuntimeError: Task got Future attached to a different loop`
- **What happened:** User model tests failed because `AsyncSessionLocal` from `app/database.py` was bound to the app's event loop, but pytest-asyncio creates its own event loop per test
- **Fix:** Created test-scoped engine inside the `db_session` fixture instead of reusing the app's module-level engine
- **Full details in BUGS.md**

### Issue: Migration files not persisting to host
- **What happened:** `alembic revision --autogenerate` ran inside Docker, but `alembic/` directory wasn't bind-mounted — files existed only in the container layer and were lost on recreation
- **Fix:** Added `./alembic:/app/alembic` bind mount to `docker-compose.yml`

---

## Checklist
- [x] `alembic revision --autogenerate` generated a real migration
- [x] Read the generated migration file before running it
- [x] `alembic upgrade head` ran without errors
- [x] `\dt` in psql shows `users` and `alembic_version` tables
- [x] `/api/v1/health/detailed` shows `"database": "ok"`
- [x] `pytest tests/ -v` → 6 tests pass
- [x] Verified rollback pattern leaves `users` table empty after tests
- [x] 7 clean commits made
- [x] BUGS.md updated with event loop mismatch bug

---

## Commits (7)
1. `feat(db): add async SQLAlchemy engine and per-request session factory`
2. `feat(models): add User model with TimestampMixin and Pydantic schemas`
3. `chore(alembic): configure async migrations against app settings`
4. `feat(db): add migration to create users table`
5. `feat(health): replace placeholder DB check with real Postgres ping`
6. `test(db): add db_session fixture and User model tests with rollback isolation`
7. `docs: update README with alembic commands, add alembic bind mount, document event loop bug`
