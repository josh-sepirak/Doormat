"""Tests for OpenRouter model proxy endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
from fastapi.testclient import TestClient

from doormat.config import settings
from doormat.cost_tracking import get_cost_tracker
from doormat.db.base import get_db
from doormat.main import app
from doormat.models.orm import Preference


class _FakeResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "data": [
                {
                    "id": "openai/gpt-4o-mini",
                    "name": "GPT-4o mini",
                    "context_length": 128000,
                    "pricing": {"prompt": "0.00000015", "completion": "0.0000006"},
                }
            ]
        }


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url: str, headers: dict[str, str]):
        assert headers["Authorization"] == "Bearer test-openrouter-secret"
        return _FakeResponse()


async def _fake_db():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    yield session


async def _fake_db_with_preference():
    session = AsyncMock()
    session.get = AsyncMock(
        return_value=Preference(
            id="pref-1",
            description="2BR under $2000",
            city="Austin",
            openrouter_api_key="test-openrouter-secret",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    yield session


def test_models_endpoint_uses_post_body_not_query_string(monkeypatch):
    """OpenRouter keys should not travel in URL query strings."""
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    app.dependency_overrides[get_db] = _fake_db

    try:
        with TestClient(app) as client:
            get_resp = client.get("/api/openrouter/models?key=test-openrouter-secret")
            post_resp = client.post(
                "/api/openrouter/models", json={"key": "test-openrouter-secret"}
            )
    finally:
        app.dependency_overrides.clear()

    assert get_resp.status_code == 405
    assert post_resp.status_code == 200
    assert post_resp.json()[0]["id"] == "openai/gpt-4o-mini"


def test_models_endpoint_can_use_stored_preference_key(monkeypatch):
    """Existing users can load models without echoing the stored key to the browser."""
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    app.dependency_overrides[get_db] = _fake_db_with_preference

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/openrouter/models",
                json={"preference_id": "pref-1", "curated": False},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "GPT-4o mini"


def test_models_endpoint_does_not_create_cost_records(monkeypatch):
    """Model-catalog fetches are metadata calls, not billable LLM completions."""
    monkeypatch.setattr(settings, "TRACK_COSTS", False)
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    get_cost_tracker().clear()
    app.dependency_overrides[get_db] = _fake_db

    try:
        with TestClient(app) as client:
            resp = client.post("/api/openrouter/models", json={"key": "test-openrouter-secret"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert get_cost_tracker().records == []
    get_cost_tracker().clear()


def test_models_endpoint_requires_a_key_or_preference():
    app.dependency_overrides[get_db] = _fake_db

    try:
        with TestClient(app) as client:
            resp = client.post("/api/openrouter/models", json={})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400


def test_models_endpoint_requires_bearer_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_BEARER_TOKEN", "test-token")
    app.dependency_overrides[get_db] = _fake_db

    try:
        with TestClient(app) as client:
            missing = client.post("/api/openrouter/models", json={"key": "test-openrouter-secret"})
            allowed = client.post(
                "/api/openrouter/models",
                json={},
                headers={"Authorization": "Bearer test-token"},
            )
    finally:
        app.dependency_overrides.clear()

    assert missing.status_code == 401
    assert allowed.status_code == 400
