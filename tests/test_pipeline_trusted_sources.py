"""Pipeline uses trusted Craigslist regions when configured."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from doormat.models.orm import TrustedSource
from doormat.runs import events as run_events
from doormat.runs.pipeline import _scrape_craigslist


class _FakeListing:
    def __init__(self, url: str, price: float = 500.0):
        self.url = url
        self.price = price
        self.title = "t"
        self.neighborhood = "n"
        self.address = "a"
        self.bedrooms = 2


@pytest.mark.asyncio
async def test_scrape_craigslist_calls_trusted_subdomain(monkeypatch):
    ts = TrustedSource(
        id="ts1",
        kind="craigslist_region",
        label="IE",
        url="https://inlandempire.craigslist.org",
        city="Lancaster, CA",
        linked_property_manager_id=None,
        created_at=datetime.now(UTC),
    )

    exec_trusted = MagicMock()
    exec_trusted.scalars.return_value.all.return_value = [ts]

    exec_empty = MagicMock()
    exec_empty.scalar_one_or_none.return_value = None

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[exec_trusted, exec_empty, exec_empty, exec_empty])
    session.get = AsyncMock(return_value=SimpleNamespace(id="sr1", extraction_attempts=0, listings_seen=0))
    session.commit = AsyncMock()
    session.add = MagicMock()

    calls: list[str | None] = []

    async def _fake_fetch(city, max_results=30, timeout=20.0, subdomain=None):
        calls.append(subdomain)
        return [_FakeListing("https://inlandempire.craigslist.org/x/1.html")]

    async def _fake_get_pm(*_a, **_k):
        return SimpleNamespace(id="pm-cl")

    monkeypatch.setattr(
        "doormat.sources.craigslist.fetch_craigslist_listings",
        _fake_fetch,
        raising=False,
    )
    monkeypatch.setattr(
        "doormat.runs.pipeline._get_or_create_source_pm",
        _fake_get_pm,
        raising=False,
    )

    emitter = AsyncMock(spec=run_events.SearchRunEventEmitter)
    emitter.emit = AsyncMock()

    await _scrape_craigslist(
        session,
        SimpleNamespace(id="sr1"),
        "Lancaster, CA",
        None,
        emitter,
    )

    assert calls and calls[0] == "inlandempire"
    warn_messages = [c.args[1] for c in emitter.emit.call_args_list if c.args[0] == "warning"]
    assert not any("Auto-routed Craigslist" in str(m) for m in warn_messages)


@pytest.mark.asyncio
async def test_scrape_craigslist_auto_warning_when_no_trusted(monkeypatch):
    exec_trusted = MagicMock()
    exec_trusted.scalars.return_value.all.return_value = []

    exec_empty = MagicMock()
    exec_empty.scalar_one_or_none.return_value = None

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[exec_trusted, exec_empty, exec_empty, exec_empty])
    session.get = AsyncMock(return_value=SimpleNamespace(id="sr1", extraction_attempts=0, listings_seen=0))
    session.commit = AsyncMock()
    session.add = MagicMock()

    async def _fake_fetch(city, max_results=30, timeout=20.0, subdomain=None):
        return [_FakeListing("https://lancaster.craigslist.org/x/1.html")]

    async def _fake_get_pm(*_a, **_k):
        return SimpleNamespace(id="pm-cl")

    monkeypatch.setattr(
        "doormat.sources.craigslist.fetch_craigslist_listings",
        _fake_fetch,
        raising=False,
    )
    monkeypatch.setattr("doormat.runs.pipeline._get_or_create_source_pm", _fake_get_pm, raising=False)

    emitter = AsyncMock(spec=run_events.SearchRunEventEmitter)
    emitter.emit = AsyncMock()

    await _scrape_craigslist(
        session,
        SimpleNamespace(id="sr1"),
        "Lancaster",
        None,
        emitter,
    )

    warn_messages = [c.args[1] for c in emitter.emit.call_args_list if c.args[0] == "warning"]
    assert any("Auto-routed Craigslist" in str(m) for m in warn_messages)
