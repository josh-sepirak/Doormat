"""Tests for extraction API boundary behavior."""

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from doormat.api.routers import discovery
from doormat.config import settings
from doormat.db.base import get_db
from doormat.main import app


def test_trigger_extraction_requires_bearer_when_configured(monkeypatch):
    """Manual extraction can call LLM/browser work, so configured auth must gate it."""
    monkeypatch.setattr(settings, "AUTH_BEARER_TOKEN", "test-token")
    discovery.reset_discovery_rate_limits()

    with TestClient(app) as client:
        response = client.post(
            "/extraction/trigger",
            json={
                "property_manager_id": "pm-1",
                "url": "https://example.com/listing",
                "html": "<html></html>",
            },
        )

    assert response.status_code == 401


def test_trigger_extraction_validates_url():
    """The request schema should reject malformed listing URLs before DB work."""
    with TestClient(app) as client:
        response = client.post(
            "/extraction/trigger",
            json={
                "property_manager_id": "pm-1",
                "url": "not-a-url",
                "html": "<html></html>",
            },
        )

    assert response.status_code == 422


async def _fake_empty_db():
    scalars = MagicMock()
    scalars.first.return_value = None
    exec_result = MagicMock()
    exec_result.scalars.return_value = scalars

    session = AsyncMock()
    session.execute = AsyncMock(return_value=exec_result)
    yield session


def test_trigger_extraction_returns_404_for_unknown_manager(monkeypatch):
    """Unknown property managers should fail without invoking extraction."""
    monkeypatch.setattr(settings, "AUTH_BEARER_TOKEN", "test-token")
    discovery.reset_discovery_rate_limits()
    app.dependency_overrides[get_db] = _fake_empty_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/extraction/trigger",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "property_manager_id": "pm-1",
                    "url": "https://example.com/listing",
                    "html": "<html></html>",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
