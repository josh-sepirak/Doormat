"""API tests for search runs (T007, T016, T030, T041, T052, T071)."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from doormat.api.routers import discovery as discovery_router
from doormat.config import settings
from doormat.discovery import agent as agent_mod
from doormat.discovery.models import DiscoveryResult
from doormat.main import app
from doormat.schemas import SearchRunResponse


@pytest.fixture(autouse=True)
def _no_auth(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_BEARER_TOKEN", "")
    discovery_router.reset_discovery_rate_limits()


async def _fake_discover_city(
    self,
    city: str,
    preference_id: str | None = None,
    run_logger=None,
    cancel_check=None,
) -> DiscoveryResult:
    if run_logger:
        await run_logger.info(
            "synthetic progress",
            component="discovery",
            event_type="stage_progress",
        )
    return DiscoveryResult(
        city=city,
        candidates_found=0,
        validated_count=0,
        cached=False,
        cost_usd=0.0,
        duration_seconds=0.01,
    )


def test_search_run_response_schema_serializes():
    """T007: response schema accepts the public JSON shape."""
    payload = {
        "id": "sr1",
        "discovery_run_id": "dr1",
        "city": "Austin",
        "preference_id": None,
        "status": "running",
        "current_stage": "discovery",
        "cancel_requested": False,
        "sources_checked": 0,
        "managers_validated": 0,
        "listings_seen": 0,
        "great_matches": 0,
        "worth_a_look": 0,
        "near_misses": 0,
        "filtered_out": 0,
        "cost_usd_so_far": 0.0,
        "active_revision": 1,
        "started_at": datetime.now(UTC).isoformat(),
        "finished_at": None,
        "filter_summary": {},
        "suggestions": [],
        "suggestions_early_signal": True,
    }
    m = SearchRunResponse.model_validate(payload)
    assert m.city == "Austin"


def test_create_active_detail_events_stop_results_filters(monkeypatch):
    monkeypatch.setattr(agent_mod.DiscoveryAgent, "discover_city", _fake_discover_city)
    with TestClient(app) as client:
        created = client.post("/api/search-runs", json={"city": "Tucson"})
        assert created.status_code == 200
        body = created.json()
        rid = body["id"]
        assert body["discovery_run_id"]
        assert SearchRunResponse.model_validate(body).id == rid

        detail = client.get(f"/api/search-runs/{rid}")
        assert detail.status_code == 200
        assert detail.json()["id"] == rid

        active = client.get("/api/search-runs/active")
        assert active.status_code == 200
        env = active.json()
        if env["active"]:
            assert env["run"]["id"] == rid

        ev = client.get(f"/api/search-runs/{rid}/events?after_sequence=-1&limit=50")
        assert ev.status_code == 200
        assert isinstance(ev.json(), list)

        ev_user = client.get(f"/api/search-runs/{rid}/events?visibility=user")
        assert ev_user.status_code == 200

        stop = client.post(f"/api/search-runs/{rid}/stop")
        assert stop.status_code == 200
        stop2 = client.post(f"/api/search-runs/{rid}/stop")
        assert stop2.status_code == 200

        res = client.get(f"/api/search-runs/{rid}/results?category=great_match")
        assert res.status_code == 200
        assert res.json() == []


def test_patch_filters_rejects_next_run_city_schema():
    """T071: next-run-only fields are rejected at validation time."""
    from pydantic import ValidationError

    from doormat.schemas import SearchRunFiltersPatch

    with pytest.raises(ValidationError):
        SearchRunFiltersPatch(next_run_city="Boulder")
