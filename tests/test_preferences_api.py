"""Tests for preference API endpoints used by the frontend."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from doormat.config import settings
from doormat.db.base import get_db
from doormat.main import app
from doormat.models.orm import Preference


def make_preference(preference_id: str = "pref-1") -> Preference:
    return Preference(
        id=preference_id,
        description="2BR pet-friendly apartment under $2000",
        city="Austin",
        api_provider="openrouter",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _fake_db_for_list(rows: list[Preference]) -> callable:
    async def _dep():
        exec_result = MagicMock()
        exec_result.scalars.return_value.all.return_value = rows
        session = AsyncMock()
        session.execute = AsyncMock(return_value=exec_result)
        yield session

    return _dep


def _fake_db_for_one(row: Preference | None) -> callable:
    async def _dep():
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = row
        session = AsyncMock()
        session.execute = AsyncMock(return_value=exec_result)
        session.commit = AsyncMock()
        session.delete = AsyncMock()
        session.add = MagicMock()
        yield session

    return _dep


def test_list_preferences_returns_saved_preferences(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "test-secret-key")
    preference = make_preference()
    preference.openrouter_api_key = "test-openrouter-key1234"
    preference.apify_api_token = "apify_secret5678"
    app.dependency_overrides[get_db] = _fake_db_for_list([preference])

    try:
        with TestClient(app) as client:
            resp = client.get("/api/preferences")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()[0]
    assert data["city"] == "Austin"
    assert data["has_openrouter_api_key"] is True
    assert data["openrouter_key_last4"] == "1234"
    assert data["has_apify_api_token"] is True
    assert data["apify_token_last4"] == "5678"
    assert "openrouter_api_key" not in data
    assert "apify_api_token" not in data


def test_create_preference_persists_and_returns_model(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "test-secret-key")
    app.dependency_overrides[get_db] = _fake_db_for_one(None)

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/preferences",
                json={
                    "city": "Austin",
                    "description": "2BR pet-friendly under $2000",
                    "openrouter_api_key": "test-openrouter-key",
                    "fast_model": "openai/gpt-4o-mini",
                    "smart_model": "anthropic/claude-3.5-sonnet",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201
    data = resp.json()
    assert data["description"] == "2BR pet-friendly under $2000"
    assert data["has_openrouter_api_key"] is True
    assert data["openrouter_key_last4"] == "-key"
    assert "openrouter_api_key" not in data
    assert data["fast_model"] == "openai/gpt-4o-mini"
    assert data["smart_model"] == "anthropic/claude-3.5-sonnet"


def test_update_preference_persists_selected_models():
    preference = make_preference()
    app.dependency_overrides[get_db] = _fake_db_for_one(preference)

    try:
        with TestClient(app) as client:
            resp = client.patch(
                "/api/preferences/pref-1",
                json={
                    "fast_model": "openai/gpt-4o-mini",
                    "smart_model": "anthropic/claude-3.5-sonnet",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert preference.fast_model == "openai/gpt-4o-mini"
    assert preference.smart_model == "anthropic/claude-3.5-sonnet"


def test_preferences_require_bearer_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_BEARER_TOKEN", "test-token")
    app.dependency_overrides[get_db] = _fake_db_for_list([])

    try:
        with TestClient(app) as client:
            missing = client.get("/api/preferences")
            allowed = client.get(
                "/api/preferences", headers={"Authorization": "Bearer test-token"}
            )
    finally:
        app.dependency_overrides.clear()

    assert missing.status_code == 401
    assert allowed.status_code == 200


def test_update_preference_can_clear_stored_secrets():
    preference = make_preference()
    preference.openrouter_api_key = "test-openrouter-key"
    preference.apify_api_token = "test-apify-token"
    app.dependency_overrides[get_db] = _fake_db_for_one(preference)

    try:
        with TestClient(app) as client:
            resp = client.patch(
                "/api/preferences/pref-1",
                json={"openrouter_api_key": None, "apify_api_token": None},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert preference.openrouter_api_key is None
    assert preference.apify_api_token is None


def test_delete_preference_returns_404_when_missing():
    app.dependency_overrides[get_db] = _fake_db_for_one(None)

    try:
        with TestClient(app) as client:
            resp = client.delete("/api/preferences/missing")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
