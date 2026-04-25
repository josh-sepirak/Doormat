"""Tests for BrowserDiscovery graceful degradation."""

from __future__ import annotations

import pytest

from doormat.discovery.browser import BrowserDiscovery


@pytest.mark.asyncio
async def test_discover_returns_empty_when_unavailable() -> None:
    """When browser-use is unavailable, discover() returns []."""
    bd = BrowserDiscovery(available=False)
    out = await bd.discover("San Francisco")
    assert out == []


@pytest.mark.asyncio
async def test_discover_returns_empty_when_runtime_missing() -> None:
    """Even when import succeeded, no real browser runtime returns []."""
    bd = BrowserDiscovery(available=True)
    out = await bd.discover("Austin")
    # Without a chromium runtime in tests, returns empty list, not raises.
    assert out == []
