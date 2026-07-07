"""
middleware.py — Custom middleware for request tracing and observability.

The X-Request-ID middleware assigns a unique identifier to every incoming request.
This ID flows through:
  - All log entries (via structlog context)
  - Error responses (via the exception handler's error envelope)
  - The response header (so clients can reference it in support requests)

Why this matters:
  When a user reports "I got a 500 error," you can ask them for the request ID
  from the response header. Then you can grep your logs for that exact request
  and see every step it took — which endpoint, which DB queries, which external
  API calls, and exactly where it failed.
"""

import uuid
import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Assigns an X-Request-ID to every incoming request.

    If the client sends an X-Request-ID header, we reuse it (common in
    microservice architectures where a gateway sets the ID).
    If not, we generate a UUID4.

    The ID is stored on request.state so exception handlers can access it,
    and it's also added to the response headers.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Reuse client-provided ID, or generate a new one
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Log the incoming request
        start_time = time.time()
        logger.info(
            f"→ {request.method} {request.url.path}",
            extra={"request_id": request_id},
        )

        response = await call_next(request)

        # Calculate duration and log the outgoing response
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.info(
            f"← {request.method} {request.url.path} [{response.status_code}] {duration_ms}ms",
            extra={"request_id": request_id, "duration_ms": duration_ms},
        )

        # Add the request ID to the response so the client can reference it
        response.headers["X-Request-ID"] = request_id
        return response
