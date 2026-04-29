"""Tests for property manager scrape URL resolution and candidate discovery."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.dialects import sqlite

from doormat.extraction.schemas import ExtractedListing, ListingExtractionResult
from doormat.models.orm import Listing as ListingORM
from doormat.models.orm import Preference, PropertyManager, SearchRun
from doormat.runs.pipeline import _run_scoring_stage, _scrape_pm_direct, _scrapeable_property_managers_stmt
from doormat.schemas import PetsPolicy
from doormat.sources.scrape_targets import (
    discover_candidate_listing_urls,
    fetch_property_manager_scrape_pages,
)
from doormat.sources.urls import resolve_property_manager_scrape_url


def test_resolve_property_manager_scrape_url_prefers_listing_page() -> None:
    pm = PropertyManager(
        id="pm-1",
        city="Austin",
        name="Acme PM",
        website="https://acme.example",
        listing_page_url="https://acme.example/listings",
        validated=True,
        discovery_timestamp=datetime.now(UTC),
    )

    assert resolve_property_manager_scrape_url(pm) == "https://acme.example/listings"


def test_resolve_property_manager_scrape_url_falls_back_to_website() -> None:
    pm = PropertyManager(
        id="pm-1",
        city="Austin",
        name="Acme PM",
        website="https://acme.example",
        listing_page_url=None,
        validated=True,
        discovery_timestamp=datetime.now(UTC),
    )

    assert resolve_property_manager_scrape_url(pm) == "https://acme.example"


def test_scrapeable_property_managers_stmt_includes_website_fallback() -> None:
    stmt = _scrapeable_property_managers_stmt("Austin")
    compiled = str(stmt.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))

    assert "property_managers.website IS NOT NULL" in compiled
    assert "property_managers.listing_page_url IS NOT NULL" in compiled


def test_discover_candidate_listing_urls_prefers_listing_links() -> None:
    html = """
    <html>
      <body>
        <a href="/about">About us</a>
        <a href="/available-apartments">Available apartments</a>
        <a href="https://acme.example/properties/floor-plans">Floor plans</a>
        <a href="https://other.example/listings">Off-site listing</a>
      </body>
    </html>
    """

    urls = discover_candidate_listing_urls(html, "https://acme.example", limit=5)

    assert urls == [
        "https://acme.example/available-apartments",
        "https://acme.example/properties/floor-plans",
    ]


@pytest.mark.asyncio
async def test_fetch_property_manager_scrape_pages_discovers_candidate_pages() -> None:
    pm = PropertyManager(
        id="pm-1",
        city="Austin",
        name="Acme PM",
        website="https://acme.example",
        listing_page_url=None,
        validated=True,
        discovery_timestamp=datetime.now(UTC),
    )

    homepage = """
    <html>
      <body>
        <a href="/about">About us</a>
        <a href="/available-apartments">Available apartments</a>
      </body>
    </html>
    """
    listing_page = "<html><body>listing page</body></html>"

    class FakeClient:
        requests: list[str]

        def __init__(self) -> None:
            self.requests = []

        async def get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
            self.requests.append(url)
            if url == "https://acme.example":
                return httpx.Response(
                    200,
                    content=homepage.encode(),
                    request=httpx.Request("GET", url),
                )
            if url == "https://acme.example/available-apartments":
                return httpx.Response(
                    200,
                    content=listing_page.encode(),
                    request=httpx.Request("GET", url),
                )
            raise AssertionError(f"unexpected URL: {url}")

    client = FakeClient()
    pages = await fetch_property_manager_scrape_pages(client, pm, max_candidate_links=5)

    assert pages == [
        ("https://acme.example", homepage),
        ("https://acme.example/available-apartments", listing_page),
    ]
    assert client.requests == [
        "https://acme.example",
        "https://acme.example/available-apartments",
    ]


@pytest.mark.asyncio
async def test_scrape_pm_direct_uses_discovered_pages(monkeypatch) -> None:
    pm = PropertyManager(
        id="pm-1",
        city="Austin",
        name="Acme PM",
        website="https://acme.example",
        listing_page_url=None,
        validated=True,
        discovery_timestamp=datetime.now(UTC),
    )
    search_run = SearchRun(
        id="run-1",
        discovery_run_id="disc-1",
        city="Austin",
        preference_id=None,
        status="running",
        current_stage="scraping",
        cancel_requested=False,
        sources_checked=0,
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
        extracted_urls.append(url)
        assert property_manager.id == pm.id
        return ListingExtractionResult(
            listing=ExtractedListing(
                address="123 Main St",
                rent=1_500,
                bedrooms=2,
                bathrooms=1.0,
                pets_policy=PetsPolicy.UNKNOWN,
                description="Test listing",
            ),
            confidence="high",
            mode="A",
        )

    extracted_urls: list[str] = []
    monkeypatch.setattr(
        "doormat.runs.pipeline.fetch_property_manager_scrape_pages",
        AsyncMock(
            return_value=[
                ("https://acme.example", "<html>homepage</html>"),
                ("https://acme.example/available-apartments", "<html>listing</html>"),
            ]
        ),
    )
    monkeypatch.setattr("doormat.extraction.orchestrator.extract_listing", fake_extract_listing)

    await _scrape_pm_direct(session, search_run, "Austin", None, FakeEmitter())

    assert extracted_urls == [
        "https://acme.example",
        "https://acme.example/available-apartments",
    ]
    assert search_run.listings_seen == 2
    assert search_run.extraction_attempts == 2
    assert search_run.managers_validated == 1
    assert session.commit.await_count >= 1


@pytest.mark.asyncio
async def test_run_scoring_stage_queries_by_city_not_preference_id(monkeypatch) -> None:
    """_run_scoring_stage must use a city join so PM-direct listings (preference_id=NULL) score."""
    from doormat.runs import events as run_events

    search_run = SearchRun(
        id="run-2",
        discovery_run_id="disc-2",
        city="Austin",
        preference_id="pref-1",
        status="running",
        current_stage="scraping",
        cancel_requested=False,
        sources_checked=0,
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
    preference = Preference(
        id="pref-1",
        description="Test pref",
        city="Austin",
    )

    # Build a listing that has preference_id=NULL (as PM-direct listings do).
    pm = PropertyManager(
        id="pm-99",
        city="Austin",
        name="Direct PM",
        website="https://direct.example",
        listing_page_url="https://direct.example/listings",
        validated=True,
        discovery_timestamp=datetime.now(UTC),
    )
    listing_without_pref = ListingORM(
        id="listing-99",
        property_manager_id="pm-99",
        address="99 Test Ave",
        price=1800,
        url="https://direct.example/listings/1",
        validation_passed=True,
        score=None,
        preference_id=None,  # PM-direct: no preference linked
    )

    scored: list[str] = []
    classify_called: list[bool] = []

    exec_result_listings = MagicMock()
    exec_result_listings.scalars.return_value.all.return_value = [listing_without_pref]
    exec_result_generic = MagicMock()
    exec_result_generic.scalars.return_value.all.return_value = []

    session = AsyncMock()
    # First execute call → SELECT unscored listings; subsequent → classify pass deletes/inserts
    session.execute = AsyncMock(
        side_effect=[exec_result_listings, exec_result_generic, exec_result_generic]
    )
    session.get = AsyncMock(return_value=search_run)
    session.add = MagicMock()
    session.commit = AsyncMock()

    emitter = AsyncMock(spec=run_events.SearchRunEventEmitter)
    emitter.stage_started = AsyncMock()
    emitter.stage_completed = AsyncMock()
    emitter.emit = AsyncMock()

    async def fake_score_batch(listings, pref):
        for l in listings:
            scored.append(l.id)
            l.score = 0.85

    async def fake_classify(sess, *, run, city, preference, emitter=None):
        classify_called.append(True)
        return len(classify_called)

    monkeypatch.setattr("doormat.runs.filters.classify_city_listings_for_run", fake_classify)
    monkeypatch.setattr("doormat.runs.pipeline.run_filters.classify_city_listings_for_run", fake_classify)

    with patch("doormat.scoring.scorer.ListingScorer") as MockScorer:
        MockScorer.return_value.score_batch = AsyncMock(side_effect=fake_score_batch)
        await _run_scoring_stage(session, search_run, "Austin", preference, emitter)

    # The listing without preference_id should still be scored.
    assert "listing-99" in scored
    # classify_city_listings_for_run should be called to update the counters.
    assert classify_called, "classify_city_listings_for_run was not called after scoring"
