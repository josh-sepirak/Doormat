"""Cost tracking for LLM and external API calls."""

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

    def clear(self) -> None:
        """Clear all records (for testing or batch resets)."""
        self.records.clear()


# Global instance
_tracker = CostTracker()


def get_cost_tracker() -> CostTracker:
    """Get global cost tracker instance."""
    return _tracker


@asynccontextmanager
async def track_cost(
    service: str,
    model: Optional[str] = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:  # type: ignore[misc]
    """Context manager to track costs for a service call.

    Usage:
        async with track_cost("openrouter", model="gpt-4", prompt_tokens=100):
            response = await llm_call()
    """
    start_time = datetime.now(UTC)

    try:
        yield
        status = "success"
    except Exception as e:
        status = "error"
        logger.error("cost_track_error", service=service, error=str(e))
        raise
    finally:
        latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
        total_tokens = prompt_tokens + completion_tokens
        cost_usd = estimate_cost(service, model, prompt_tokens, completion_tokens)

        record = CostRecord(
            service=service,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            status=status,
        )
        get_cost_tracker().add_record(record)


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
        }
        if model in pricing:
            rates = pricing[model]
        else:
            # Default to gpt-3.5-turbo rates for unknown models
            rates = pricing["gpt-3.5-turbo"]

        return (prompt_tokens * rates["prompt"]) + (
            completion_tokens * rates["completion"]
        )

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
