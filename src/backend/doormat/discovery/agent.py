"""DiscoveryAgent orchestrates the full city discovery workflow.

Pipeline:
  1. Cache hit check (PropertyManager rows for the city). If validated rows
     exist, return early with cached=True.
  2. LLM-based candidate search.
  3. Browser-use candidate search (no-op when unavailable).
  4. Domain dedupe across both sources.
  5. LLM classification of each candidate.
  6. Up to 2 retries with refined search if no candidates validated.
  7. Persist validated candidates to PropertyManager table.
  8. Return DiscoveryResult with cost and duration.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.cost_tracking import get_cost_tracker
from doormat.discovery.browser import BrowserDiscovery
from doormat.discovery.classifier import PropertyManagerClassifier
from doormat.discovery.models import (
    DiscoveryCandidate,
    DiscoveryResult,
    RunLoggerProtocol,
    ValidationResult,
)
from doormat.discovery.search import DiscoverySearch, _dedupe_by_domain
from doormat.models.orm import Preference, PropertyManager
from doormat.runs.errors import CooperativeCancel

logger = structlog.get_logger(__name__)

MAX_RETRIES = 2


class DiscoveryAgent:
    """Coordinator for property manager discovery for a city."""

    def __init__(
        self,
        session: AsyncSession,
        search: Optional[DiscoverySearch] = None,
        browser: Optional[BrowserDiscovery] = None,
        classifier: Optional[PropertyManagerClassifier] = None,
    ) -> None:
        self._session = session
        self._search = search or DiscoverySearch()
        self._browser = browser or BrowserDiscovery()
        self._classifier = classifier or PropertyManagerClassifier()

    async def discover_city(
        self,
        city: str,
        preference_id: str | None = None,
        run_logger: Optional[RunLoggerProtocol] = None,
        cancel_check: Optional[Callable[[], Awaitable[bool]]] = None,
    ) -> DiscoveryResult:
        """Run the discovery pipeline for `city`."""
        request_id = uuid.uuid4().hex[:12]
        log = logger.bind(request_id=request_id, city=city, preference_id=preference_id)
        log.info("discovery_start")

        preference_row: Preference | None = None
        if preference_id:
            preference_row = await self._session.get(Preference, preference_id)

        if cancel_check and await cancel_check():
            raise CooperativeCancel()

        cached_pm = await self._cached_managers(city)
        if cached_pm:
            log.info("discovery_cache_hit", validated_count=len(cached_pm))
            if run_logger:
                await run_logger.info(
                    f"Cache hit — returning {len(cached_pm)} previously validated managers",
                    component="agent",
                )
            return DiscoveryResult(
                city=city,
                candidates_found=len(cached_pm),
                validated_count=len(cached_pm),
                cached=True,
                cost_usd=0.0,
                duration_seconds=0.0,
            )

        cost_before = get_cost_tracker().total_cost()
        start_time = time.monotonic()

        candidates, validated_pairs = await self._search_and_classify(
            city, log, run_logger, cancel_check, preference_row
        )

        validated_count = await self._persist_validated(city, validated_pairs, log)

        duration = time.monotonic() - start_time
        cost_after = get_cost_tracker().total_cost()
        cost_delta = max(0.0, cost_after - cost_before)

        result = DiscoveryResult(
            city=city,
            candidates_found=len(candidates),
            validated_count=validated_count,
            cached=False,
            cost_usd=cost_delta,
            duration_seconds=duration,
        )

        log.info(
            "discovery_complete",
            candidates_found=result.candidates_found,
            validated_count=result.validated_count,
            cost_usd=result.cost_usd,
            duration_seconds=result.duration_seconds,
        )
        return result

    async def _cached_managers(self, city: str) -> list[PropertyManager]:
        """Return previously-validated managers for the city, if any.

        Also backfills ``listing_page_url`` from ``website`` for any cached row
        that pre-dates the field, so the multi-page scraper has a starting URL.
        """
        stmt = select(PropertyManager).where(
            PropertyManager.city == city,
            PropertyManager.validated.is_(True),
        )
        rows = (await self._session.execute(stmt)).scalars().all()

        # Backfill: any PM saved before listing_page_url existed will have NULL.
        # Set it to website so fetch_property_manager_scrape_pages has a seed URL.
        needs_backfill = [pm for pm in rows if pm.listing_page_url is None and pm.website]
        if needs_backfill:
            await self._session.execute(
                update(PropertyManager)
                .where(
                    PropertyManager.city == city,
                    PropertyManager.listing_page_url.is_(None),
                    PropertyManager.website.isnot(None),
                )
                .values(listing_page_url=PropertyManager.website)
            )
            await self._session.commit()
            # Refresh in-memory objects so callers see updated values.
            for pm in needs_backfill:
                await self._session.refresh(pm)

        return list(rows)

    async def _search_and_classify(  # noqa: C901
        self,
        city: str,
        log: structlog.stdlib.BoundLogger,
        run_logger: Optional[RunLoggerProtocol] = None,
        cancel_check: Optional[Callable[[], Awaitable[bool]]] = None,
        preference: Preference | None = None,
    ) -> tuple[list[DiscoveryCandidate], list[tuple[DiscoveryCandidate, ValidationResult]]]:
        """Run search + classification with up to MAX_RETRIES refinement loops."""
        all_candidates: list[DiscoveryCandidate] = []
        validated: list[tuple[DiscoveryCandidate, ValidationResult]] = []
        refinement: str | None = None

        for attempt in range(MAX_RETRIES + 1):
            if cancel_check and await cancel_check():
                raise CooperativeCancel()
            log.info("discovery_attempt", attempt=attempt + 1, max=MAX_RETRIES + 1)
            if run_logger:
                await run_logger.info(
                    f"Search attempt {attempt + 1}/{MAX_RETRIES + 1}", component="agent"
                )
            if run_logger:
                await run_logger.info(
                    "Starting LLM candidate search",
                    component="discovery",
                    event_type="search_query_started",
                )
            llm_cands = await self._search.find_candidates(
                city,
                refinement=refinement,
                run_logger=run_logger,
                preference=preference,
            )
            browser_cands = await self._browser.discover(city)
            attempt_candidates = _dedupe_by_domain(llm_cands + browser_cands)

            if run_logger:
                await run_logger.info(
                    f"Classifying {len(attempt_candidates)} candidates", component="agent"
                )

            # Track distinct candidates ever seen (for reporting).
            for cand in attempt_candidates:
                if cand not in all_candidates:
                    all_candidates.append(cand)

            if run_logger and not attempt_candidates:
                await run_logger.warning(
                    "LLM returned 0 candidates — model may not support structured output",
                    component="agent",
                )

            if run_logger:
                await run_logger.info(
                    "Search query completed",
                    component="discovery",
                    event_type="search_query_completed",
                    candidates=len(attempt_candidates),
                )

            attempt_validated = await self._classify_candidates(
                attempt_candidates, log, run_logger, cancel_check, preference
            )
            validated.extend(attempt_validated)

            if attempt_validated:
                break

            if run_logger:
                await run_logger.warning(
                    f"Attempt {attempt + 1}: 0 validated — retrying with refined search",
                    component="agent",
                )
            refinement = (
                "Previous attempt yielded zero validated property managers. "
                "Focus on smaller, locally-active companies (not aggregators), "
                "and try alternative naming variations."
            )

        return all_candidates, validated

    async def _classify_candidates(
        self,
        candidates: list[DiscoveryCandidate],
        log: structlog.stdlib.BoundLogger,
        run_logger: Optional[RunLoggerProtocol] = None,
        cancel_check: Optional[Callable[[], Awaitable[bool]]] = None,
        preference: Preference | None = None,
    ) -> list[tuple[DiscoveryCandidate, ValidationResult]]:
        """Classify each candidate; return only valid pairs."""
        validated: list[tuple[DiscoveryCandidate, ValidationResult]] = []
        for cand in candidates:
            if cancel_check and await cancel_check():
                raise CooperativeCancel()
            if run_logger:
                await run_logger.debug(
                    f"Classifying: {cand.name} ({cand.website})", component="classifier"
                )
            result = await self._classifier.classify(cand, preference=preference)
            if result.is_valid:
                validated.append((cand, result))
                if run_logger:
                    await run_logger.success(
                        f"✓ {cand.name} — validated (confidence: {result.confidence:.0%})",
                        component="classifier",
                    )
            else:
                log.info(
                    "candidate_rejected",
                    candidate=cand.name,
                    reason=result.reason,
                    confidence=result.confidence,
                )
                if run_logger:
                    await run_logger.debug(
                        f"✗ {cand.name} — rejected: {result.reason}",
                        component="classifier",
                    )
        return validated

    async def _persist_validated(
        self,
        city: str,
        validated_pairs: list[tuple[DiscoveryCandidate, ValidationResult]],
        log: structlog.stdlib.BoundLogger,
    ) -> int:
        """Persist validated PMs; return the count actually persisted."""
        persisted = 0
        for candidate, _result in validated_pairs:
            try:
                pm = PropertyManager(
                    id=str(uuid.uuid4()),
                    city=city,
                    name=candidate.name,
                    website=candidate.website,
                    listing_page_url=candidate.website,
                    validated=True,
                    discovery_timestamp=datetime.now(UTC),
                )
                self._session.add(pm)
                persisted += 1
            except Exception as exc:
                log.error(
                    "persist_failed",
                    candidate=candidate.name,
                    error=str(exc),
                )
        if persisted:
            try:
                await self._session.commit()
            except Exception as exc:
                log.error("commit_failed", error=str(exc))
                await self._session.rollback()
                return 0
        return persisted
