"""
main.py — FastAPI application factory.

This is the entry point. Uvicorn runs this file:
  uvicorn app.main:app
        │    │    └── the `app` variable in this file
        │    └── this module
        └── the package

lifespan() handles startup and shutdown — cleaner than @app.on_event (deprecated).
"""

import asyncio
import structlog
import redis.asyncio as aioredis
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.api.v1.endpoints import health, auth, github, webhooks, websockets
from app.services.websocket_manager import listen_to_redis_pubsub
from app.core.rate_limit import limiter
from app.core.exceptions import PRScopeError, prscope_exception_handler, unhandled_exception_handler
from app.core.middleware import RequestIDMiddleware

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Code before `yield` runs on startup.
    Code after `yield` runs on shutdown.
    """
    logger.info(
        "prscope_starting",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
    )
    
    # Start Redis pub/sub listener for WebSockets
    redis_client = aioredis.from_url(settings.REDIS_URL)
    pubsub_task = asyncio.create_task(listen_to_redis_pubsub(redis_client))
    
    yield
    
    pubsub_task.cancel()
    await redis_client.aclose()
    logger.info("prscope_shutdown")


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "AI-powered GitHub PR review engine. "
        "Webhook → Queue → Worker → GitHub comments."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────────────
# Order matters: middleware added LAST runs FIRST (outermost).
# So RequestIDMiddleware is added last to ensure every request gets an ID
# before any other middleware (CORS, rate limiting, etc.) runs.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── Exception Handlers ────────────────────────────────────────────────────────
# Catch all PRScopeError subclasses → consistent JSON error envelope
app.add_exception_handler(PRScopeError, prscope_exception_handler)
# Catch-all for truly unexpected errors → clean 500 JSON instead of HTML
app.add_exception_handler(Exception, unhandled_exception_handler)

# ── Request Tracing ───────────────────────────────────────────────────────────
# Added last = runs first (outermost middleware). Every request gets an
# X-Request-ID before any other processing happens.
app.add_middleware(RequestIDMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(github.router, prefix="/api/v1", tags=["github"])
app.include_router(webhooks.router, prefix="/api/v1", tags=["webhooks"])
app.include_router(websockets.router, prefix="/api/v1", tags=["websockets"])

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
