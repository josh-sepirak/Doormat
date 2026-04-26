"""Unit tests for listing extraction helpers."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from doormat.extraction import mode_a, mode_b
from doormat.extraction.orchestrator import (
    _identify_missing_fields,
    _is_persistable_result,
    _save_listing,
    extract_listing,
)
from doormat.extraction.schemas import ExtractedListing, ListingExtractionResult, StrategyUpdate
from doormat.extraction.strategy import StrategyCache
from doormat.models.orm import PropertyManager
from doormat.schemas import PetsPolicy


def make_listing(
    *,
    address: str = "123 Main St",
    rent: int = 1_500,
    bedrooms: int = 2,
) -> ExtractedListing:
    """Build an extracted listing fixture."""
    return ExtractedListing(
        address=address,
        rent=rent,
        bedrooms=bedrooms,
        bathrooms=1.0,
        pets_policy=PetsPolicy.UNKNOWN,
        description="Test listing",
    )


def make_result(*, confidence: str = "high", mode: str = "A") -> ListingExtractionResult:
    """Build an extraction result fixture."""
    return ListingExtractionResult(
        listing=make_listing(),
        confidence=confidence,
        mode=mode,
    )


@pytest.mark.asyncio
async def test_mode_a_uses_structured_llm_response(monkeypatch):
    """Mode A should return the structured extraction response from the LLM client."""

    class FakeLLM:
        async def complete(self, **kwargs):
            assert kwargs["response_model"] is ListingExtractionResult
            return make_result(mode="A")

    monkeypatch.setattr(mode_a, "get_llm_client", lambda: FakeLLM())

    result = await mode_a.run_mode_a("<html></html>", "https://example.com", "pm-1", None)

    assert result.mode == "A"
    assert result.confidence == "high"


@pytest.mark.asyncio
async def test_mode_a_truncates_html_before_prompt(monkeypatch):
    """Mode A should bound prompt size before sending scraped HTML to the LLM."""
    captured_messages = {}

    class FakeLLM:
        async def complete(self, **kwargs):
            captured_messages["messages"] = kwargs["messages"]
            return make_result(mode="A")

    monkeypatch.setattr(mode_a, "get_llm_client", lambda: FakeLLM())
    monkeypatch.setattr(mode_a, "MAX_MODE_A_HTML_CHARS", 8)

    result = await mode_a.run_mode_a("x" * 20, "https://example.com", "pm-1", None)

    assert result.mode == "A"
    assert "[truncated" in captured_messages["messages"][1]["content"]


@pytest.mark.asyncio
async def test_mode_b_falls_back_when_browser_use_unavailable(monkeypatch):
    """Mode B should degrade to a low-confidence result when browser tooling is absent."""
    monkeypatch.setattr(mode_b, "BROWSER_USE_AVAILABLE", False)

    result = await mode_b.run_mode_b(
        "https://example.com/listing",
        "pm-1",
        prior_failure={"missing_fields": ["rent"]},
    )

    assert result.mode == "B"
    assert result.confidence == "low"
    assert result.listing.rent == 0


@pytest.mark.asyncio
async def test_mode_b_falls_back_when_api_key_missing(monkeypatch):
    """Mode B should fail closed when agent tooling exists but no OpenRouter key is configured."""
    monkeypatch.setattr(mode_b, "BROWSER_USE_AVAILABLE", True)
    monkeypatch.setattr(mode_b.settings, "OPENROUTER_API_KEY", "")

    result = await mode_b.run_mode_b(
        "https://example.com/listing",
        "pm-1",
        prior_failure={"missing_fields": ["rent"]},
    )

    assert result.mode == "B"
    assert result.confidence == "low"
    assert "OPENROUTER_API_KEY" in (result.reasoning or "")


def test_identify_missing_fields():
    """Missing-field detection should flag unknown rent, address, and bedrooms."""
    listing = make_listing(address="Unknown - see source URL", rent=0, bedrooms=0)

    assert _identify_missing_fields(listing) == ["rent", "address", "bedrooms"]


def test_low_confidence_or_missing_price_is_not_persistable():
    """Low quality extraction results should not poison the listings table."""
    assert _is_persistable_result(make_result(confidence="low")) is False
    assert (
        _is_persistable_result(
            ListingExtractionResult(listing=make_listing(rent=0), confidence="medium", mode="B")
        )
        is False
    )


@pytest.mark.asyncio
async def test_save_listing_persists_extracted_data():
    """Saving an extraction result should persist a Listing ORM row."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    manager = PropertyManager(
        id="pm-1",
        city="Austin",
        name="Test PM",
        website="https://example.com",
        listing_page_url=None,
        validated=True,
        discovery_timestamp=datetime.now(UTC),
    )

    result = await _save_listing(
        session,
        make_result(mode="A"),
        manager,
        "https://example.com/listing",
    )

    saved_listing = session.add.call_args.args[0]
    assert result.mode == "A"
    assert saved_listing.property_manager_id == "pm-1"
    assert saved_listing.price == 1_500
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_listing_returns_low_confidence_without_persisting(monkeypatch):
    """If Mode B cannot recover, extraction should return evidence without saving junk rows."""
    session = AsyncMock()
    session.add = MagicMock()
    manager = PropertyManager(
        id="pm-1",
        city="Austin",
        name="Test PM",
        website="https://example.com",
        listing_page_url=None,
        validated=True,
        discovery_timestamp=datetime.now(UTC),
    )

    async def fake_mode_a(*args, **kwargs):
        return make_result(confidence="low", mode="A")

    async def fake_mode_b(*args, **kwargs):
        return make_result(confidence="low", mode="B")

    class FakeStrategyCache:
        def __init__(self, session):
            self.session = session

        async def get(self, source_id):
            return None

    monkeypatch.setattr("doormat.extraction.orchestrator.run_mode_a", fake_mode_a)
    monkeypatch.setattr("doormat.extraction.orchestrator.run_mode_b", fake_mode_b)
    monkeypatch.setattr("doormat.extraction.orchestrator.StrategyCache", FakeStrategyCache)

    result = await extract_listing(session, "<html></html>", "https://example.com", manager)

    assert result.confidence == "low"
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_strategy_cache_merge_creates_strategy_when_missing():
    """Strategy merge should create a new strategy row when no cached strategy exists."""
    scalars = MagicMock()
    scalars.first.return_value = None
    exec_result = MagicMock()
    exec_result.scalars.return_value = scalars

    session = AsyncMock()
    session.execute = AsyncMock(return_value=exec_result)
    session.add = MagicMock()
    session.commit = AsyncMock()

    cache = StrategyCache(session)
    result = await cache.merge(
        "pm-1",
        StrategyUpdate(field_selectors={"rent": ".rent"}, pre_extraction_actions=["scroll down"]),
    )

    saved_strategy = session.add.call_args.args[0]
    assert result is True
    assert saved_strategy.property_manager_id == "pm-1"
    assert '"rent": ".rent"' in saved_strategy.strategy_json
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_strategy_cache_recovers_from_corrupt_strategy_json():
    """Bad cached strategy JSON should be quarantined instead of crashing extraction."""
    existing_strategy = MagicMock()
    existing_strategy.id = "strategy-1"
    existing_strategy.strategy_json = "{not-json"

    scalars = MagicMock()
    scalars.first.return_value = existing_strategy
    exec_result = MagicMock()
    exec_result.scalars.return_value = scalars

    session = AsyncMock()
    session.execute = AsyncMock(return_value=exec_result)
    session.add = MagicMock()
    session.commit = AsyncMock()

    cache = StrategyCache(session)
    result = await cache.merge("pm-1", StrategyUpdate(field_selectors={"rent": ".rent"}))

    assert result is True
    assert '"rent": ".rent"' in existing_strategy.strategy_json
