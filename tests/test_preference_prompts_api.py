"""Tests for GET/PATCH /api/preferences/{id}/prompts."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from doormat.db.base import get_db
from doormat.main import app
from doormat.models.orm import Preference


def _fake_db_pref(pref: Preference | None) -> callable:
    async def _dep():
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = pref
        session = AsyncMock()
        session.execute = AsyncMock(return_value=exec_result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        yield session

    return _dep


def _make_pref() -> Preference:
    now = datetime.now(UTC)
    return Preference(
        id="pref-prompts-1",
        description="x" * 15,
        city="Austin",
        prompt_overrides=None,
        created_at=now,
        updated_at=now,
    )


def test_get_preference_prompts_returns_catalog():
    pref = _make_pref()
    app.dependency_overrides[get_db] = _fake_db_pref(pref)
    try:
        with TestClient(app) as client:
            r = client.get("/api/preferences/pref-prompts-1/prompts")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    data = r.json()
    assert "prompts" in data
    assert len(data["prompts"]) >= 1
    keys = {p["key"] for p in data["prompts"]}
    assert "scoring_system" in keys
    first = data["prompts"][0]
    assert "default_text" in first and "effective_text" in first
    assert first["is_custom"] is False


def test_patch_preference_prompts_reset_all():
    pref = _make_pref()
    pref.prompt_overrides = {"scoring_system": "custom override for scoring prompt text"}
    app.dependency_overrides[get_db] = _fake_db_pref(pref)
    try:
        with TestClient(app) as client:
            r = client.patch(
                "/api/preferences/pref-prompts-1/prompts",
                json={"reset_all": True},
            )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    scoring = next(p for p in r.json()["prompts"] if p["key"] == "scoring_system")
    assert scoring["is_custom"] is False
