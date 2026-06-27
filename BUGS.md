# BUGS.md — Hard Problems & How I Fixed Them

> This file documents the toughest bugs hit during development.
> Every entry here is a real problem-solving story — the kind interviewers ask about.

---

## Template

```
### Bug #N: [Short title]

**Date:** YYYY-MM-DD
**Layer affected:** API / Worker / DB / Cache / WebSocket

**Symptom:**
What you saw. Error message, wrong behavior, etc.

**Root cause:**
Why it actually happened. The real reason, not the surface error.

**Failed approaches:**
What you tried that didn't work and why.

**Fix:**
What actually solved it, with code snippet if helpful.

**What I learned:**
The principle this taught you. One sentence.
```

---

*Start filling this in from Day 1. Every frustrating error is an entry.*

---

### Bug #1: Docker build fails — `uv pip install -e ".[dev]"` can't find importable package

**Date:** 2026-06-20
**Layer affected:** Docker / Build

**Symptom:**
`docker compose up --build` fails at Dockerfile step 6/7 with:
```
error: Failed to resolve `.[dev]`
  Caused by: The directory `/app` must contain a `setup.py`, `setup.cfg`, or
  `pyproject.toml` file to be installable as an editable package
  Caused by: Package is not-importable
```

**Root cause:**
The Dockerfile copies `pyproject.toml` before the source code (for Docker layer caching), then runs `uv pip install --system -e ".[dev]"`. The `-e` (editable) flag requires the package to be **importable** — meaning `app/__init__.py` must exist. But `COPY . .` (which includes the source code) comes *after* the install step. So at install time, there's a `pyproject.toml` but no actual Python package to install.

This is a tension between Docker layer caching (copy deps first, install, then copy code) and editable installs (need the package to exist).

**Failed approaches:**
- Considered removing `-e` flag entirely, but that would mean code changes require a full rebuild (losing the bind-mount hot-reload benefit).
- Considered moving `COPY . .` before the install, but that destroys Docker layer caching — every code change would reinstall all dependencies.

**Fix:**
Add a minimal package stub before the install step:
```dockerfile
# Create the minimal package structure needed for editable install
RUN mkdir -p app && touch app/__init__.py

# Install all dependencies
RUN uv pip install --system -e ".[dev]"

# THEN copy source code (overwrites the stub)
COPY . .
```

The `COPY . .` at the end overwrites the empty stub with the real `app/__init__.py`. Layer caching is preserved because `pyproject.toml` changes still trigger a rebuild of the install layer, but code-only changes only rebuild the final `COPY . .` layer.

**What I learned:**
Editable installs (`-e`) require a valid package structure at install time — Docker layer caching strategies must account for this by creating a minimal stub before the install step.

---

### Bug #2: `RuntimeError: Task got Future attached to a different loop` in async DB tests

**Date:** 2026-06-20
**Layer affected:** Testing / DB / Async

**Symptom:**
`test_create_user` and `test_email_must_be_unique` fail with:
```
RuntimeError: Task <Task pending name='Task-38' coro=<test_email_must_be_unique()>>
got Future <Future pending> attached to a different loop
```
The health tests (which don't use `db_session`) pass fine. Only the model tests that directly use the `db_session` fixture fail.

**Root cause:**
The `AsyncSessionLocal` factory in `app/database.py` is module-level. When it's first imported, the underlying `create_async_engine` binds its connection pool to whatever asyncio event loop is running at that time (the app's event loop during startup).

When `pytest-asyncio` runs tests, it creates its OWN event loop per test function. The `db_session` fixture was using `AsyncSessionLocal` from `app/database.py`, which had a connection pool bound to a DIFFERENT loop. `asyncpg` then tries to use a connection from that pool on the test's loop → `RuntimeError`.

This is the classic async Python "event loop mismatch" bug. It's essentially the async equivalent of threading bugs — resource created on one loop, used on another.

**Failed approaches:**
- Initially tried reusing `AsyncSessionLocal` directly from `app.database` — this was the approach from the original conftest, and it fails due to the loop mismatch.

**Fix:**
Create a test-scoped engine and session factory inside the `db_session` fixture, so the connection pool is always created on the test's event loop:
```python
@pytest.fixture
async def db_session():
    test_engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, ...)
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()
    await test_engine.dispose()
```

The `dispose()` call is critical — without it, connections leak between tests.

**What I learned:**
In async Python, connection pools are bound to the event loop they're created on. Tests run on different loops than the app, so test fixtures must create their own engine/pool rather than reusing the app's module-level one.
