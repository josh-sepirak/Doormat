"""Structured logging configuration using structlog."""

import logging
import sys
from typing import Any

import structlog

from doormat.config import settings


def setup_logging() -> None:
    """Configure structlog for JSON or console output."""
    # Determine if running in production
    is_prod = settings.LOG_FORMAT == "json"

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
            if is_prod
            else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
        wrapper_class=structlog.stdlib.BoundLogger,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL),
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a configured logger instance."""
    return structlog.get_logger(name)


def log_cost(
    component: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    cache_hit: bool = False,
) -> None:
    """Log LLM cost tracking."""
    if not settings.TRACK_COSTS:
        return

    logger = get_logger("doormat.cost")
    logger.info(
        "llm_call",
        component=component,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        cache_hit=cache_hit,
    )
