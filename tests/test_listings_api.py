"""Tests for listing API endpoints."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from doormat.api.routers.listings import _serialize_listing
from doormat.db.base import get_db
from doormat.main import app
from doormat.models.orm import Listing, Preference


def make_db_listing(
    listing_id: str = "listing-1",
    price: float = 1500.0,
    bedrooms: int = 2,
    saved: bool = False,
    score: float | None = None,
) -> Listing:
    return Listing(
        id=listing_id,
        property_manager_id="pm-1",
        address="123 Main St, Austin TX",
        bedrooms=bedrooms,
        bathrooms=1.0,
        sqft=800,
        price=price,
        url="https://example.com/listing-1",
        pets_policy="unknown",
        amenities=json.dumps([]),
        photos=json.dumps([]),
        description="Test listing",
        extraction_timestamp=datetime.now(UTC),
        validation_passed=True,
        saved=saved,
        score=score,
        score_explanation="Test explanation" if score is not None else None,
    )


def make_preference() -> Preference:
    return Preference(
        id="pref-1",
        description="2BR pet-friendly under $2000",
        city="Austin",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _fake_db_with_scalars(rows: list) -> callable:
    async def _dep():
        exec_result = MagicMock()
        exec_result.scalars.return_value.all.return_value = rows
        session = AsyncMock()
        session.execute = AsyncMock(return_value=exec_result)
        yield session

    return _dep


def _fake_db_with_one(row) -> callable:
    async def _dep():
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = row
        session = AsyncMock()
        session.execute = AsyncMock(return_value=exec_result)
        session.commit = AsyncMock()
        yield session

    return _dep


def test_get_listings_returns_200():
    """GET /api/listings should return a paginated list."""
    listings = [make_db_listing("l-1"), make_db_listing("l-2", price=2000.0)]
    app.dependency_overrides[get_db] = _fake_db_with_scalars(listings)

    try:
        with TestClient(app) as client:
            resp = client.get("/api/listings")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["id"] == "l-1"


def test_listings_stream_route_is_not_shadowed_by_listing_id_route():
    """Specific SSE route should be registered before /{listing_id}."""
    listing_paths = [
        getattr(route, "path", "")
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/listings")
    ]

    assert listing_paths.index("/api/listings/stream") < listing_paths.index(
        "/api/listings/{listing_id}"
    )


def test_serialize_listing_tolerates_corrupt_json_fields():
    """Bad cached extraction JSON should not break the listing API."""
    listing = make_db_listing()
    listing.amenities = "{not-json"
    listing.photos = "{not-json"

    data = _serialize_listing(listing)

    assert data["amenities"] == []
    assert data["photos"] == []


def test_serialize_listing_rejects_unsafe_url_schemes():
    """Scraped listing URLs must not become javascript: links in the frontend."""
    listing = make_db_listing()
    listing.url = "javascript:alert(1)"

    data = _serialize_listing(listing)

    assert data["url"] is None


def test_get_listing_by_id_returns_404_when_missing():
    """GET /api/listings/{id} should return 404 for unknown IDs."""
    app.dependency_overrides[get_db] = _fake_db_with_one(None)

    try:
        with TestClient(app) as client:
            resp = client.get("/api/listings/nonexistent-id")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


def test_get_listing_by_id_returns_listing():
    """GET /api/listings/{id} should return the listing when found."""
    listing = make_db_listing(score=0.85)
    app.dependency_overrides[get_db] = _fake_db_with_one(listing)

    try:
        with TestClient(app) as client:
            resp = client.get("/api/listings/listing-1")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == 0.85
    assert data["address"] == "123 Main St, Austin TX"


def test_save_listing_toggles_saved():
    """POST /api/listings/{id}/save should toggle the saved flag."""
    listing = make_db_listing(saved=False)
    app.dependency_overrides[get_db] = _fake_db_with_one(listing)

    try:
        with TestClient(app) as client:
            resp = client.post("/api/listings/listing-1/save")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["saved"] is True


def test_save_listing_returns_404_when_missing():
    """POST /api/listings/{id}/save should return 404 for unknown listing."""
    app.dependency_overrides[get_db] = _fake_db_with_one(None)

    try:
        with TestClient(app) as client:
            resp = client.post("/api/listings/nonexistent/save")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


def test_score_listings_endpoint_runs_scorer(monkeypatch):
    """POST /api/listings/score should update matching listings and commit."""
    listings = [make_db_listing("l-1"), make_db_listing("l-2")]
    pref_result = MagicMock()
    pref_result.scalar_one_or_none.return_value = make_preference()
    listing_result = MagicMock()
    listing_result.scalars.return_value.all.return_value = listings
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[pref_result, listing_result])
    session.commit = AsyncMock()

    async def _dep():
        yield session

    class FakeScorer:
        async def score_batch(self, rows, preference):
            for row in rows:
                row.score = 0.8
                row.score_explanation = f"Scored for {preference.city}"

    import doormat.api.routers.listings as listings_router

    monkeypatch.setattr(listings_router, "ListingScorer", FakeScorer)
    app.dependency_overrides[get_db] = _dep

    try:
        with TestClient(app) as client:
            resp = client.post("/api/listings/score", json={"preference_id": "pref-1"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["scored_count"] == 2
    assert listings[0].score == 0.8
    session.commit.assert_awaited_once()


def test_get_listings_filters_by_max_price():
    """GET /api/listings?max_price=1600 should apply price filter."""
    listings = [make_db_listing("l-1", price=1500.0)]
    app.dependency_overrides[get_db] = _fake_db_with_scalars(listings)

    try:
        with TestClient(app) as client:
            resp = client.get("/api/listings?max_price=1600")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert all(listing["price"] <= 1600 for listing in data)
