"""Tests for PropertyManagerClassifier."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from doormat.discovery.classifier import PropertyManagerClassifier
from doormat.discovery.models import DiscoveryCandidate, ValidationResult


def make_candidate(**overrides: Any) -> DiscoveryCandidate:
    """Build a default candidate with optional overrides."""
    base: dict[str, Any] = {
        "name": "Acme Property Management",
        "website": "https://acmepm.com",
        "city": "San Francisco",
        "confidence": 0.8,
        "source": "llm_search",
    }
    base.update(overrides)
    return DiscoveryCandidate(**base)


class _StubLLM:
    """Stub LLM client that returns a queued ValidationResult or raises."""

    def __init__(self, response: ValidationResult | Exception) -> None:
        self._response = response
        self.complete = AsyncMock(side_effect=self._side_effect)

    async def _side_effect(self, *args: Any, **kwargs: Any) -> ValidationResult:
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


@pytest.mark.asyncio
async def test_classify_valid_pm_site() -> None:
    """A legitimate PM site is returned as is_valid=True."""
    stub = _StubLLM(
        ValidationResult(is_valid=True, reason="Active rental listings found", confidence=0.95)
    )
    classifier = PropertyManagerClassifier(llm=stub)  # type: ignore[arg-type]

    result = await classifier.classify(make_candidate())

    assert result.is_valid is True
    assert result.confidence == pytest.approx(0.95)
    stub.complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_classify_spam_site() -> None:
    """A spam-flagged site returns is_valid=False."""
    stub = _StubLLM(
        ValidationResult(
            is_valid=False,
            reason="Site appears to be a parked domain / spam",
            confidence=0.9,
        )
    )
    classifier = PropertyManagerClassifier(llm=stub)  # type: ignore[arg-type]

    result = await classifier.classify(make_candidate(name="Spam Co"))

    assert result.is_valid is False
    assert "spam" in result.reason.lower() or "parked" in result.reason.lower()


@pytest.mark.asyncio
async def test_classify_llm_error_returns_invalid() -> None:
    """When the LLM raises, the classifier returns is_valid=False gracefully."""
    stub = _StubLLM(RuntimeError("openrouter unavailable"))
    classifier = PropertyManagerClassifier(llm=stub)  # type: ignore[arg-type]

    result = await classifier.classify(make_candidate())

    assert result.is_valid is False
    assert result.confidence == 0.0
    assert "classification_error" in result.reason
