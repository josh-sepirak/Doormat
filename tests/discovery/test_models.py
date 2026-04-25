"""Tests for discovery Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from doormat.discovery.models import (
    DiscoveryCandidate,
    DiscoveryResult,
    ValidationResult,
)


class TestDiscoveryCandidate:
    """Tests for DiscoveryCandidate."""

    def test_valid_candidate(self) -> None:
        """A well-formed candidate is accepted."""
        candidate = DiscoveryCandidate(
            name="Acme Property Management",
            website="https://acmepm.com",
            city="San Francisco",
            confidence=0.85,
            source="llm_search",
        )
        assert candidate.name == "Acme Property Management"
        assert candidate.confidence == pytest.approx(0.85)
        assert candidate.source == "llm_search"

    def test_confidence_lower_bound(self) -> None:
        """Confidence below 0 is rejected."""
        with pytest.raises(ValidationError):
            DiscoveryCandidate(
                name="X",
                website="https://x.com",
                city="SF",
                confidence=-0.1,
                source="llm_search",
            )

    def test_confidence_upper_bound(self) -> None:
        """Confidence above 1 is rejected."""
        with pytest.raises(ValidationError):
            DiscoveryCandidate(
                name="X",
                website="https://x.com",
                city="SF",
                confidence=1.5,
                source="llm_search",
            )

    def test_confidence_zero_allowed(self) -> None:
        """Confidence of exactly 0 is allowed."""
        candidate = DiscoveryCandidate(
            name="X",
            website="https://x.com",
            city="SF",
            confidence=0.0,
            source="browser",
        )
        assert candidate.confidence == 0.0

    def test_confidence_one_allowed(self) -> None:
        """Confidence of exactly 1 is allowed."""
        candidate = DiscoveryCandidate(
            name="X",
            website="https://x.com",
            city="SF",
            confidence=1.0,
            source="browser",
        )
        assert candidate.confidence == 1.0

    def test_unknown_source_rejected(self) -> None:
        """Unknown source values are rejected."""
        with pytest.raises(ValidationError):
            DiscoveryCandidate(
                name="X",
                website="https://x.com",
                city="SF",
                confidence=0.5,
                source="random_source",
            )


class TestValidationResult:
    """Tests for ValidationResult."""

    def test_valid_result(self) -> None:
        """A well-formed validation result is accepted."""
        result = ValidationResult(is_valid=True, reason="Has rental listings", confidence=0.9)
        assert result.is_valid is True
        assert result.reason == "Has rental listings"

    def test_confidence_validated(self) -> None:
        """Confidence outside [0, 1] is rejected."""
        with pytest.raises(ValidationError):
            ValidationResult(is_valid=False, reason="spam", confidence=2.0)


class TestDiscoveryResult:
    """Tests for DiscoveryResult."""

    def test_serializes_correctly(self) -> None:
        """DiscoveryResult round-trips via model_dump."""
        result = DiscoveryResult(
            city="Austin",
            candidates_found=12,
            validated_count=7,
            cached=False,
            cost_usd=0.0285,
            duration_seconds=14.2,
        )
        dumped = result.model_dump()
        assert dumped["city"] == "Austin"
        assert dumped["candidates_found"] == 12
        assert dumped["validated_count"] == 7
        assert dumped["cached"] is False
        assert dumped["cost_usd"] == pytest.approx(0.0285)
        assert dumped["duration_seconds"] == pytest.approx(14.2)

    def test_negative_cost_rejected(self) -> None:
        """Negative cost values are rejected."""
        with pytest.raises(ValidationError):
            DiscoveryResult(
                city="Austin",
                candidates_found=1,
                validated_count=0,
                cached=False,
                cost_usd=-0.01,
                duration_seconds=1.0,
            )

    def test_negative_counts_rejected(self) -> None:
        """Negative counts are rejected."""
        with pytest.raises(ValidationError):
            DiscoveryResult(
                city="Austin",
                candidates_found=-1,
                validated_count=0,
                cached=False,
                cost_usd=0.0,
                duration_seconds=1.0,
            )
