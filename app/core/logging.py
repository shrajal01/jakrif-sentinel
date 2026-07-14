"""
Centralized structlog configuration for the entire project.

Provides:
- configure_structlog(): call once at API or worker startup.
- get_logger(component): returns a structlog logger bound with a component name
  and enriched with context variables (request_id, correlation_id, etc.).
"""
import logging
import sys
from typing import Any, MutableMapping

import structlog
import structlog.stdlib
import structlog.contextvars
from app.core.context import get_context


def _inject_context(logger: Any, method_name: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """
    Structlog processor that injects all active context variables
    into every log entry automatically.
    """
    event_dict.update(get_context())
    return event_dict


def configure_structlog() -> None:
    """
    Configure structlog for the entire process.
    Call this once at startup (API lifespan or worker main).

    Output format: JSON lines with timestamp, level, component, context fields, event.
    """
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.processors.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            _inject_context,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib root logger so structlog output goes to stdout
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicate output
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    root_logger.addHandler(handler)


def get_logger(component: str) -> structlog.stdlib.BoundLogger:
    """
    Return a structlog logger bound with a component name.
    The logger automatically includes all active context variables
    (request_id, correlation_id, payment_id, worker_id) in every log entry.

    Usage:
        logger = get_logger("service.payment")
        logger.info("Payment created", amount=100.0)
    """
    return structlog.get_logger(component=component)
