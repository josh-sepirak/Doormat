"""Search run lifecycle helpers: active lookup, cancellation, terminal transitions."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.models.orm import DiscoveryRun, SearchRun

ACTIVE_STATUSES = frozenset({"queued", "running", "cancel_requested"})
TERMINAL_STATUSES = frozenset({"success", "error", "cancelled"})


async def get_search_run(session: AsyncSession, search_run_id: str) -> SearchRun | None:
    return await session.get(SearchRun, search_run_id)


async def get_active_search_run(session: AsyncSession) -> SearchRun | None:
    stmt = (
        select(SearchRun)
        .where(SearchRun.status.in_(ACTIVE_STATUSES))
        .order_by(SearchRun.started_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def is_cancel_requested(session: AsyncSession, search_run_id: str) -> bool:
    row = await session.get(SearchRun, search_run_id)
    if row is None:
        return False
    return bool(row.cancel_requested or row.status == "cancel_requested")


async def mark_cancel_requested(session: AsyncSession, search_run_id: str) -> SearchRun | None:
    row = await session.get(SearchRun, search_run_id)
    if row is None:
        return None
    if row.status in TERMINAL_STATUSES:
        return row
    if row.cancel_requested or row.status == "cancel_requested":
        await session.refresh(row)
        return row
    row.cancel_requested = True
    row.status = "cancel_requested"
    await session.commit()
    await session.refresh(row)
    return row


async def apply_cancelled_terminal_state(
    session: AsyncSession, search_run: SearchRun, discovery_run: DiscoveryRun | None
) -> None:
    """Mark parent + discovery runs cancelled (caller commits)."""
    search_run.status = "cancelled"
    search_run.finished_at = datetime.now(UTC)
    if discovery_run and discovery_run.status == "running":
        discovery_run.status = "cancelled"
        discovery_run.finished_at = datetime.now(UTC)
    session.add(search_run)
    if discovery_run:
        session.add(discovery_run)


async def mark_search_run_success(session: AsyncSession, search_run: SearchRun) -> None:
    search_run.status = "success"
    search_run.finished_at = datetime.now(UTC)
    await session.commit()


async def mark_search_run_error(session: AsyncSession, search_run: SearchRun) -> None:
    search_run.status = "error"
    search_run.finished_at = datetime.now(UTC)
    await session.commit()


def terminal_suggestions_final(status: str) -> bool:
    return status in TERMINAL_STATUSES
