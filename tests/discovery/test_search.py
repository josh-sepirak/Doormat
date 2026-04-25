"""Tests for DiscoverySearch."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from doormat.discovery.models import DiscoveryCandidate
from doormat.discovery.search import (
    DiscoverySearch,
    _SearchCandidate,
    _SearchResponse,
    _dedupe_by_domain,
    _normalize_host,
)


class _StubLLM:
    """Stub LLM client whose `complete` returns a fixed response."""

    def __init__(self, response: _SearchResponse | Exception) -> None:
        self._response = response
        self.complete = AsyncMock(side_effect=self._side_effect)

    async def _side_effect(self, *args: Any, **kwargs: Any) -> _SearchResponse:
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


@pytest.mark.asyncio
async def test_find_candidates_returns_list() -> None:
    """Search returns a list of DiscoveryCandidate objects with city set."""
    payload = _SearchResponse(
        candidates=[
            _SearchCandidate(name="Acme PM", website="https://acmepm.com", confidence=0.9),
            _SearchCandidate(name="Beta Realty", website="https://betarealty.com", confidence=0.7),
        ]
    )
    stub = _StubLLM(payload)
    search = DiscoverySearch(llm=stub)  # type: ignore[arg-type]

    candidates = await search.find_candidates("San Francisco")

    assert len(candidates) == 2
    assert all(isinstance(c, DiscoveryCandidate) for c in candidates)
    assert all(c.city == "San Francisco" for c in candidates)
    assert all(c.source == "llm_search" for c in candidates)


@pytest.mark.asyncio
async def test_find_candidates_handles_empty_response() -> None:
    """An empty LLM response yields an empty list, not an error."""
    stub = _StubLLM(_SearchResponse(candidates=[]))
    search = DiscoverySearch(llm=stub)  # type: ignore[arg-type]

    candidates = await search.find_candidates("Nowhere, USA")

    assert candidates == []


@pytest.mark.asyncio
async def test_find_candidates_dedupes_websites() -> None:
    """Duplicate websites are collapsed via host-based dedup."""
    payload = _SearchResponse(
        candidates=[
            _SearchCandidate(name="Acme PM", website="https://acmepm.com", confidence=0.9),
            _SearchCandidate(name="Acme PM Inc", website="https://www.acmepm.com", confidence=0.6),
            _SearchCandidate(name="Beta Realty", website="https://betarealty.com", confidence=0.5),
        ]
    )
    stub = _StubLLM(payload)
    search = DiscoverySearch(llm=stub)  # type: ignore[arg-type]

    candidates = await search.find_candidates("Austin")

    assert len(candidates) == 2
    hosts = {_normalize_host(c.website) for c in candidates}
    assert hosts == {"acmepm.com", "betarealty.com"}


@pytest.mark.asyncio
async def test_find_candidates_returns_empty_on_llm_error() -> None:
    """When the LLM raises, search degrades gracefully to []."""
    stub = _StubLLM(RuntimeError("openrouter down"))
    search = DiscoverySearch(llm=stub)  # type: ignore[arg-type]

    candidates = await search.find_candidates("Seattle")

    assert candidates == []


def test_dedupe_by_domain_unit() -> None:
    """The dedupe helper collapses by registrable host."""
    cands = [
        DiscoveryCandidate(
            name="A", website="https://acme.com", city="X", confidence=0.5, source="llm_search"
        ),
        DiscoveryCandidate(
            name="A2", website="https://www.acme.com", city="X", confidence=0.6, source="llm_search"
        ),
        DiscoveryCandidate(
            name="B", website="https://beta.com", city="X", confidence=0.4, source="llm_search"
        ),
    ]
    out = _dedupe_by_domain(cands)
    assert len(out) == 2
    names = {c.name for c in out}
    assert names == {"A", "B"}
