"""Tests for DiscoveryAgent orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from doormat.cost_tracking import CostRecord, get_cost_tracker
from doormat.discovery.agent import DiscoveryAgent
from doormat.discovery.models import DiscoveryCandidate, ValidationResult
from doormat.models.orm import PropertyManager

# Helpers --------------------------------------------------------------------


def make_candidate(name: str, website: str, city: str = "San Francisco") -> DiscoveryCandidate:
    """Build a DiscoveryCandidate quickly."""
    return DiscoveryCandidate(
        name=name,
        website=website,
        city=city,
        confidence=0.8,
        source="llm_search",
    )


def _scalar_result(rows: list[Any]) -> Any:
    """Build a fake SQLAlchemy execute() result that yields `rows` from .scalars().all()."""
    scalars = MagicMock()
    scalars.all.return_value = rows
    exec_result = MagicMock()
    exec_result.scalars.return_value = scalars
    return exec_result


def make_session(cached_pm_rows: list[PropertyManager] | None = None) -> AsyncMock:
    """Build an AsyncSession-like mock with predictable execute()/add()/commit()."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(cached_pm_rows or []))
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


def stub_search(candidates_per_call: list[list[DiscoveryCandidate]]) -> AsyncMock:
    """Stub DiscoverySearch returning `candidates_per_call[i]` on the i-th call."""
    search = AsyncMock()
    search.find_candidates = AsyncMock(side_effect=candidates_per_call)
    return search


def stub_browser(empty_calls: int = 5) -> AsyncMock:
    """Stub BrowserDiscovery that always returns []."""
    browser = AsyncMock()
    browser.discover = AsyncMock(return_value=[])
    return browser


def stub_classifier(results_in_order: list[ValidationResult]) -> AsyncMock:
    """Stub PropertyManagerClassifier returning queued results in order."""
    classifier = AsyncMock()
    classifier.classify = AsyncMock(side_effect=results_in_order)
    return classifier


# Tests ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit_returns_early() -> None:
    """When validated rows already exist for the city, return cached=True early."""
    cached = [
        PropertyManager(
            id="abc",
            city="Austin",
            name="Cached PM",
            website="https://cached.com",
            listing_page_url=None,
            validated=True,
            discovery_timestamp=datetime.now(UTC),
        )
    ]
    session = make_session(cached_pm_rows=cached)
    search = stub_search([])  # should not be called
    browser = stub_browser()
    classifier = stub_classifier([])

    agent = DiscoveryAgent(session=session, search=search, browser=browser, classifier=classifier)

    result = await agent.discover_city("Austin")

    assert result.cached is True
    assert result.validated_count == 1
    assert result.candidates_found == 1
    assert result.cost_usd == 0.0
    search.find_candidates.assert_not_called()
    classifier.classify.assert_not_called()


@pytest.mark.asyncio
async def test_full_flow_search_classify_persist() -> None:
    """End-to-end: search -> classify -> persist -> DiscoveryResult."""
    session = make_session(cached_pm_rows=[])
    cands = [
        make_candidate("Acme PM", "https://acmepm.com"),
        make_candidate("Beta Realty", "https://betarealty.com"),
    ]
    search = stub_search([cands])
    browser = stub_browser()
    classifier = stub_classifier(
        [
            ValidationResult(is_valid=True, reason="legit", confidence=0.9),
            ValidationResult(is_valid=False, reason="parked", confidence=0.8),
        ]
    )

    agent = DiscoveryAgent(session=session, search=search, browser=browser, classifier=classifier)

    result = await agent.discover_city("San Francisco")

    assert result.cached is False
    assert result.candidates_found == 2
    assert result.validated_count == 1
    assert session.add.call_count == 1
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_feedback_loop_retries_on_zero_validated() -> None:
    """When the first attempt yields no validated PMs, retry with a refinement."""
    session = make_session(cached_pm_rows=[])
    first_attempt = [make_candidate("Junk PM", "https://junk.com")]
    second_attempt = [make_candidate("Good PM", "https://goodpm.com")]
    search = stub_search([first_attempt, second_attempt])
    browser = stub_browser()
    classifier = stub_classifier(
        [
            ValidationResult(is_valid=False, reason="spam", confidence=0.9),
            ValidationResult(is_valid=True, reason="legit", confidence=0.95),
        ]
    )

    agent = DiscoveryAgent(session=session, search=search, browser=browser, classifier=classifier)

    result = await agent.discover_city("Seattle")

    assert search.find_candidates.await_count == 2  # initial + 1 retry
    refinement_call = search.find_candidates.await_args_list[1]
    assert refinement_call.kwargs.get("refinement") is not None
    assert result.validated_count == 1


@pytest.mark.asyncio
async def test_cost_tracking_diff_recorded() -> None:
    """When LLM activity occurs, DiscoveryResult.cost_usd reflects tracker diff."""
    tracker = get_cost_tracker()
    tracker.clear()

    session = make_session(cached_pm_rows=[])

    async def classify_side_effect(candidate: DiscoveryCandidate) -> ValidationResult:
        # Simulate LLM call cost via the cost tracker
        tracker.add_record(
            CostRecord(
                service="openrouter",
                model="openai/gpt-4o-mini",
                prompt_tokens=10,
                completion_tokens=10,
                total_tokens=20,
                cost_usd=0.001,
                latency_ms=5.0,
            )
        )
        return ValidationResult(is_valid=True, reason="legit", confidence=0.9)

    cands = [make_candidate("Acme PM", "https://acmepm.com")]
    search = stub_search([cands])
    browser = stub_browser()
    classifier = AsyncMock()
    classifier.classify = AsyncMock(side_effect=classify_side_effect)

    agent = DiscoveryAgent(session=session, search=search, browser=browser, classifier=classifier)

    result = await agent.discover_city("Portland")

    assert result.cost_usd > 0
    assert result.validated_count == 1
    tracker.clear()


@pytest.mark.asyncio
async def test_max_retries_respected() -> None:
    """Agent stops after MAX_RETRIES+1 attempts even with 0 validated."""
    session = make_session(cached_pm_rows=[])
    # Provide enough attempt-lists to satisfy any number of retries
    attempts = [[make_candidate(f"Junk{i}", f"https://j{i}.com")] for i in range(5)]
    search = stub_search(attempts)
    browser = stub_browser()
    # Always fail validation
    classifier = AsyncMock()
    classifier.classify = AsyncMock(
        return_value=ValidationResult(is_valid=False, reason="spam", confidence=0.5)
    )

    agent = DiscoveryAgent(session=session, search=search, browser=browser, classifier=classifier)

    result = await agent.discover_city("Boston")

    # 1 initial + 2 retries = 3 attempts total
    assert search.find_candidates.await_count == 3
    assert result.validated_count == 0
    session.add.assert_not_called()
