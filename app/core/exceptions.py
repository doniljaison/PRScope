"""
exceptions.py — Centralized exception hierarchy and FastAPI exception handlers.

All custom exceptions inherit from PRScopeError. This gives us:
  1. A single place to define error codes and messages
  2. Consistent JSON error responses across the entire API
  3. Clean separation between "expected" errors (4xx) and "unexpected" errors (5xx)

Exception hierarchy:
  PRScopeError (base)
  ├── AuthenticationError (401)
  ├── AuthorizationError (403)
  ├── NotFoundError (404)
  ├── ConflictError (409)
  ├── RateLimitError (429)
  ├── ExternalServiceError (502)
  │   ├── GitHubAPIError
  │   │   └── GitHubRateLimitError
  │   └── LLMError
  │       └── LLMParseError
  └── WebhookVerificationError (401)
"""

import logging
import uuid
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ── Base Exception ────────────────────────────────────────────────────────────

class PRScopeError(Exception):
    """
    Base exception for all PRScope errors.

    Subclasses define their own status_code and error_code.
    The global exception handler catches PRScopeError and returns
    a consistent JSON envelope.
    """
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "An unexpected error occurred", details: Any = None):
        self.message = message
        self.details = details
        super().__init__(self.message)


# ── Auth Errors ───────────────────────────────────────────────────────────────

class AuthenticationError(PRScopeError):
    """Invalid or expired credentials."""
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "AUTHENTICATION_ERROR"


class AuthorizationError(PRScopeError):
    """User doesn't have permission for this action."""
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "AUTHORIZATION_ERROR"


# ── Resource Errors ───────────────────────────────────────────────────────────

class NotFoundError(PRScopeError):
    """Requested resource doesn't exist."""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"


class ConflictError(PRScopeError):
    """Resource already exists or state conflict (e.g., duplicate webhook)."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"


class RateLimitError(PRScopeError):
    """Client has exceeded rate limits."""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "RATE_LIMIT_EXCEEDED"


# ── Webhook Errors ────────────────────────────────────────────────────────────

class WebhookVerificationError(PRScopeError):
    """GitHub webhook signature verification failed."""
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "WEBHOOK_VERIFICATION_FAILED"


# ── External Service Errors ──────────────────────────────────────────────────

class ExternalServiceError(PRScopeError):
    """An external API (GitHub, LLM) returned an error."""
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "EXTERNAL_SERVICE_ERROR"


class GitHubAPIError(ExternalServiceError):
    """GitHub API returned an error."""
    error_code = "GITHUB_API_ERROR"


class GitHubRateLimitError(GitHubAPIError):
    """GitHub API rate limit exceeded."""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "GITHUB_RATE_LIMIT"


class LLMError(ExternalServiceError):
    """LLM API (Claude/OpenAI) returned an error."""
    error_code = "LLM_ERROR"


class LLMParseError(LLMError):
    """LLM returned a response that couldn't be parsed as expected."""
    error_code = "LLM_PARSE_ERROR"


# ── Exception Handlers ───────────────────────────────────────────────────────

def _build_error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    """
    Build a consistent JSON error envelope.

    Every error response from PRScope looks like:
    {
      "error": {
        "code": "GITHUB_API_ERROR",
        "message": "GitHub API returned 403: rate limit exceeded",
        "request_id": "abc-123-def",
        "details": null
      }
    }

    The request_id comes from the X-Request-ID header (set by our middleware).
    """
    request_id = getattr(request.state, "request_id", "unknown")

    body: dict[str, Any] = {
        "error": {
            "code": error_code,
            "message": message,
            "request_id": request_id,
        }
    }
    if details is not None:
        body["error"]["details"] = details

    return JSONResponse(status_code=status_code, content=body)


async def prscope_exception_handler(request: Request, exc: PRScopeError) -> JSONResponse:
    """
    Catch all PRScopeError subclasses and return a consistent JSON error.

    This replaces the default FastAPI error handling for our custom exceptions,
    giving us a uniform error format across the entire API.
    """
    logger.warning(
        f"PRScopeError: {exc.error_code} — {exc.message}",
        extra={"error_code": exc.error_code, "status_code": exc.status_code},
    )
    return _build_error_response(
        request=request,
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for unhandled exceptions.

    This ensures that even unexpected errors (like a TypeError deep in our code)
    return a clean JSON response instead of an HTML error page.
    The actual traceback is logged server-side but never exposed to the client.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(
        f"Unhandled exception (request_id={request_id}): {exc}",
        exc_info=True,
    )
    return _build_error_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_ERROR",
        message="An unexpected error occurred. Please try again later.",
    )
