"""Request tracing middleware — assigns X-Request-ID and logs request/response."""

import uuid
import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assigns X-Request-ID to every request for tracing and debugging."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        start_time = time.time()
        logger.info(f"→ {request.method} {request.url.path}", extra={"request_id": request_id})

        response = await call_next(request)

        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.info(
            f"← {request.method} {request.url.path} [{response.status_code}] {duration_ms}ms",
            extra={"request_id": request_id},
        )

        response.headers["X-Request-ID"] = request_id
        return response
