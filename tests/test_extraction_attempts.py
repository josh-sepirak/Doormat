"""SearchRun.extraction_attempts increments on low-confidence skips, not listings_seen."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from doormat.extraction.schemas import ExtractedListing, ListingExtractionResult, PetsPolicy
from doormat.models.orm import PropertyManager, SearchRun
from doormat.runs.pipeline import _scrape_pm_direct


@pytest.mark.asyncio
async def test_low_confidence_increments_extraction_attempts_not_listings_seen(monkeypatch) -> None:
    pm = PropertyManager(
        id="pm-low",
        city="Dallas",
        name="Keyrenter",
        website="https://keyrenterdallas.com",
        listing_page_url=None,
        validated=True,
        discovery_timestamp=datetime.now(UTC),
    )
    search_run = SearchRun(
        id="run-low",
        discovery_run_id="disc-low",
        city="Dallas",
        preference_id=None,
        status="running",
        current_stage="scraping",
        cancel_requested=False,
        sources_checked=1,
        managers_validated=0,
        listings_seen=0,
        extraction_attempts=0,
        great_matches=0,
        worth_a_look=0,
        near_misses=0,
        filtered_out=0,
        cost_usd_so_far=0.0,
        active_revision=1,
        filters_json="{}",
        started_at=datetime.now(UTC),
    )

    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = [pm]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=exec_result)
    session.get = AsyncMock(return_value=search_run)
    session.add = MagicMock()
    session.commit = AsyncMock()

    class FakeEmitter:
        def __init__(self) -> None:
            self.emit = AsyncMock()

    async def fake_extract_listing(session_arg, html, url, property_manager, preference):
        return ListingExtractionResult(
            listing=ExtractedListing(
                address="1 Main",
                rent=2_000,
                bedrooms=2,
                bathrooms=1.0,
                pets_policy=PetsPolicy.UNKNOWN,
                description="x",
            ),
            confidence="low",
            mode="A",
            reasoning="uncertain",
        )

    monkeypatch.setattr(
        "doormat.runs.pipeline.fetch_property_manager_scrape_pages",
        AsyncMock(return_value=[("https://keyrenterdallas.com/p1", "<html></html>")]),
    )
    monkeypatch.setattr("doormat.extraction.orchestrator.extract_listing", fake_extract_listing)

    await _scrape_pm_direct(session, search_run, "Dallas", None, FakeEmitter())

    assert search_run.listings_seen == 0
    assert search_run.extraction_attempts == 1
    assert session.commit.await_count >= 1
