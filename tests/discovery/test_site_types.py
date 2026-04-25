"""Site-shape simulation tests covering 5+ structural types.

These tests don't actually visit the network - they exercise the classifier with
representative candidate inputs that mimic the *result* of inspecting these
site shapes (server-rendered HTML, JS-only SPA, paginated index, aggregator,
parked domain). The LLM is mocked to mirror the classification we'd expect
given a real fetch of each shape.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from doormat.discovery.classifier import PropertyManagerClassifier
from doormat.discovery.models import DiscoveryCandidate, ValidationResult


def _candidate(name: str, website: str) -> DiscoveryCandidate:
    return DiscoveryCandidate(
        name=name, website=website, city="San Francisco", confidence=0.7, source="llm_search"
    )


def _stub_with(result: ValidationResult) -> Any:
    stub = AsyncMock()
    stub.complete = AsyncMock(return_value=result)
    return stub


@pytest.mark.asyncio
async def test_server_rendered_html_site_validates() -> None:
    """A traditional server-rendered HTML PM site validates as a real PM."""
    stub = _stub_with(
        ValidationResult(is_valid=True, reason="server-rendered listings present", confidence=0.92)
    )
    classifier = PropertyManagerClassifier(llm=stub)
    res = await classifier.classify(_candidate("Server Rendered PM", "https://serverpm.com"))
    assert res.is_valid is True


@pytest.mark.asyncio
async def test_js_spa_site_validates_with_lower_confidence() -> None:
    """A JS-only SPA PM site can validate but typically with lower confidence."""
    stub = _stub_with(
        ValidationResult(is_valid=True, reason="SPA - signals via meta/og tags", confidence=0.7)
    )
    classifier = PropertyManagerClassifier(llm=stub)
    res = await classifier.classify(_candidate("Spa PM", "https://spapm.com"))
    assert res.is_valid is True
    assert res.confidence < 0.85


@pytest.mark.asyncio
async def test_paginated_index_site_validates() -> None:
    """A paginated listings index counts as a valid PM site."""
    stub = _stub_with(
        ValidationResult(is_valid=True, reason="paginated rentals index detected", confidence=0.88)
    )
    classifier = PropertyManagerClassifier(llm=stub)
    res = await classifier.classify(_candidate("Paginated PM", "https://pagedpm.com"))
    assert res.is_valid is True


@pytest.mark.asyncio
async def test_aggregator_site_rejected() -> None:
    """Aggregators (Zillow-like) should not classify as a PM."""
    stub = _stub_with(
        ValidationResult(is_valid=False, reason="aggregator/marketplace, not a PM", confidence=0.95)
    )
    classifier = PropertyManagerClassifier(llm=stub)
    res = await classifier.classify(_candidate("Big Aggregator", "https://aggregator.example"))
    assert res.is_valid is False


@pytest.mark.asyncio
async def test_parked_domain_rejected() -> None:
    """A parked / placeholder domain is rejected."""
    stub = _stub_with(
        ValidationResult(is_valid=False, reason="parked domain placeholder", confidence=0.97)
    )
    classifier = PropertyManagerClassifier(llm=stub)
    res = await classifier.classify(_candidate("Parked", "https://parked.example"))
    assert res.is_valid is False


@pytest.mark.asyncio
async def test_directory_site_rejected() -> None:
    """A directory-only site (no live listings) is rejected."""
    stub = _stub_with(
        ValidationResult(is_valid=False, reason="directory only, no live listings", confidence=0.9)
    )
    classifier = PropertyManagerClassifier(llm=stub)
    res = await classifier.classify(_candidate("PM Directory", "https://pmdir.example"))
    assert res.is_valid is False
