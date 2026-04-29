"""Bridge tests: discovery logs mirrored to search run events (T017, T042)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from doormat.api.routers import discovery as discovery_router
from doormat.config import settings
from doormat.db.base import AsyncSessionLocal
from doormat.discovery import agent as agent_mod
from doormat.discovery.models import DiscoveryResult
from doormat.main import app
from doormat.models.orm import SearchRunEvent


@pytest.fixture(autouse=True)
def _no_auth(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_BEARER_TOKEN", "")
    discovery_router.reset_discovery_rate_limits()


async def _chatty_discover(
    self,
    city: str,
    preference_id: str | None = None,
    run_logger=None,
    cancel_check=None,
) -> DiscoveryResult:
    if run_logger:
        await run_logger.info("bridge-line-1", component="discovery")
        await run_logger.success("bridge-line-2", component="discovery")
    return DiscoveryResult(
        city=city,
        candidates_found=1,
        validated_count=1,
        cached=False,
        cost_usd=0.0,
        duration_seconds=0.01,
    )


@pytest.mark.asyncio
async def test_bridge_writes_search_run_events(monkeypatch):
    monkeypatch.setattr(agent_mod.DiscoveryAgent, "discover_city", _chatty_discover)
    with TestClient(app) as client:
        created = client.post("/api/search-runs", json={"city": "Phoenix"})
        rid = created.json()["id"]

    async with AsyncSessionLocal() as session:
        count = (
            await session.execute(
                select(func.count()).select_from(SearchRunEvent).where(SearchRunEvent.run_id == rid)
            )
        ).scalar_one()
        assert int(count) >= 2
