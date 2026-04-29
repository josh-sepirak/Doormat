"""Search run lifecycle API (durable parent runs wrapping discovery)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.api.routers.discovery import (
    _run_discovery_background,
    enforce_discovery_rate_limit,
    require_discovery_auth,
)
from doormat.db.base import get_db
from doormat.models.orm import DiscoveryRun, Preference, RunListingResult, SearchRun, SearchRunEvent
from doormat.runs import events as run_events
from doormat.runs import filters as run_filters
from doormat.runs import state as run_state
from doormat.runs import suggestions as run_suggestions
from doormat.schemas import (
    RunListingResultOut,
    SearchRunActiveEnvelope,
    SearchRunCreate,
    SearchRunEventOut,
    SearchRunFiltersPatch,
    SearchRunResponse,
    SearchRunSuggestion,
)

DBSession = Annotated[AsyncSession, Depends(get_db)]

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/search-runs", tags=["search-runs"])


def _validate_city(city: str) -> str:
    cleaned = city.strip()
    if not cleaned or len(cleaned) < 2 or len(cleaned) > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="city must be 2-100 chars",
        )
    return cleaned


async def _build_run_response(session: AsyncSession, run: SearchRun) -> SearchRunResponse:
    stmt = select(RunListingResult).where(
        RunListingResult.run_id == run.id,
        RunListingResult.revision == run.active_revision,
    )
    rows = list((await session.execute(stmt)).scalars().all())
    raw_suggestions = run_suggestions.aggregate_suggestions_from_results(rows)
    suggestions = [SearchRunSuggestion.model_validate(s) for s in raw_suggestions]
    run_filters_snapshot: dict[str, Any] = {}
    if run.filters_json:
        try:
            parsed_filters = json.loads(run.filters_json)
        except json.JSONDecodeError:
            parsed_filters = {}
        if isinstance(parsed_filters, dict):
            run_filters_snapshot = parsed_filters
    filter_summary = {
        "revision": run.active_revision,
        "great_matches": run.great_matches,
        "worth_a_look": run.worth_a_look,
        "near_misses": run.near_misses,
        "filtered_out": run.filtered_out,
        "managers_validated": run.managers_validated,
        "listings_seen": run.listings_seen,
        "extraction_attempts": run.extraction_attempts,
        "sources_checked": run.sources_checked,
        "sources_enabled": run_filters_snapshot.get("sources_enabled", []),
    }
    return SearchRunResponse(
        id=run.id,
        discovery_run_id=run.discovery_run_id,
        city=run.city,
        preference_id=run.preference_id,
        status=run.status,
        current_stage=run.current_stage,
        cancel_requested=run.cancel_requested,
        sources_checked=run.sources_checked,
        managers_validated=run.managers_validated,
        listings_seen=run.listings_seen,
        extraction_attempts=run.extraction_attempts,
        great_matches=run.great_matches,
        worth_a_look=run.worth_a_look,
        near_misses=run.near_misses,
        filtered_out=run.filtered_out,
        cost_usd_so_far=run.cost_usd_so_far,
        active_revision=run.active_revision,
        started_at=run.started_at,
        finished_at=run.finished_at,
        filter_summary=filter_summary,
        suggestions=suggestions,
        suggestions_early_signal=not run_state.terminal_suggestions_final(run.status),
    )


@router.post("", response_model=SearchRunResponse)
async def create_search_run(
    body: SearchRunCreate,
    background_tasks: BackgroundTasks,
    session: DBSession,
    _auth: Annotated[None, Depends(require_discovery_auth)],
    _rate_limit: Annotated[None, Depends(enforce_discovery_rate_limit)],
) -> SearchRunResponse:
    """Create a parent `SearchRun` and start wrapped discovery in the background."""
    cleaned_city = _validate_city(body.city)
    discovery_id = str(uuid.uuid4())
    search_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    discovery = DiscoveryRun(
        id=discovery_id,
        city=cleaned_city,
        preference_id=body.preference_id,
        status="running",
        started_at=now,
    )
    pref_row = await session.get(Preference, body.preference_id) if body.preference_id else None
    search = SearchRun(
        id=search_id,
        discovery_run_id=discovery_id,
        city=cleaned_city,
        preference_id=body.preference_id,
        status="running",
        current_stage="discovery",
        cancel_requested=False,
        started_at=now,
        filters_json=json.dumps(run_filters.build_run_filter_snapshot(pref_row)),
    )
    session.add(discovery)
    session.add(search)
    await session.commit()

    await run_events.append_search_run_event_standalone(
        run_id=search_id,
        event_type="run_started",
        message=f"Search run started for {cleaned_city}",
        stage="discovery",
        payload={"city": cleaned_city, "preference_id": body.preference_id},
    )

    background_tasks.add_task(
        _run_discovery_background,
        discovery_id,
        cleaned_city,
        body.preference_id,
        search_id,
    )

    refreshed = await session.get(SearchRun, search_id)
    assert refreshed is not None
    return await _build_run_response(session, refreshed)


@router.get("/active", response_model=SearchRunActiveEnvelope)
async def get_active_search_run(session: DBSession) -> SearchRunActiveEnvelope:
    active = await run_state.get_active_search_run(session)
    if active is None:
        return SearchRunActiveEnvelope(active=False, run=None)
    return SearchRunActiveEnvelope(active=True, run=await _build_run_response(session, active))


@router.get("/{run_id}", response_model=SearchRunResponse)
async def get_search_run(run_id: str, session: DBSession) -> SearchRunResponse:
    run = await session.get(SearchRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return await _build_run_response(session, run)


@router.get("/{run_id}/events", response_model=list[SearchRunEventOut])
async def list_search_run_events(
    run_id: str,
    session: DBSession,
    after_sequence: int = -1,
    limit: int = 100,
    visibility: Optional[str] = None,
) -> list[SearchRunEventOut]:
    if await session.get(SearchRun, run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")
    stmt = select(SearchRunEvent).where(SearchRunEvent.run_id == run_id)
    if after_sequence >= 0:
        stmt = stmt.where(SearchRunEvent.sequence > after_sequence)
    if visibility in {"user", "developer"}:
        stmt = stmt.where(SearchRunEvent.visibility == visibility)
    stmt = stmt.order_by(SearchRunEvent.sequence).limit(min(max(limit, 1), 500))
    rows = list((await session.execute(stmt)).scalars().all())
    return [SearchRunEventOut.model_validate(r) for r in rows]


@router.post("/{run_id}/stop", response_model=SearchRunResponse)
async def stop_search_run(
    run_id: str,
    session: DBSession,
    _auth: Annotated[None, Depends(require_discovery_auth)],
) -> SearchRunResponse:
    existing = await session.get(SearchRun, run_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="run not found")
    if existing.status in run_state.TERMINAL_STATUSES:
        return await _build_run_response(session, existing)
    if existing.cancel_requested or existing.status == "cancel_requested":
        return await _build_run_response(session, existing)

    run = await run_state.mark_cancel_requested(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    await run_events.append_search_run_event_standalone(
        run_id=run_id,
        event_type="run_waiting_to_stop",
        message="Stopping after the current unit finishes…",
        stage=run.current_stage,
        payload={},
    )
    await run_events.append_search_run_event_standalone(
        run_id=run_id,
        event_type="cancel_requested",
        message="Cancellation requested",
        stage=run.current_stage,
        payload={},
    )
    refreshed = await session.get(SearchRun, run_id)
    assert refreshed is not None
    return await _build_run_response(session, refreshed)


@router.get("/{run_id}/results", response_model=list[RunListingResultOut])
async def list_search_run_results(
    run_id: str,
    session: DBSession,
    category: Optional[str] = None,
    revision: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[RunListingResultOut]:
    run = await session.get(SearchRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    rev = revision if revision is not None else run.active_revision
    stmt = select(RunListingResult).where(
        RunListingResult.run_id == run_id,
        RunListingResult.revision == rev,
    )
    if category:
        stmt = stmt.where(RunListingResult.category == category)
    stmt = stmt.order_by(RunListingResult.id).offset(max(offset, 0)).limit(min(max(limit, 1), 200))
    rows = list((await session.execute(stmt)).scalars().all())
    return [RunListingResultOut.model_validate(r) for r in rows]


@router.patch("/{run_id}/filters", response_model=SearchRunResponse)
async def patch_search_run_filters(
    run_id: str,
    body: SearchRunFiltersPatch,
    session: DBSession,
    _auth: Annotated[None, Depends(require_discovery_auth)],
) -> SearchRunResponse:
    run = await session.get(SearchRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    if run.status in run_state.TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="run is not active")

    current: dict[str, Any] = {}
    if run.filters_json:
        try:
            current = json.loads(run.filters_json)
        except json.JSONDecodeError:
            current = {}
    patch = body.model_dump(exclude_unset=True)
    patch.pop("next_run_city", None)
    patch.pop("next_run_change_openrouter_key", None)
    current.update({k: v for k, v in patch.items() if v is not None})
    run.filters_json = json.dumps(current)
    run.active_revision += 1
    session.add(run)
    await session.commit()
    await session.refresh(run)
    emitter = run_events.SearchRunEventEmitter(session, run.id)
    await emitter.emit(
        "stage_progress",
        f"Filters updated — revision {run.active_revision}",
        payload={"revision": run.active_revision, "filters": current},
    )
    pref_row = await session.get(Preference, run.preference_id) if run.preference_id else None
    await run_filters.classify_city_listings_for_run(
        session, run=run, city=run.city, preference=pref_row, emitter=emitter
    )
    await session.commit()
    refreshed = await session.get(SearchRun, run_id)
    assert refreshed is not None
    return await _build_run_response(session, refreshed)
