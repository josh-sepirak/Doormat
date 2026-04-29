"""Discovery API router."""

from __future__ import annotations

import json
import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.config import settings
from doormat.db.base import AsyncSessionLocal, get_db
from doormat.discovery.agent import DiscoveryAgent
from doormat.discovery.classifier import PropertyManagerClassifier
from doormat.discovery.models import DiscoveryResult
from doormat.discovery.search import DiscoverySearch
from doormat.llm.client import get_llm_client
from doormat.models.orm import DiscoveryRun, DiscoveryRunLog, Preference, PropertyManager, SearchRun
from doormat.runs import events as run_events
from doormat.runs import state as run_state
from doormat.runs.errors import CooperativeCancel
from doormat.schemas import DiscoveryRunResponse
from doormat.security.auth import require_bearer_auth
from doormat.security.secrets import decrypt_secret

DBSession = Annotated[AsyncSession, Depends(get_db)]

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/discovery", tags=["discovery"])

_RATE_WINDOW_SECONDS = 60.0
_discovery_request_times: dict[str, deque[float]] = {}


class TriggerRequest(BaseModel):
    city: str
    preference_id: Optional[str] = None


class ManagerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    city: str
    name: str
    website: str | None
    listing_page_url: str | None
    validated: bool


class CityStatus(BaseModel):
    city: str
    managers_total: int
    managers_validated: int
    has_been_discovered: bool


class ScrapeRequest(BaseModel):
    preference_id: Optional[str] = None
    max_managers: int = 5
    search_run_id: Optional[str] = None


class ScrapeResult(BaseModel):
    city: str
    managers_scraped: int
    listings_extracted: int
    listings_scored: int


class RunLogger:
    """Writes log lines to DiscoveryRunLog using independent committed sessions.

    Each entry is committed immediately so polling requests see live progress.
    """

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._seq = 0

    async def log(
        self,
        message: str,
        level: str = "info",
        component: str = "discovery",
        details: dict[str, Any] | None = None,
    ) -> None:
        async with AsyncSessionLocal() as session:
            entry = DiscoveryRunLog(
                id=str(uuid.uuid4()),
                run_id=self._run_id,
                sequence=self._seq,
                level=level,
                component=component,
                message=message,
                details=json.dumps(details) if details else None,
            )
            session.add(entry)
            await session.commit()
        self._seq += 1

    async def info(self, message: str, component: str = "discovery", **kw: Any) -> None:
        await self.log(message, "info", component, kw or None)

    async def success(self, message: str, component: str = "discovery", **kw: Any) -> None:
        await self.log(message, "success", component, kw or None)

    async def error(self, message: str, component: str = "discovery", **kw: Any) -> None:
        await self.log(message, "error", component, kw or None)

    async def debug(self, message: str, component: str = "discovery", **kw: Any) -> None:
        await self.log(message, "debug", component, kw or None)

    async def warning(self, message: str, component: str = "discovery", **kw: Any) -> None:
        await self.log(message, "warning", component, kw or None)


class BridgedSearchRunLogger(RunLogger):
    """Mirrors discovery logs into `SearchRunEvent` rows for the parent run."""

    def __init__(self, discovery_run_id: str, search_run_id: str) -> None:
        super().__init__(discovery_run_id)
        self._search_run_id = search_run_id

    async def log(
        self,
        message: str,
        level: str = "info",
        component: str = "discovery",
        details: dict[str, Any] | None = None,
    ) -> None:
        await super().log(message, level, component, details)
        await run_events.mirror_discovery_log_to_search_run(
            search_run_id=self._search_run_id,
            message=message,
            level=level,
            component=component,
            details=details,
        )


require_discovery_auth = require_bearer_auth


async def enforce_discovery_rate_limit(request: Request) -> None:
    limit = settings.DISCOVERY_RATE_LIMIT_PER_MINUTE
    if limit <= 0:
        return
    now = time.monotonic()
    client_host = request.client.host if request.client else "unknown"
    request_times = _discovery_request_times.setdefault(client_host, deque())
    while request_times and now - request_times[0] >= _RATE_WINDOW_SECONDS:
        request_times.popleft()
    if len(request_times) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many discovery requests",
        )
    request_times.append(now)


def reset_discovery_rate_limits() -> None:
    _discovery_request_times.clear()


def _build_run_response(run: DiscoveryRun, logs: list[DiscoveryRunLog]) -> DiscoveryRunResponse:
    """Build response dict without triggering SQLAlchemy lazy loads."""
    return DiscoveryRunResponse.model_validate(
        {
            "id": run.id,
            "city": run.city,
            "preference_id": run.preference_id,
            "status": run.status,
            "managers_found": run.managers_found,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "logs": [
                {
                    "id": log.id,
                    "sequence": log.sequence,
                    "level": log.level,
                    "component": log.component,
                    "message": log.message,
                    "details": log.details,
                    "timestamp": log.timestamp,
                }
                for log in logs
            ],
        }
    )


def _validate_city(city: str) -> str:
    cleaned = city.strip()
    if not cleaned or len(cleaned) < 2 or len(cleaned) > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="city must be 2-100 chars",
        )
    return cleaned


async def _preferred_openrouter_settings(
    session: AsyncSession, preference_id: str | None
) -> tuple[str | None, str | None]:
    """Return the saved fast model and decrypted key for a discovery run."""
    if not preference_id:
        return None, None
    pref = await session.get(Preference, preference_id)
    if not pref:
        return None, None
    return pref.fast_model, decrypt_secret(pref.openrouter_api_key)


async def _run_discovery_agent(
    session: AsyncSession,
    city: str,
    preference_id: str | None,
    fast_model: str | None,
    openrouter_api_key: str | None,
    run_logger: RunLogger,
    cancel_check: Callable[[], Awaitable[bool]] | None = None,
) -> DiscoveryResult:
    """Initialize model-aware discovery dependencies and execute the agent."""
    llm = get_llm_client(api_key=openrouter_api_key)
    search = DiscoverySearch(llm=llm, model=fast_model)
    classifier = PropertyManagerClassifier(llm=llm, model=fast_model)
    agent = DiscoveryAgent(session=session, search=search, classifier=classifier)
    model_label = fast_model or "default"
    await run_logger.info(f"Discovery agent initialized (model: {model_label})", component="agent")
    return await agent.discover_city(
        city,
        preference_id=preference_id,
        run_logger=run_logger,
        cancel_check=cancel_check,
    )


async def _record_discovery_success(
    run: DiscoveryRun,
    result: DiscoveryResult,
    run_logger: RunLogger,
) -> None:
    """Persist success status and user-facing run logs."""
    managers_found = result.validated_count
    if managers_found == 0 and result.candidates_found == 0:
        await run_logger.warning(
            "No candidates found — LLM search returned empty. "
            "Model may be rate-limited or not support structured output. "
            "Try switching to a paid model in Preferences.",
            component="discovery",
        )
    await run_logger.success(
        f"Discovery complete — found {managers_found} property managers",
        component="discovery",
        managers_found=managers_found,
    )
    run.status = "success"
    run.managers_found = managers_found
    run.finished_at = datetime.now(timezone.utc)


# ─── Main trigger (what the frontend calls) ──────────────────────────────────


async def _run_discovery_background(  # noqa: C901
    run_id: str,
    city: str,
    preference_id: str | None,
    search_run_id: str | None = None,
) -> None:
    """Background task: runs discovery pipeline, updates run record, commits logs live."""
    run_logger: RunLogger = (
        BridgedSearchRunLogger(run_id, search_run_id) if search_run_id else RunLogger(run_id=run_id)
    )
    await run_logger.info(f"Starting discovery for {city}")

    async def cancel_check() -> bool:
        if not search_run_id:
            return False
        async with AsyncSessionLocal() as s2:
            sr = await s2.get(SearchRun, search_run_id)
            if sr is None:
                return False
            return bool(sr.cancel_requested or sr.status == "cancel_requested")

    async with AsyncSessionLocal() as session:
        run = await session.get(DiscoveryRun, run_id)
        if run is None:
            logger.error("background_run_not_found", run_id=run_id)
            return
        search_outcome: str | None = None
        try:
            fast_model, openrouter_api_key = await _preferred_openrouter_settings(
                session, preference_id
            )
            result = await _run_discovery_agent(
                session,
                city,
                preference_id,
                fast_model,
                openrouter_api_key,
                run_logger,
                cancel_check=cancel_check,
            )
            await _record_discovery_success(run, result, run_logger)
            if search_run_id:
                sr = await session.get(SearchRun, search_run_id)
                if sr:
                    sr.managers_validated = int(result.validated_count)
                    # keep status=running; pipeline.run_scraping_stage will finalize it
                    run_events.sync_run_cost_from_tracker(session, sr)
                    session.add(sr)
            search_outcome = "success"
        except CooperativeCancel:
            await run_logger.warning(
                "Discovery stopped after cancellation request", component="discovery"
            )
            if search_run_id:
                sr = await session.get(SearchRun, search_run_id)
                if sr:
                    await run_state.apply_cancelled_terminal_state(session, sr, run)
                else:
                    run.status = "cancelled"
                    run.finished_at = datetime.now(timezone.utc)
            else:
                run.status = "cancelled"
                run.finished_at = datetime.now(timezone.utc)
            search_outcome = "cancelled"
        except Exception as exc:
            await run_logger.error(
                f"Discovery failed: {exc}",
                component="discovery",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            run.status = "error"
            run.finished_at = datetime.now(timezone.utc)
            if search_run_id:
                sr = await session.get(SearchRun, search_run_id)
                if sr:
                    sr.status = "error"
                    sr.finished_at = datetime.now(timezone.utc)
                    session.add(sr)
            logger.error("trigger_discovery_failed", city=city, error=str(exc))
            search_outcome = "error"
        await session.commit()

    if search_run_id and search_outcome == "success":
        await run_events.append_search_run_event_standalone(
            run_id=search_run_id,
            event_type="stage_completed",
            message="Discovery complete — starting scraping",
            stage="discovery",
            payload={"discovery_run_id": run_id},
        )
        from doormat.runs.pipeline import run_scraping_stage

        await run_scraping_stage(search_run_id, city, preference_id)
    elif search_run_id and search_outcome == "cancelled":
        await run_events.append_search_run_event_standalone(
            run_id=search_run_id,
            event_type="cancelled",
            message="Run cancelled",
            stage="discovery",
            payload={"discovery_run_id": run_id},
        )


@router.post("/trigger", response_model=DiscoveryRunResponse)
async def trigger_discovery_v2(
    body: TriggerRequest,
    background_tasks: BackgroundTasks,
    _auth: Annotated[None, Depends(require_discovery_auth)],
    _rate_limit: Annotated[None, Depends(enforce_discovery_rate_limit)],
    session: DBSession,
) -> DiscoveryRunResponse:
    """Trigger a discovery run asynchronously.

    Creates a run record, kicks off discovery as a background task, and returns
    immediately. The frontend should poll GET /runs/{run_id} to track progress.
    """
    cleaned_city = _validate_city(body.city)
    run_id = str(uuid.uuid4())

    run = DiscoveryRun(
        id=run_id,
        city=cleaned_city,
        preference_id=body.preference_id,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.commit()

    background_tasks.add_task(_run_discovery_background, run_id, cleaned_city, body.preference_id)

    return _build_run_response(run, [])


# ─── Run history endpoints ────────────────────────────────────────────────────


@router.get("/runs", response_model=list[DiscoveryRunResponse])
async def list_runs(
    session: DBSession,
    limit: int = 20,
) -> list[DiscoveryRunResponse]:
    """List recent discovery runs, newest first."""
    stmt = select(DiscoveryRun).order_by(DiscoveryRun.started_at.desc()).limit(min(limit, 100))
    runs = (await session.execute(stmt)).scalars().all()

    result = []
    for run in runs:
        log_stmt = (
            select(DiscoveryRunLog)
            .where(DiscoveryRunLog.run_id == run.id)
            .order_by(DiscoveryRunLog.sequence)
        )
        logs = (await session.execute(log_stmt)).scalars().all()
        result.append(_build_run_response(run, list(logs)))

    return result


@router.get("/runs/{run_id}", response_model=DiscoveryRunResponse)
async def get_run(
    run_id: str,
    session: DBSession,
) -> DiscoveryRunResponse:
    """Get a single discovery run with all log lines."""
    run = await session.get(DiscoveryRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    stmt = (
        select(DiscoveryRunLog)
        .where(DiscoveryRunLog.run_id == run_id)
        .order_by(DiscoveryRunLog.sequence)
    )
    logs = (await session.execute(stmt)).scalars().all()
    return _build_run_response(run, list(logs))


# ─── Legacy city-based endpoints (keep for backward compat) ──────────────────


@router.post("/cities/{city}", response_model=DiscoveryResult)
async def trigger_discovery(
    city: str,
    _auth: Annotated[None, Depends(require_discovery_auth)],
    _rate_limit: Annotated[None, Depends(enforce_discovery_rate_limit)],
    session: DBSession,
    body: TriggerRequest | None = None,
) -> DiscoveryResult:
    cleaned_city = _validate_city(city)
    pref_id = body.preference_id if body else None
    logger.info("api_trigger_discovery", city=cleaned_city, preference_id=pref_id)
    agent = DiscoveryAgent(session=session)
    try:
        return await agent.discover_city(cleaned_city, preference_id=pref_id)
    except Exception as exc:
        logger.error("api_discovery_failed", city=cleaned_city, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="discovery failed",
        ) from exc


@router.get("/cities/{city}/managers", response_model=list[ManagerOut])
async def list_managers(city: str, session: DBSession) -> list[ManagerOut]:
    cleaned_city = _validate_city(city)
    stmt = select(PropertyManager).where(PropertyManager.city == cleaned_city)
    rows = (await session.execute(stmt)).scalars().all()
    return [ManagerOut.model_validate(r) for r in rows]


@router.get("/cities/{city}/status", response_model=CityStatus)
async def city_status(city: str, session: DBSession) -> CityStatus:
    cleaned_city = _validate_city(city)
    stmt = select(PropertyManager).where(PropertyManager.city == cleaned_city)
    rows: list[Any] = list((await session.execute(stmt)).scalars().all())
    validated_count = sum(1 for r in rows if r.validated)
    return CityStatus(
        city=cleaned_city,
        managers_total=len(rows),
        managers_validated=validated_count,
        has_been_discovered=len(rows) > 0,
    )


@router.post("/cities/{city}/scrape", response_model=ScrapeResult)
async def scrape_city_listings(  # noqa: C901
    city: str,
    session: DBSession,
    body: Optional[ScrapeRequest] = None,
) -> ScrapeResult:
    """Fetch HTML from validated property managers and run listing extraction.

    For each validated PM in the city (up to max_managers), fetches their
    website HTML and runs Mode A extraction. Scores persisted results against
    the given preference when preference_id is provided.
    """
    from doormat.extraction.orchestrator import extract_listing
    from doormat.models.orm import Listing as ListingORM
    from doormat.runs import events as run_events
    from doormat.runs import filters as run_filters
    from doormat.scoring.scorer import ListingScorer
    from doormat.sources.scrape_targets import fetch_property_manager_scrape_pages

    cleaned_city = _validate_city(city)
    preference_id = body.preference_id if body else None
    max_managers = (body.max_managers if body else None) or 5
    search_run_id = body.search_run_id if body else None

    pm_stmt = (
        select(PropertyManager)
        .where(PropertyManager.city == cleaned_city, PropertyManager.validated.is_(True))
        .limit(max_managers)
    )
    pms = list((await session.execute(pm_stmt)).scalars().all())

    preference = await session.get(Preference, preference_id) if preference_id else None
    search_run = await session.get(SearchRun, search_run_id) if search_run_id else None
    emitter = (
        run_events.SearchRunEventEmitter(session, search_run.id) if search_run is not None else None
    )

    listings_extracted = 0

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as http:
        for pm in pms:
            pm_validated = False
            if search_run_id and await run_state.is_cancel_requested(session, search_run_id):
                break
            try:
                pages = await fetch_property_manager_scrape_pages(http, pm, max_candidate_links=8)
            except Exception as exc:
                logger.warning("scrape_fetch_failed", pm=pm.name, error=str(exc))
                continue
            if not pages:
                continue

            if emitter is not None:
                await emitter.emit(
                    "stage_progress",
                    f"Discovered {len(pages)} scrape page(s) for {pm.name}",
                    stage="scraping",
                    payload={"pm": pm.name, "count": len(pages)},
                )

            for page_url, page_html in pages:
                if search_run_id and await run_state.is_cancel_requested(session, search_run_id):
                    break
                try:
                    result = await extract_listing(session, page_html, page_url, pm, preference)
                    if search_run is not None:
                        search_run.extraction_attempts += 1
                    if result.confidence != "low":
                        listings_extracted += 1
                        if search_run is not None:
                            search_run.listings_seen += 1
                            if not pm_validated:
                                search_run.managers_validated += 1
                                pm_validated = True
                            if preference is not None:
                                last_stmt = (
                                    select(ListingORM)
                                    .where(
                                        ListingORM.property_manager_id == pm.id,
                                        ListingORM.url == page_url,
                                    )
                                    .order_by(ListingORM.extraction_timestamp.desc())
                                    .limit(1)
                                )
                                listing_row = (
                                    await session.execute(last_stmt)
                                ).scalar_one_or_none()
                                if listing_row is not None:
                                    await run_filters.persist_listing_classification(
                                        session,
                                        run=search_run,
                                        listing=listing_row,
                                        preference=preference,
                                        emitter=emitter,
                                    )
                    if search_run is not None:
                        session.add(search_run)
                except Exception as exc:
                    logger.error("scrape_extract_failed", pm=pm.name, url=page_url, error=str(exc))
                    await session.rollback()

    listings_scored = 0
    if preference:
        try:
            if search_run_id and await run_state.is_cancel_requested(session, search_run_id):
                pass
            else:
                score_stmt = (
                    select(ListingORM)
                    .join(PropertyManager, ListingORM.property_manager_id == PropertyManager.id)
                    .where(
                        PropertyManager.city == cleaned_city,
                        ListingORM.score.is_(None),
                    )
                    .order_by(ListingORM.extraction_timestamp.desc())
                    .limit(50)
                )
                unscored = list((await session.execute(score_stmt)).scalars().all())
                if unscored:
                    scorer = ListingScorer()
                    await scorer.score_batch(unscored, preference)
                    await session.commit()
                    listings_scored = len(unscored)
        except Exception as exc:
            logger.error("scrape_scoring_failed", error=str(exc))

    if search_run is not None:
        session.add(search_run)
        await session.commit()

    logger.info(
        "scrape_complete",
        city=cleaned_city,
        managers_scraped=len(pms),
        listings_extracted=listings_extracted,
        listings_scored=listings_scored,
    )
    return ScrapeResult(
        city=cleaned_city,
        managers_scraped=len(pms),
        listings_extracted=listings_extracted,
        listings_scored=listings_scored,
    )
