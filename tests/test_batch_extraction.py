"""Tests for policy-aware batch listing extraction."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest

from doormat.extraction.batch import BatchExtractionPolicy, BatchExtractor
from doormat.extraction.schemas import ExtractedListing, ListingExtractionResult
from doormat.models.orm import PropertyManager
from doormat.schemas import PetsPolicy


def make_manager() -> PropertyManager:
    """Build a property manager with a canonical listing origin."""
    return PropertyManager(
        id="pm-1",
        city="Austin",
        name="Test PM",
        website="https://pm.example",
        listing_page_url="https://pm.example/listings",
        validated=True,
        discovery_timestamp=datetime.now(UTC),
    )


def make_extraction() -> ListingExtractionResult:
    """Build a successful extraction result."""
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


def client_factory(handler):
    """Create an AsyncClient factory backed by a MockTransport."""

    @asynccontextmanager
    async def _factory() -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
        ) as client:
            yield client

    return _factory


async def no_sleep(_: float) -> None:
    """Avoid slowing tests while preserving the async sleep contract."""


def test_batch_policy_rejects_invalid_bounds():
    """Crawler limits should fail fast when configured unsafely."""
    with pytest.raises(ValueError):
        BatchExtractionPolicy(max_urls=0)


@pytest.mark.asyncio
async def test_batch_extractor_rejects_cross_origin_and_non_http_urls():
    """Batch extraction should not become an SSRF/open crawler primitive."""
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, text="<html>ok</html>", headers={"content-type": "text/html"})

    extractor_call = AsyncMock(return_value=make_extraction())
    batch = BatchExtractor(
        session=AsyncMock(),
        property_manager=make_manager(),
        client_factory=client_factory(handler),
        extractor=extractor_call,
        sleep=no_sleep,
    )

    results = await batch.process_urls(
        [
            "https://evil.example/listing",
            "file:///etc/passwd",
            "https://pm.example/listing-1",
        ]
    )

    assert len(results) == 1
    assert seen_urls == [
        "https://pm.example/robots.txt",
        "https://pm.example/listing-1",
    ]
    extractor_call.assert_awaited_once()


@pytest.mark.asyncio
async def test_batch_extractor_honors_robots_txt_disallow():
    """Robots disallow rules should prevent fetch and extraction."""
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
        return httpx.Response(200, text="<html>should not be fetched</html>")

    extractor_call = AsyncMock(return_value=make_extraction())
    batch = BatchExtractor(
        session=AsyncMock(),
        property_manager=make_manager(),
        client_factory=client_factory(handler),
        extractor=extractor_call,
        sleep=no_sleep,
    )

    results = await batch.process_urls(["https://pm.example/private/listing-1"])

    assert results == []
    assert seen_urls == ["https://pm.example/robots.txt"]
    extractor_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_batch_extractor_enforces_html_size_limit():
    """Oversized pages should be skipped before the LLM extraction path."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, content=b"x" * 20, headers={"content-type": "text/html"})

    extractor_call = AsyncMock(return_value=make_extraction())
    batch = BatchExtractor(
        session=AsyncMock(),
        property_manager=make_manager(),
        client_factory=client_factory(handler),
        extractor=extractor_call,
        sleep=no_sleep,
        policy=BatchExtractionPolicy(max_html_bytes=10),
    )

    results = await batch.process_urls(["https://pm.example/listing-1"])

    assert results == []
    extractor_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_batch_extractor_dedupes_and_limits_urls():
    """Batch policy should bound work and avoid duplicate extraction."""
    fetched_listing_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        fetched_listing_urls.append(str(request.url))
        return httpx.Response(200, text="<html>ok</html>", headers={"content-type": "text/html"})

    extractor_call = AsyncMock(return_value=make_extraction())
    batch = BatchExtractor(
        session=AsyncMock(),
        property_manager=make_manager(),
        client_factory=client_factory(handler),
        extractor=extractor_call,
        sleep=no_sleep,
        policy=BatchExtractionPolicy(max_urls=2),
    )

    results = await batch.process_urls(
        [
            "https://pm.example/listing-1",
            "https://pm.example/listing-1",
            "https://pm.example/listing-2",
            "https://pm.example/listing-3",
        ]
    )

    assert len(results) == 2
    assert fetched_listing_urls == [
        "https://pm.example/listing-1",
        "https://pm.example/listing-2",
    ]
