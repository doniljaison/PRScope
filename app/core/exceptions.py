"""Centralized exception hierarchy and FastAPI exception handlers."""

import logging
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ── Exception Hierarchy ──────────────────────────────────────────────────────

class PRScopeError(Exception):
    """Base exception — all custom errors inherit from this."""
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "An unexpected error occurred", details: Any = None):
        self.message = message
        self.details = details
        super().__init__(self.message)


class AuthenticationError(PRScopeError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "AUTHENTICATION_ERROR"


class AuthorizationError(PRScopeError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "AUTHORIZATION_ERROR"


class NotFoundError(PRScopeError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"


class ConflictError(PRScopeError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"


class RateLimitError(PRScopeError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "RATE_LIMIT_EXCEEDED"


class WebhookVerificationError(PRScopeError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "WEBHOOK_VERIFICATION_FAILED"


class ExternalServiceError(PRScopeError):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "EXTERNAL_SERVICE_ERROR"


class GitHubAPIError(ExternalServiceError):
    error_code = "GITHUB_API_ERROR"


class GitHubRateLimitError(GitHubAPIError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "GITHUB_RATE_LIMIT"


class LLMError(ExternalServiceError):
    error_code = "LLM_ERROR"


class LLMParseError(LLMError):
    error_code = "LLM_PARSE_ERROR"


# ── Exception Handlers ──────────────────────────────────────────────────────

def _build_error_response(
    request: Request, status_code: int, error_code: str,
    message: str, details: Any = None,
) -> JSONResponse:
    """Build a consistent JSON error envelope with request_id."""
    request_id = getattr(request.state, "request_id", "unknown")
    body: dict[str, Any] = {
        "error": {"code": error_code, "message": message, "request_id": request_id}
    }
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


async def prscope_exception_handler(request: Request, exc: PRScopeError) -> JSONResponse:
    """Catch PRScopeError subclasses → consistent JSON error."""
    logger.warning(f"PRScopeError: {exc.error_code} — {exc.message}")
    return _build_error_response(
        request, exc.status_code, exc.error_code, exc.message, exc.details,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unexpected errors → clean JSON instead of HTML."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(f"Unhandled exception (request_id={request_id}): {exc}")
    return _build_error_response(
        request, status.HTTP_500_INTERNAL_SERVER_ERROR,
        "INTERNAL_ERROR", "An unexpected error occurred. Please try again later.",
    )
