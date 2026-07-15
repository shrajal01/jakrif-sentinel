"""
FastAPI middleware for structured logging context.

Sets request_id and correlation_id context variables on every incoming request.
Logs request start and completion with method, path, status code, and duration.
"""
import asyncio
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.context import request_id, correlation_id, generate_id
from app.core.logging import get_logger
from app.database.session import AsyncSessionLocal
from app.models.request_log import RequestLog
from app.services.service_registry import get_or_create_service_id

logger = get_logger("api.middleware")

# Logical service name this API process is registered under for RequestLog FKs.
API_SERVICE_NAME = "jakrif-api"


async def _persist_request_log(req_id: str, method: str, path: str, status_code: int, latency_ms: float, response_size: str | None) -> None:
    """
    Fire-and-forget persistence of a single request log row, used to power the
    dashboard's "Recent System Logs" panel. Runs in its own DB session so it
    never shares/blocks the request's own session, and never raises back into
    the request lifecycle - a logging failure must not fail the request.
    """
    try:
        async with AsyncSessionLocal() as db:
            service_id = await get_or_create_service_id(db, name=API_SERVICE_NAME, base_url="internal://api")
            db.add(RequestLog(
                request_id=req_id,
                service_id=service_id,
                method=method,
                path=path,
                status_code=status_code,
                latency_ms=int(latency_ms),
                response_size=int(response_size) if response_size and response_size.isdigit() else None,
            ))
            await db.commit()
    except Exception as e:
        logger.warning("Failed to persist request log", error=str(e), request_id=req_id)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Reads X-Request-ID header (or generates one).
    2. Reads X-Correlation-ID header (or generates one).
    3. Sets contextvars so all downstream logs include these IDs.
    4. Logs request start and completion with timing.
    5. Persists a RequestLog row (async, non-blocking) for dashboard observability.
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

            # Persist the request log in the background so dashboard queries
            # never add latency to the actual request/response cycle.
            asyncio.create_task(_persist_request_log(
                req_id,
                request.method,
                str(request.url.path),
                response.status_code,
                duration_ms,
                response.headers.get("content-length"),
            ))

            return response
        finally:
            # Reset context variables
            request_id.reset(req_token)
            correlation_id.reset(corr_token)