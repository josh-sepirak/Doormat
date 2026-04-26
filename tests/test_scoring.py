"""Tests for listing scoring module."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from doormat.models.orm import Listing, Preference
from doormat.scoring.scorer import ListingScore, ListingScorer


def make_preference(description: str = "2BR apartment, pet-friendly, under $2000") -> Preference:
    return Preference(
        id="pref-1",
        description=description,
        city="Austin",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def make_listing(
    *,
    price: float = 1500.0,
    bedrooms: int = 2,
    pets_policy: str = "allowed_with_small_dog",
    description: str = "Nice 2BR apartment",
) -> Listing:
    return Listing(
        id="listing-1",
        property_manager_id="pm-1",
        address="123 Main St, Austin TX",
        bedrooms=bedrooms,
        bathrooms=1.0,
        price=price,
        url="https://example.com/listing-1",
        pets_policy=pets_policy,
        amenities="[]",
        photos="[]",
        description=description,
        extraction_timestamp=datetime.now(UTC),
        validation_passed=True,
    )


@pytest.mark.asyncio
async def test_scorer_returns_score_and_explanation(monkeypatch):
    """Scorer should return a score between 0-1 and a text explanation."""

    class FakeLLM:
        async def complete(self, **kwargs):
            assert kwargs["response_model"] is ListingScore
            return ListingScore(score=0.85, explanation="Good match: pet-friendly, within budget")

    import doormat.scoring.scorer as scorer_mod

    monkeypatch.setattr(scorer_mod, "get_llm_client", lambda: FakeLLM())

    scorer = ListingScorer()
    result = await scorer.score(make_listing(), make_preference())

    assert 0.0 <= result.score <= 1.0
    assert len(result.explanation) > 0
    assert result.score == 0.85


@pytest.mark.asyncio
async def test_scorer_degrades_on_llm_error(monkeypatch):
    """LLM failure should return score=0 with error explanation, not raise."""

    class FailingLLM:
        async def complete(self, **kwargs):
            raise RuntimeError("LLM unavailable")

    import doormat.scoring.scorer as scorer_mod

    monkeypatch.setattr(scorer_mod, "get_llm_client", lambda: FailingLLM())

    scorer = ListingScorer()
    result = await scorer.score(make_listing(), make_preference())

    assert result.score == 0.0
    assert "error" in result.explanation.lower() or "unavailable" in result.explanation.lower()


@pytest.mark.asyncio
async def test_scorer_score_batch_updates_listings():
    """score_batch should update listing.score and listing.score_explanation in place."""
    listings = [make_listing(price=1400), make_listing(price=1800)]
    listings[1].id = "listing-2"

    scores = [
        ListingScore(score=0.9, explanation="Great match"),
        ListingScore(score=0.5, explanation="Acceptable"),
    ]

    scorer = ListingScorer()

    async def fake_score(listing, preference):
        idx = 0 if listing.price == 1400.0 else 1
        return scores[idx]

    scorer.score = fake_score  # type: ignore[method-assign]

    await scorer.score_batch(listings, make_preference())

    assert listings[0].score == 0.9
    assert listings[0].score_explanation == "Great match"
    assert listings[1].score == 0.5
    assert listings[1].score_explanation == "Acceptable"


def test_listing_score_validates_range():
    """ListingScore must enforce 0-1 bounds."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        ListingScore(score=1.5, explanation="out of range")

    with pytest.raises(pydantic.ValidationError):
        ListingScore(score=-0.1, explanation="negative")
