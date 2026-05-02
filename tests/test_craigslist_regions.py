"""Tests for Craigslist region catalog and suggest API."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from doormat.api.routers import craigslist_regions as craigslist_regions_router
from doormat.config import settings
from doormat.db.base import get_db
from doormat.main import app
from doormat.sources.craigslist_regions import haversine_miles, load_regions, nearest_regions


@pytest.fixture(autouse=True)
def _no_auth(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_BEARER_TOKEN", "")


def test_load_regions_non_empty():
    regions = load_regions()
    assert len(regions) > 400
    subs = {r.subdomain for r in regions}
    assert "inlandempire" in subs
    assert "sfbay" in subs


def test_nearest_regions_lancaster_ca_prefers_inland_empire():
    lat, lon = 34.6868, -118.1542
    ranked = nearest_regions(lat, lon, k=5)
    subs = [r.subdomain for r, _ in ranked]
    assert "inlandempire" in subs
    assert subs[0] == "inlandempire" or subs.index("inlandempire") <= 2


def test_haversine_miles_reasonable():
    d = haversine_miles(34.0, -118.0, 34.1, -118.1)
    assert 5 < d < 15


def test_regions_api_uses_geocode(monkeypatch):
    async def _fake_geocode(_session, _query):
        return {"lat": 34.6868, "lon": -118.1542, "display_name": "Lancaster, CA, USA"}

    monkeypatch.setattr(craigslist_regions_router, "geocode_place", _fake_geocode)

    async def _fake_db():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = _fake_db
    try:
        with TestClient(app) as client:
            r = client.get("/api/craigslist/regions", params={"city": "Lancaster", "state": "CA"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    body = r.json()
    assert body["geocoded"]["lat"] == pytest.approx(34.6868)
    subs = [s["subdomain"] for s in body["suggestions"]]
    assert "inlandempire" in subs


def test_parse_region_url():
    with TestClient(app) as client:
        r = client.post(
            "/api/craigslist/regions/parse",
            json={"url": "https://inlandempire.craigslist.org/search/apa"},
        )
    assert r.status_code == 200
    b = r.json()
    assert b["valid"] is True
    assert b["subdomain"] == "inlandempire"
    assert b["url"] == "https://inlandempire.craigslist.org"
