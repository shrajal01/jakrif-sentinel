"""
FastAPI middleware for structured logging context.

Sets request_id and correlation_id context variables on every incoming request.
Logs request start and completion with method, path, status code, and duration.
"""
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.context import request_id, correlation_id, generate_id
from app.core.logging import get_logger

logger = get_logger("api.middleware")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Reads X-Request-ID header (or generates one).
    2. Reads X-Correlation-ID header (or generates one).
    3. Sets contextvars so all downstream logs include these IDs.
    4. Logs request start and completion with timing.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract or generate IDs
        req_id = request.headers.get("X-Request-ID") or generate_id()
        corr_id = request.headers.get("X-Correlation-ID") or generate_id()

        # Set context variables for this request's scope
        req_token = request_id.set(req_id)
        corr_token = correlation_id.set(corr_id)
        
        # Store in request.state for access in route handlers
        request.state.request_id = req_id
        request.state.correlation_id = corr_id

        start_time = time.monotonic()
        logger.info(
            "Request started",
            method=request.method,
            path=str(request.url.path),
        )

        try:
            response = await call_next(request)

            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.info(
                "Request completed",
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

            # Include IDs in response headers for client traceability
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Correlation-ID"] = corr_id

            return response
        finally:
            # Reset context variables
            request_id.reset(req_token)
            correlation_id.reset(corr_token)
