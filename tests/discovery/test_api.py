"""Tests for discovery API boundary behavior."""

from fastapi.testclient import TestClient

from doormat.api.routers import discovery
from doormat.config import settings
from doormat.db.base import get_db
from doormat.discovery.models import DiscoveryResult
from doormat.main import app


async def _fake_db():
    yield object()


class _FakeDiscoveryAgent:
    def __init__(self, session):
        self.session = session

    async def discover_city(self, city: str, preference_id: str | None = None) -> DiscoveryResult:
        return DiscoveryResult(
            city=city,
            candidates_found=0,
            validated_count=0,
            cached=False,
            cost_usd=0.0,
            duration_seconds=0.0,
        )


def test_trigger_discovery_requires_bearer_when_configured(monkeypatch):
    """Configured bearer auth must block unauthenticated expensive discovery runs."""
    monkeypatch.setattr(settings, "AUTH_BEARER_TOKEN", "test-token")
    discovery.reset_discovery_rate_limits()

    with TestClient(app) as client:
        response = client.post("/api/discovery/cities/Seattle")

    assert response.status_code == 401


def test_trigger_discovery_rejects_after_rate_limit(monkeypatch):
    """Discovery trigger should rate-limit clients before expensive LLM work."""
    monkeypatch.setattr(settings, "AUTH_BEARER_TOKEN", "test-token")
    monkeypatch.setattr(settings, "DISCOVERY_RATE_LIMIT_PER_MINUTE", 1)
    monkeypatch.setattr(discovery, "DiscoveryAgent", _FakeDiscoveryAgent)
    app.dependency_overrides[get_db] = _fake_db
    discovery.reset_discovery_rate_limits()

    headers = {"Authorization": "Bearer test-token"}
    try:
        with TestClient(app) as client:
            first = client.post("/api/discovery/cities/Austin", headers=headers)
            second = client.post("/api/discovery/cities/Boston", headers=headers)
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 429
