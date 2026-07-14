"""
Centralized context variables for structured logging.

Provides request-scoped context (request_id, correlation_id, payment_id)
and process-scoped context (worker_id) that are automatically included
in every structured log entry.
"""
import uuid
from contextvars import ContextVar
from typing import Optional, Dict, Any

# Request-scoped context (set per HTTP request via middleware)
request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

# Payment-scoped context (set when processing a specific payment)
payment_id: ContextVar[Optional[str]] = ContextVar("payment_id", default=None)

# Process-scoped context (set once at worker startup)
worker_id: ContextVar[Optional[str]] = ContextVar("worker_id", default=None)


def get_context() -> Dict[str, Any]:
    """
    Read all context variables and return a dict of non-None values.
    Used by structlog to enrich every log entry automatically.
    """
    ctx: Dict[str, Any] = {}
    val = request_id.get()
    if val is not None:
        ctx["request_id"] = val
    val = correlation_id.get()
    if val is not None:
        ctx["correlation_id"] = val
    val = payment_id.get()
    if val is not None:
        ctx["payment_id"] = val
    val = worker_id.get()
    if val is not None:
        ctx["worker_id"] = val
    return ctx


def generate_id() -> str:
    """Generate a short unique ID for request/correlation tracking."""
    return str(uuid.uuid4())
