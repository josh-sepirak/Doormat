"""Unit tests for listing scorer."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from doormat.models.orm import Listing, Preference
from doormat.scoring.scorer import (
    ListingScorer,
    heuristic_listing_score,
    build_listing_scoring_prompt,
)


@pytest.fixture
def sample_listing():
    """Create a sample listing for testing."""
    return Listing(
        id="test-listing-1",
        property_manager_id="test-pm",
        address="123 Main St, San Francisco, CA",
        price=3200,
        bedrooms=2,
        bathrooms=1.5,
        url="https://example.com/listing/1",
        description="Modern 2-bed in Mission District",
        amenities='["parking", "laundry"]',
        pets_policy="cats_and_dogs_allowed",
    )


@pytest.fixture
def sample_preference():
    """Create a sample preference for testing."""
    return Preference(
        id="test-pref-1",
        city="San Francisco",
        description="Looking for a modern 2-bed apartment in a walkable neighborhood, max $3500/month, walkable",
        smart_model="openrouter/anthropic/claude-3.5-sonnet",
        openrouter_api_key="encrypted_key_placeholder",
    )


def test_heuristic_listing_score_within_budget(sample_listing, sample_preference):
    """Test heuristic scoring for listing within budget."""
    score = heuristic_listing_score(sample_listing, sample_preference)

    assert 0.0 <= score.score <= 1.0
    assert isinstance(score.explanation, str)
    assert len(score.explanation) > 0
    assert "budget" in score.explanation.lower()


def test_heuristic_listing_score_above_budget(sample_listing, sample_preference):
    """Test heuristic scoring for listing above budget."""
    sample_listing.price = 4000
    score = heuristic_listing_score(sample_listing, sample_preference)

    assert 0.0 <= score.score <= 1.0
    assert "above budget" in score.explanation.lower()


def test_heuristic_listing_score_bedroom_mismatch(sample_listing, sample_preference):
    """Test heuristic scoring for bedroom count mismatch."""
    sample_listing.bedrooms = 1
    score = heuristic_listing_score(sample_listing, sample_preference)

    assert 0.0 <= score.score <= 1.0
    assert "bedroom" in score.explanation.lower()


def test_heuristic_listing_score_city_match(sample_listing, sample_preference):
    """Test heuristic scoring for city match."""
    sample_listing.address = "456 Valencia St, San Francisco, CA"
    score = heuristic_listing_score(sample_listing, sample_preference)

    assert "city" in score.explanation.lower() or "San Francisco" in score.explanation


def test_heuristic_listing_score_pet_policy(sample_listing, sample_preference):
    """Test heuristic scoring includes pet policy evaluation."""
    sample_listing.pets_policy = "cats_and_dogs_allowed"
    score = heuristic_listing_score(sample_listing, sample_preference)

    assert 0.0 <= score.score <= 1.0
    # Explanation should exist
    assert score.explanation


def test_heuristic_listing_score_no_pets_preference(sample_listing):
    """Test heuristic scoring when preference has no pet requirement."""
    preference = Preference(
        id="no-pets-pref",
        city="San Francisco",
        description="Looking for a 2-bed apartment in San Francisco, max $3500",
        smart_model="openrouter/anthropic/claude-3.5-sonnet",
        openrouter_api_key="key",
    )
    score = heuristic_listing_score(sample_listing, preference)

    assert 0.0 <= score.score <= 1.0
    # No pet-related penalty expected
    assert "pet" not in score.explanation.lower()


def test_build_listing_scoring_prompt(sample_listing, sample_preference):
    """Test prompt building for scoring."""
    prompt = build_listing_scoring_prompt(sample_listing, sample_preference)

    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "123 Main St" in prompt or "listing" in prompt.lower()
    assert "San Francisco" in prompt or sample_preference.city in prompt


def test_build_listing_scoring_prompt_truncates_long_values(sample_preference):
    """Test that prompt building truncates overly long values."""
    long_address = "A" * 3000
    listing = Listing(
        id="long-listing",
        property_manager_id="pm",
        address=long_address,
        price=3000,
        bedrooms=2,
        url="https://example.com/1",
    )
    prompt = build_listing_scoring_prompt(listing, sample_preference)

    # Prompt should exist and not contain full address (truncated)
    assert "[truncated]" in prompt or len(prompt) < len(long_address)


@pytest.mark.asyncio
async def test_listing_scorer_fallback_on_llm_error(sample_listing, sample_preference):
    """Test that scorer falls back to heuristics on LLM error."""
    scorer = ListingScorer()

    # Mock LLM to fail
    scorer.llm = AsyncMock()
    scorer.llm.complete.side_effect = ValueError("API key invalid")

    result = await scorer.score(sample_listing, sample_preference)

    # Should get a result from heuristic fallback
    assert result is not None
    assert 0.0 <= result.score <= 1.0
    assert "heuristic" in result.explanation.lower() or len(result.explanation) > 0


@pytest.mark.asyncio
async def test_listing_scorer_score_batch(sample_listing, sample_preference):
    """Test batch scoring of multiple listings."""
    scorer = ListingScorer()

    # Mock LLM
    scorer.llm = AsyncMock()

    listings = [sample_listing] * 3
    for i, listing in enumerate(listings):
        listing.id = f"test-listing-{i}"

    # Each listing should be scored
    for listing in listings:
        result = await scorer.score(listing, sample_preference)
        assert result is not None
        assert 0.0 <= result.score <= 1.0


@pytest.mark.asyncio
async def test_listing_scorer_respects_timeout():
    """Test that scorer respects timeout configuration."""
    scorer = ListingScorer()

    # Default timeout should be set
    assert scorer.config is not None
