"""Tests for trusted sources API."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from doormat.config import settings
from doormat.db.base import get_db
from doormat.main import app
from doormat.models.orm import TrustedSource


@pytest.fixture(autouse=True)
def _no_auth(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_BEARER_TOKEN", "")


def _fake_db(rows: list[TrustedSource]) -> callable:
    async def _dep():
        exec_all = MagicMock()
        exec_all.scalars.return_value.all.return_value = rows
        session = MagicMock()
        session.execute = AsyncMock(return_value=exec_all)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        session.delete = AsyncMock()
        session.get = AsyncMock(return_value=None)
        session.rollback = AsyncMock()
        session.scalar = AsyncMock(return_value=0)
        yield session

    return _dep


def test_list_trusted_sources_empty():
    app.dependency_overrides[get_db] = _fake_db([])
    try:
        with TestClient(app) as client:
            r = client.get("/api/trusted-sources")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 200
    assert r.json() == []


@patch("doormat.api.routers.trusted_sources._probe_url", new_callable=AsyncMock)
def test_create_craigslist_region(mock_probe):
    mock_probe.return_value = (True, 200, None)

    created: list[TrustedSource] = []

    async def _dep():
        session = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock(side_effect=lambda obj: None)
        session.add = MagicMock(side_effect=lambda obj: created.append(obj))
        session.execute = AsyncMock()
        session.get = AsyncMock(return_value=None)
        session.rollback = AsyncMock()
        session.scalar = AsyncMock(return_value=0)
        yield session

    app.dependency_overrides[get_db] = _dep
    try:
        with TestClient(app) as client:
            r = client.post(
                "/api/trusted-sources",
                json={
                    "kind": "craigslist_region",
                    "label": "Inland Empire",
                    "url": "https://inlandempire.craigslist.org/foo",
                    "city": "Lancaster, CA",
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 201
    body = r.json()
    assert body["kind"] == "craigslist_region"
    assert body["url"] == "https://inlandempire.craigslist.org"
    assert len(created) >= 1
    assert any(getattr(x, "kind", None) == "craigslist_region" for x in created)


def test_parse_invalid_in_parse_endpoint():
    with TestClient(app) as client:
        r = client.post("/api/craigslist/regions/parse", json={"url": "https://evil.example.com"})
    assert r.status_code == 200
    assert r.json()["valid"] is False
