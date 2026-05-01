"""Search run events: constants, sanitization, persistence, and structured emitters."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.db.base import AsyncSessionLocal
from doormat.models.orm import SearchRun, SearchRunEvent

MAX_PAYLOAD_CHARS = 8_000
_SECRET_KEY_SUBSTRINGS = (
    "api_key",
    "token",
    "secret",
    "password",
    "bearer",
    "authorization",
    "openrouter",
    "apify",
)


def default_event_type_from_discovery(level: str, message: str) -> str:
    m = message.lower()
    if level == "error":
        return "error"
    if level == "warning":
        return "warning"
    if level == "success" and "complete" in m:
        return "stage_completed"
    if "classifying" in m or "candidate" in m or "search" in m:
        return "stage_progress"
    return "stage_progress"


def sanitize_diagnostic_payload(data: Any) -> Any:
    """Remove secrets and bound large strings for safe persistence."""
    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for k, v in data.items():
            lk = str(k).lower()
            if any(s in lk for s in _SECRET_KEY_SUBSTRINGS):
                out[k] = "[redacted]"
                continue
            if lk == "html" or lk.endswith("_raw"):
                out[k] = _truncate(str(v), 500)
                continue
            out[k] = sanitize_diagnostic_payload(v)
        return out
    if isinstance(data, list):
        return [sanitize_diagnostic_payload(x) for x in data[:200]]
    if isinstance(data, str):
        return _truncate(data, 2000)
    return data


def _truncate(s: str, max_len: int) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 15] + "...[truncated]"


async def next_event_sequence(session: AsyncSession, run_id: str) -> int:
    stmt = select(func.coalesce(func.max(SearchRunEvent.sequence), -1)).where(
        SearchRunEvent.run_id == run_id
    )
    current = (await session.execute(stmt)).scalar_one()
    return int(current) + 1


async def append_search_run_event(
    session: AsyncSession,
    *,
    run_id: str,
    event_type: str,
    message: str,
    stage: str | None = None,
    payload: dict[str, Any] | None = None,
    visibility: str = "user",
) -> SearchRunEvent:
    seq = await next_event_sequence(session, run_id)
    safe_payload = sanitize_diagnostic_payload(payload) if payload else None
    payload_str = json.dumps(safe_payload) if safe_payload is not None else None
    if payload_str and len(payload_str) > MAX_PAYLOAD_CHARS:
        payload_str = json.dumps(
            {"truncated": True, "preview": payload_str[: MAX_PAYLOAD_CHARS - 80]}
        )
    evt = SearchRunEvent(
        id=str(uuid.uuid4()),
        run_id=run_id,
        sequence=seq,
        event_type=event_type,
        stage=stage,
        message=message,
        payload_json=payload_str,
        visibility=visibility,
        timestamp=datetime.now(UTC),
    )
    session.add(evt)
    return evt


async def append_search_run_event_standalone(
    *,
    run_id: str,
    event_type: str,
    message: str,
    stage: str | None = None,
    payload: dict[str, Any] | None = None,
    visibility: str = "user",
) -> None:
    async with AsyncSessionLocal() as session:
        await append_search_run_event(
            session,
            run_id=run_id,
            event_type=event_type,
            message=message,
            stage=stage,
            payload=payload,
            visibility=visibility,
        )
        await session.commit()


async def mirror_discovery_log_to_search_run(
    *,
    search_run_id: str,
    message: str,
    level: str,
    component: str,
    details: dict[str, Any] | None,
) -> None:
    """Mirror a discovery log line into `SearchRunEvent` rows (standalone session)."""
    merged = dict(details or {})
    event_type = str(merged.pop("event_type", default_event_type_from_discovery(level, message)))
    visibility = "developer" if level == "debug" else "user"
    payload = sanitize_diagnostic_payload(
        {
            **merged,
            "discovery_level": level,
            "discovery_component": component,
        }
    )
    await append_search_run_event_standalone(
        run_id=search_run_id,
        event_type=event_type,
        message=message,
        stage=merged.get("stage") if isinstance(merged.get("stage"), str) else None,
        payload=payload if isinstance(payload, dict) else {"value": payload},
        visibility=visibility,
    )


class SearchRunEventEmitter:
    """Structured emitters for user-visible and developer diagnostics."""

    def __init__(self, session: AsyncSession, run_id: str) -> None:
        self._session = session
        self._run_id = run_id

    async def emit(
        self,
        event_type: str,
        message: str,
        *,
        stage: str | None = None,
        payload: dict[str, Any] | None = None,
        visibility: str = "user",
    ) -> SearchRunEvent:
        return await append_search_run_event(
            self._session,
            run_id=self._run_id,
            event_type=event_type,
            message=message,
            stage=stage,
            payload=payload,
            visibility=visibility,
        )

    async def stage_started(self, stage: str, message: str) -> SearchRunEvent:
        return await self.emit("stage_started", message, stage=stage, payload={"stage": stage})

    async def stage_completed(self, stage: str, message: str) -> SearchRunEvent:
        return await self.emit("stage_completed", message, stage=stage, payload={"stage": stage})

    async def search_query_started(self, query: str) -> SearchRunEvent:
        return await self.emit(
            "search_query_started",
            "Starting a new search query",
            stage="discovery",
            payload={"query": _truncate(query, 500)},
        )

    async def search_query_completed(self, summary: str) -> SearchRunEvent:
        return await self.emit(
            "search_query_completed",
            summary,
            stage="discovery",
            payload={"summary": _truncate(summary, 1000)},
        )

    async def cost_updated(self, total_usd: float) -> SearchRunEvent:
        return await self.emit(
            "cost_updated",
            f"Cost so far: ${total_usd:.4f}",
            payload={"cost_usd": total_usd},
            visibility="user",
        )

    async def warning(self, message: str, payload: dict[str, Any] | None = None) -> SearchRunEvent:
        return await self.emit("warning", message, payload=payload)

    async def error(self, message: str, payload: dict[str, Any] | None = None) -> SearchRunEvent:
        return await self.emit("error", message, payload=payload, visibility="user")

    async def developer_diag(
        self,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> SearchRunEvent:
        safe = sanitize_diagnostic_payload(payload or {})
        return await self.emit(
            "stage_progress",
            message,
            payload=safe if isinstance(safe, dict) else {"data": safe},
            visibility="developer",
        )

    # Discovery events (candidates, managers, validation)
    async def candidate_found(self, query: str, url: str, manager_name: str) -> SearchRunEvent:
        return await self.emit(
            "candidate_found",
            f"Found candidate: {manager_name}",
            stage="discovery",
            payload={
                "query": _truncate(query, 500),
                "url": _truncate(url, 500),
                "manager": manager_name,
            },
        )

    async def candidate_rejected(
        self,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> SearchRunEvent:
        return await self.emit(
            "candidate_rejected",
            f"Candidate rejected: {reason}",
            stage="discovery",
            payload={"reason": reason, **(details or {})},
        )

    async def manager_validated(
        self,
        manager_name: str,
        url: str,
        listings_found: int,
    ) -> SearchRunEvent:
        return await self.emit(
            "manager_validated",
            f"Validated {manager_name}: found {listings_found} listings",
            stage="discovery",
            payload={
                "manager": manager_name,
                "url": _truncate(url, 500),
                "listings_found": listings_found,
            },
        )

    # Scraping events (managers, listings)
    async def scrape_manager_started(self, manager_name: str) -> SearchRunEvent:
        return await self.emit(
            "scrape_manager_started",
            f"Starting to scrape {manager_name}",
            stage="scraping",
            payload={"manager": manager_name},
        )

    async def scrape_listings_completed(
        self,
        manager_name: str,
        extracted: int,
        seen: int,
        failures: int = 0,
    ) -> SearchRunEvent:
        return await self.emit(
            "scrape_listings_completed",
            f"Scraped {manager_name}: {extracted} extracted, {seen} seen",
            stage="scraping",
            payload={
                "manager": manager_name,
                "extracted": extracted,
                "seen": seen,
                "failures": failures,
            },
        )

    # Extraction and scoring events
    async def extraction_started(self, listing_count: int) -> SearchRunEvent:
        return await self.emit(
            "extraction_started",
            f"Starting extraction for {listing_count} listings",
            stage="extraction",
            payload={"listing_count": listing_count},
        )

    async def scoring_started(self, listing_count: int) -> SearchRunEvent:
        return await self.emit(
            "scoring_started",
            f"Starting to score {listing_count} listings",
            stage="scoring",
            payload={"listing_count": listing_count},
        )

    async def scoring_completed(
        self,
        great_matches: int,
        worth_a_look: int,
        near_misses: int,
        filtered_out: int,
    ) -> SearchRunEvent:
        return await self.emit(
            "scoring_completed",
            f"Scoring complete: {great_matches} great, {worth_a_look} good, {near_misses} near misses, {filtered_out} filtered",
            stage="scoring",
            payload={
                "great_matches": great_matches,
                "worth_a_look": worth_a_look,
                "near_misses": near_misses,
                "filtered_out": filtered_out,
            },
        )

    # Cancellation and status
    async def cancellation_requested(self) -> SearchRunEvent:
        return await self.emit(
            "cancellation_requested",
            "User requested cancellation",
            payload={"reason": "user_stop"},
            visibility="user",
        )

    async def run_completed(self, summary: str) -> SearchRunEvent:
        return await self.emit(
            "run_completed",
            summary,
            payload={"summary": _truncate(summary, 1000)},
            visibility="user",
        )


def sync_run_cost_from_tracker(session: AsyncSession, run: SearchRun) -> None:
    """Best-effort snapshot of aggregate tracker cost onto the parent run."""
    from doormat.cost_tracking import get_cost_summary

    summary = get_cost_summary()
    raw = cast(Any, summary.get("total_cost_usd", 0.0))
    total = float(raw or 0.0)
    run.cost_usd_so_far = total
    session.add(run)
