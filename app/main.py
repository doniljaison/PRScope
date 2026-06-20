"""
main.py — FastAPI application factory.

This is the entry point. Uvicorn runs this file:
  uvicorn app.main:app
        │    │    └── the `app` variable in this file
        │    └── this module
        └── the package

lifespan() handles startup and shutdown — cleaner than @app.on_event (deprecated).
"""

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1.endpoints import health

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Code before `yield` runs on startup.
    Code after `yield` runs on shutdown.

    Future: add DB connection pool warmup, Redis ping check, etc.
    """
    logger.info(
        "prscope_starting",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
    )
    yield
    logger.info("prscope_shutdown")


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "AI-powered GitHub PR review engine. "
        "Webhook → Queue → Worker → GitHub comments."
    ),
    docs_url="/docs",     # Swagger UI at http://localhost:8000/docs
    redoc_url="/redoc",   # Alternative docs at /redoc
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # ← Tighten this to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
# Each feature area is a separate router (file). Register them here.
# Pattern: app.include_router(router, prefix="/api/v1", tags=["..."])

app.include_router(health.router, prefix="/api/v1", tags=["health"])

# Future routers (uncomment as you build each feature):
# from app.api.v1.endpoints import auth, webhooks, repos, prs
# app.include_router(auth.router,     prefix="/api/v1", tags=["auth"])
# app.include_router(webhooks.router, prefix="/api/v1", tags=["webhooks"])
# app.include_router(repos.router,    prefix="/api/v1", tags=["repos"])
# app.include_router(prs.router,      prefix="/api/v1", tags=["pull-requests"])


# ── Root endpoint ─────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    """Landing page — useful when someone hits the bare URL."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health",
    }
