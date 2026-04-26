"""Tests for preference API endpoints used by the frontend."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

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


def test_list_preferences_returns_saved_preferences():
    app.dependency_overrides[get_db] = _fake_db_for_list([make_preference()])

    try:
        with TestClient(app) as client:
            resp = client.get("/api/preferences")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()[0]["city"] == "Austin"


def test_create_preference_persists_and_returns_model():
    app.dependency_overrides[get_db] = _fake_db_for_one(None)

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/preferences",
                json={"city": "Austin", "description": "2BR pet-friendly under $2000"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201
    assert resp.json()["description"] == "2BR pet-friendly under $2000"


def test_delete_preference_returns_404_when_missing():
    app.dependency_overrides[get_db] = _fake_db_for_one(None)

    try:
        with TestClient(app) as client:
            resp = client.delete("/api/preferences/missing")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
