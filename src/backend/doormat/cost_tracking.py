"""Cost tracking for LLM and external API calls."""

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class CostRecord:
    """Single cost record for an LLM or API call."""

    service: str  # "openrouter", "apify", etc.
    model: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: str = "success"  # success, error, timeout
    component: str = "unknown"  # discovery, extraction, scoring
    city: Optional[str] = None


class CostTracker:
    """Track and aggregate costs across service calls."""

    def __init__(self) -> None:
        """Initialize cost tracker."""
        self.records: list[CostRecord] = []

    def add_record(self, record: CostRecord) -> None:
        """Add a cost record."""
        self.records.append(record)
        logger.info(
            "cost_tracked",
            service=record.service,
            model=record.model,
            tokens=record.total_tokens,
            cost_usd=record.cost_usd,
            latency_ms=record.latency_ms,
            status=record.status,
            component=record.component,
        )

        # Budget alert
        from doormat.config import settings

        total = self.total_cost()
        if total > settings.BUDGET_LIMIT_USD:
            logger.warning(
                "budget_exceeded",
                total_cost_usd=total,
                budget_limit_usd=settings.BUDGET_LIMIT_USD,
            )

    def total_cost(self) -> float:
        """Get total cost across all records."""
        return sum(r.cost_usd for r in self.records)

    def total_tokens(self) -> int:
        """Get total tokens across all records."""
        return sum(r.total_tokens for r in self.records)

    def records_by_service(self, service: str) -> list[CostRecord]:
        """Get all records for a specific service."""
        return [r for r in self.records if r.service == service]

    def is_budget_exceeded(self) -> bool:
        """Check if total cost exceeds the configured budget limit."""
        from doormat.config import settings

        return self.total_cost() > settings.BUDGET_LIMIT_USD

    def clear(self) -> None:
        """Clear all records (for testing or batch resets)."""
        self.records.clear()


@dataclass
class CostScope:
    """Mutable accounting details updated by a tracked operation."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float | None = None
    cache_hit: bool = False
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


# Global instance
_tracker = CostTracker()


def get_cost_tracker() -> CostTracker:
    """Get global cost tracker instance."""
    return _tracker


async def persist_cost_record(record: CostRecord, cache_hit: bool = False) -> None:
    """Persist a cost record to the database.

    Creates a new DB session for each write so callers don't have to thread
    a session through the cost-tracking context manager.
    """
    try:
        from doormat.db.base import AsyncSessionLocal
        from doormat.models.orm import Cost

        async with AsyncSessionLocal() as session:
            cost = Cost(
                id=str(uuid.uuid4()),
                component=record.component,
                model=record.model or "unknown",
                tokens_in=record.prompt_tokens,
                tokens_out=record.completion_tokens,
                cost_usd=record.cost_usd,
                cache_hit=cache_hit,
                timestamp=record.timestamp,
                city=record.city,
            )
            session.add(cost)
            await session.commit()
    except Exception as exc:
        # Never let cost persistence crash the main flow
        logger.warning("cost_persist_failed", error=str(exc))


@asynccontextmanager
async def track_cost(
    service: str,
    model: Optional[str] = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    component: str = "unknown",
    city: Optional[str] = None,
    cache_hit: bool = False,
) -> AsyncGenerator[CostScope, None]:
    """Context manager to track costs for a service call.

    Usage:
        async with track_cost("openrouter", model="gpt-4", prompt_tokens=100):
            response = await llm_call()
    """
    start_time = datetime.now(UTC)
    scope = CostScope(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)

    try:
        yield scope
        status = "success"
    except Exception as e:
        status = "error"
        logger.error("cost_track_error", service=service, error=str(e))
        raise
    finally:
        latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
        total_tokens = scope.prompt_tokens + scope.completion_tokens
        cost_usd = (
            scope.cost_usd
            if scope.cost_usd is not None
            else estimate_cost(service, model, scope.prompt_tokens, scope.completion_tokens)
        )

        record = CostRecord(
            service=service,
            model=model,
            prompt_tokens=scope.prompt_tokens,
            completion_tokens=scope.completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            status=status,
            component=component,
            city=city,
        )
        get_cost_tracker().add_record(record)

        # Also persist to DB
        from doormat.config import settings

        if settings.TRACK_COSTS:
            await persist_cost_record(record, cache_hit=scope.cache_hit)


def estimate_cost(
    service: str, model: Optional[str], prompt_tokens: int, completion_tokens: int
) -> float:
    """Estimate cost in USD for a service call.

    OpenRouter pricing varies by model. This is a simple estimator.
    Real implementation would use actual pricing from the API.
    """
    if service == "openrouter":
        # Simplified pricing (actual prices from OpenRouter API)
        pricing = {
            "gpt-4-turbo": {"prompt": 0.01 / 1000, "completion": 0.03 / 1000},
            "gpt-4": {"prompt": 0.03 / 1000, "completion": 0.06 / 1000},
            "gpt-3.5-turbo": {"prompt": 0.0005 / 1000, "completion": 0.0015 / 1000},
            "google/gemma-4-31b-it:free": {"prompt": 0.0, "completion": 0.0},
            "anthropic/claude-3.5-sonnet": {"prompt": 0.003 / 1000, "completion": 0.015 / 1000},
            "anthropic/claude-3-haiku": {"prompt": 0.00025 / 1000, "completion": 0.00125 / 1000},
        }
        if model in pricing:
            rates = pricing[model]
        else:
            # Default to haiku rates for unknown models to be conservative
            rates = pricing["anthropic/claude-3-haiku"]

        return (prompt_tokens * rates["prompt"]) + (completion_tokens * rates["completion"])

    elif service == "apify":
        # Apify charges per actor run, roughly $0.25-$1.00 per run
        return 0.50  # Average estimate

    return 0.0


def get_cost_summary() -> dict[str, object]:
    """Get summary of all tracked costs."""
    tracker = get_cost_tracker()
    return {
        "total_cost_usd": tracker.total_cost(),
        "total_tokens": tracker.total_tokens(),
        "record_count": len(tracker.records),
        "by_service": {
            service: {
                "cost_usd": sum(r.cost_usd for r in records),
                "tokens": sum(r.total_tokens for r in records),
                "count": len(records),
            }
            for service, records in {
                s: tracker.records_by_service(s) for s in ["openrouter", "apify"]
            }.items()
            if records
        },
    }
