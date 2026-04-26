"""Cost dashboard API endpoints.

Provides DB-backed cost aggregation for the frontend dashboard.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated, Optional

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.config import settings
from doormat.db.base import get_db
from doormat.models.orm import Cost
from doormat.schemas import (
    CostGroupedEntry,
    CostResponse,
    CostSummaryResponse,
    CostTimeseriesPoint,
)
from doormat.security.auth import require_bearer_auth

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/costs",
    tags=["costs"],
    dependencies=[Depends(require_bearer_auth)],
)
DbSession = Annotated[AsyncSession, Depends(get_db)]


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO date string into a UTC datetime, or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=UTC)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# GET /api/costs — paginated raw records
# ---------------------------------------------------------------------------


@router.get("", response_model=list[CostResponse])
async def list_costs(
    session: DbSession,
    start: Optional[str] = Query(None, description="ISO start date"),
    end: Optional[str] = Query(None, description="ISO end date"),
    component: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[Cost]:
    """Return paginated cost records from the database."""
    stmt = select(Cost)
    stmt = stmt.where(Cost.component != "model_catalog")

    start_dt = _parse_date(start)
    end_dt = _parse_date(end)
    if start_dt:
        stmt = stmt.where(Cost.timestamp >= start_dt)
    if end_dt:
        stmt = stmt.where(Cost.timestamp <= end_dt)
    if component:
        stmt = stmt.where(Cost.component == component)

    stmt = stmt.order_by(Cost.timestamp.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# GET /api/costs/summary — aggregate totals + budget info
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=CostSummaryResponse)
async def cost_summary(
    session: DbSession,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
) -> CostSummaryResponse:
    """Return aggregate cost summary with budget status."""
    stmt = select(
        func.coalesce(func.sum(Cost.cost_usd), 0.0).label("total_cost"),
        func.count(Cost.id).label("total_calls"),
        func.coalesce(func.sum(Cost.tokens_in + Cost.tokens_out), 0).label("total_tokens"),
        func.coalesce(
            func.sum(case((Cost.cache_hit.is_(True), 1), else_=0)), 0
        ).label("cache_hits"),
    )
    stmt = stmt.where(Cost.component != "model_catalog")

    start_dt = _parse_date(start)
    end_dt = _parse_date(end)
    if start_dt:
        stmt = stmt.where(Cost.timestamp >= start_dt)
    if end_dt:
        stmt = stmt.where(Cost.timestamp <= end_dt)

    result = await session.execute(stmt)
    row = result.one()

    total_cost = float(row.total_cost)
    total_calls = int(row.total_calls)
    total_tokens = int(row.total_tokens)
    cache_hits = int(row.cache_hits)

    return CostSummaryResponse(
        total_cost_usd=round(total_cost, 6),
        total_calls=total_calls,
        total_tokens=total_tokens,
        avg_cost_per_call=round(total_cost / max(total_calls, 1), 6),
        cache_hit_rate=round(cache_hits / max(total_calls, 1), 4),
        budget_limit_usd=settings.BUDGET_LIMIT_USD,
        budget_remaining_usd=round(max(settings.BUDGET_LIMIT_USD - total_cost, 0.0), 6),
        budget_exceeded=total_cost > settings.BUDGET_LIMIT_USD,
    )


# ---------------------------------------------------------------------------
# GET /api/costs/by-component
# ---------------------------------------------------------------------------


@router.get("/by-component", response_model=list[CostGroupedEntry])
async def costs_by_component(
    session: DbSession,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
) -> list[CostGroupedEntry]:
    """Return costs grouped by component (discovery, extraction, scoring)."""
    stmt = select(
        Cost.component,
        func.sum(Cost.cost_usd).label("cost_usd"),
        func.count(Cost.id).label("call_count"),
        func.sum(Cost.tokens_in + Cost.tokens_out).label("tokens_total"),
    ).where(Cost.component != "model_catalog").group_by(Cost.component)

    start_dt = _parse_date(start)
    end_dt = _parse_date(end)
    if start_dt:
        stmt = stmt.where(Cost.timestamp >= start_dt)
    if end_dt:
        stmt = stmt.where(Cost.timestamp <= end_dt)

    result = await session.execute(stmt)
    return [
        CostGroupedEntry(
            group=row.component,
            cost_usd=round(float(row.cost_usd), 6),
            call_count=int(row.call_count),
            tokens_total=int(row.tokens_total),
        )
        for row in result.all()
    ]


# ---------------------------------------------------------------------------
# GET /api/costs/by-model
# ---------------------------------------------------------------------------


@router.get("/by-model", response_model=list[CostGroupedEntry])
async def costs_by_model(
    session: DbSession,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
) -> list[CostGroupedEntry]:
    """Return costs grouped by LLM model."""
    stmt = select(
        Cost.model,
        func.sum(Cost.cost_usd).label("cost_usd"),
        func.count(Cost.id).label("call_count"),
        func.sum(Cost.tokens_in + Cost.tokens_out).label("tokens_total"),
    ).where(Cost.component != "model_catalog").group_by(Cost.model)

    start_dt = _parse_date(start)
    end_dt = _parse_date(end)
    if start_dt:
        stmt = stmt.where(Cost.timestamp >= start_dt)
    if end_dt:
        stmt = stmt.where(Cost.timestamp <= end_dt)

    result = await session.execute(stmt)
    return [
        CostGroupedEntry(
            group=row.model,
            cost_usd=round(float(row.cost_usd), 6),
            call_count=int(row.call_count),
            tokens_total=int(row.tokens_total),
        )
        for row in result.all()
    ]


# ---------------------------------------------------------------------------
# GET /api/costs/by-city
# ---------------------------------------------------------------------------


@router.get("/by-city", response_model=list[CostGroupedEntry])
async def costs_by_city(
    session: DbSession,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
) -> list[CostGroupedEntry]:
    """Return costs grouped by city."""
    stmt = (
        select(
            Cost.city,
            func.sum(Cost.cost_usd).label("cost_usd"),
            func.count(Cost.id).label("call_count"),
            func.sum(Cost.tokens_in + Cost.tokens_out).label("tokens_total"),
        )
        .where(Cost.city.is_not(None))
        .where(Cost.component != "model_catalog")
        .group_by(Cost.city)
    )

    start_dt = _parse_date(start)
    end_dt = _parse_date(end)
    if start_dt:
        stmt = stmt.where(Cost.timestamp >= start_dt)
    if end_dt:
        stmt = stmt.where(Cost.timestamp <= end_dt)

    result = await session.execute(stmt)
    return [
        CostGroupedEntry(
            group=row.city or "unknown",
            cost_usd=round(float(row.cost_usd), 6),
            call_count=int(row.call_count),
            tokens_total=int(row.tokens_total),
        )
        for row in result.all()
    ]


# ---------------------------------------------------------------------------
# GET /api/costs/timeseries — daily aggregates for charting
# ---------------------------------------------------------------------------


@router.get("/timeseries", response_model=list[CostTimeseriesPoint])
async def costs_timeseries(
    session: DbSession,
    days: int = Query(30, ge=1, le=365),
) -> list[CostTimeseriesPoint]:
    """Return daily cost aggregates for the last N days."""
    cutoff = datetime.now(UTC) - timedelta(days=days)

    stmt = (
        select(Cost)
        .where(Cost.timestamp >= cutoff)
        .where(Cost.component != "model_catalog")
        .order_by(Cost.timestamp)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    # Aggregate by day in Python (SQLite date functions are limited)
    daily: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"cost_usd": 0.0, "call_count": 0, "tokens_total": 0}
    )
    for row in rows:
        day_key = row.timestamp.strftime("%Y-%m-%d")
        daily[day_key]["cost_usd"] += row.cost_usd
        daily[day_key]["call_count"] += 1
        daily[day_key]["tokens_total"] += row.tokens_in + row.tokens_out

    # Fill in missing days with zeros
    points: list[CostTimeseriesPoint] = []
    current = cutoff.date()
    today = datetime.now(UTC).date()
    while current <= today:
        key = current.isoformat()
        entry = daily.get(key, {"cost_usd": 0.0, "call_count": 0, "tokens_total": 0})
        points.append(
            CostTimeseriesPoint(
                date=key,
                cost_usd=round(float(entry["cost_usd"]), 6),
                call_count=int(entry["call_count"]),
                tokens_total=int(entry["tokens_total"]),
            )
        )
        current += timedelta(days=1)

    return points
