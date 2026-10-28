"""Unit tests for multimodal decision model evaluator."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from doormat.models.orm import Listing, Preference
from doormat.scoring.multimodal_evaluator import (
    DEFAULT_MULTIMODAL_MODEL,
    MultimodalListingEvaluator,
    extract_photo_urls,
    extract_visual_criteria,
)
from doormat.scoring.schemas import MultimodalEvaluationResult, VisualCriterionVerdict
from doormat.security.secrets import encrypt_secret


def make_test_preference(description: str = "Backyard for 12ft trampoline and dog space") -> Preference:
    return Preference(
        id="pref-mm-1",
        description=description,
        city="Austin",
        openrouter_api_key=encrypt_secret("sk-or-v1-testkey1234567890"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def make_test_listing(photos: list[str] | None = None) -> Listing:
    photo_json = json.dumps(
        photos
        if photos is not None
        else [
            "https://images.example.com/front.jpg",
            "https://images.example.com/backyard-lawn.jpg",
            "https://images.example.com/fenced-grass.jpg",
            "https://images.example.com/laundry.jpg",
        ]
    )
    return Listing(
        id="listing-mm-1",
        property_manager_id="pm-1",
        address="742 Evergreen Terrace, Austin TX",
        price=2400.0,
        bedrooms=3,
        bathrooms=2.0,
        url="https://example.com/listing-mm-1",
        pets_policy="allowed_with_small_dog",
        amenities="[]",
        photos=photo_json,
        description="Charming home with large fenced backyard and sunny patio.",
        extraction_timestamp=datetime.now(UTC),
        validation_passed=True,
    )


def test_extract_visual_criteria_trampoline_and_dog():
    text = "We have active kids needing space for a 12ft trampoline and a fenced yard for our dog."
    criteria = extract_visual_criteria(text)
    assert any("trampoline" in c.lower() for c in criteria)
    assert any("dog" in c.lower() or "fenced" in c.lower() for c in criteria)


def test_extract_visual_criteria_laundry_and_light():
    text = "Looking for bright natural light, in-unit laundry, and room for a desk nook."
    criteria = extract_visual_criteria(text)
    assert any("laundry" in c.lower() for c in criteria)
    assert any("natural light" in c.lower() for c in criteria)
    assert any("workspace" in c.lower() or "desk" in c.lower() for c in criteria)


def test_extract_visual_criteria_defaults_when_empty():
    criteria = extract_visual_criteria("")
    assert len(criteria) >= 3
    assert any("outdoor" in c.lower() for c in criteria)
    assert any("laundry" in c.lower() for c in criteria)


def test_extract_photo_urls_filters_and_caps():
    listing = make_test_listing(
        photos=[
            "https://example.com/1.jpg",
            "invalid-url",
            "ftp://bad-scheme.com/2.jpg",
            "https://example.com/2.jpg",
            "https://example.com/3.jpg",
            "https://example.com/4.jpg",
            "https://example.com/5.jpg",
        ]
    )
    urls = extract_photo_urls(listing, max_photos=4)
    assert urls == [
        "https://example.com/1.jpg",
        "https://example.com/2.jpg",
        "https://example.com/3.jpg",
        "https://example.com/4.jpg",
    ]


def test_visual_criterion_verdict_to_filter_reason():
    verdict = VisualCriterionVerdict(
        criterion="12ft trampoline fit",
        verdict="confirmed",
        confidence="high",
        plain_label="Fits 12ft Trampoline",
        evidence="Photo 2 shows a flat grassy backyard (~35ft wide) with no overhead tree canopy.",
        photo_index=2,
    )
    reason = verdict.to_filter_reason()
    assert reason["label"] == "Fits 12ft Trampoline"
    assert reason["severity"] == "confirmed"
    assert reason["verdict"] == "confirmed"
    assert reason["photo_index"] == 2
    assert reason["is_visual"] is True
    assert "Photo 2" in reason["evidence"]


@pytest.mark.asyncio
async def test_multimodal_evaluator_calls_gemini_and_parses_response(monkeypatch):
    expected_result = MultimodalEvaluationResult(
        match_score=0.94,
        headline="Great 3BR home with wide flat lawn fitting your trampoline and dog",
        criteria=[
            VisualCriterionVerdict(
                criterion="12ft trampoline fit",
                verdict="confirmed",
                confidence="high",
                plain_label="Fits 12ft Trampoline",
                evidence="Photo 2 shows a large flat grassy lawn (~35ft across) with plenty of clearance.",
                photo_index=2,
            ),
            VisualCriterionVerdict(
                criterion="Dog outdoor space",
                verdict="confirmed",
                confidence="high",
                plain_label="Fenced Yard for Dogs",
                evidence="Photo 3 shows secure 6ft perimeter fencing enclosing the grass.",
                photo_index=3,
            ),
        ],
    )

    mock_llm = AsyncMock()
    mock_llm.complete.return_value = expected_result

    import doormat.scoring.multimodal_evaluator as mm_mod

    monkeypatch.setattr(mm_mod, "get_llm_client", lambda api_key=None: mock_llm)

    pref = make_test_preference("Need space for 12ft trampoline and fenced dog yard")
    listing = make_test_listing()

    evaluator = MultimodalListingEvaluator()
    res = await evaluator.evaluate(listing, pref)

    assert res.match_score == 0.94
    assert len(res.criteria) == 2
    assert res.criteria[0].verdict == "confirmed"
    assert res.criteria[0].photo_index == 2
    assert res.criteria[1].photo_index == 3

    # Verify model and multimodal message formatting
    call_kwargs = mock_llm.complete.call_args.kwargs
    assert call_kwargs["model"] == DEFAULT_MULTIMODAL_MODEL
    messages = call_kwargs["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")
    image_parts = [p for p in user_msg["content"] if p.get("type") == "image_url"]
    assert len(image_parts) == 4
    assert image_parts[1]["image_url"]["url"] == "https://images.example.com/backyard-lawn.jpg"


@pytest.mark.asyncio
async def test_multimodal_evaluator_errors_on_no_photos():
    pref = make_test_preference()
    listing = make_test_listing(photos=[])

    evaluator = MultimodalListingEvaluator()
    with pytest.raises(ValueError, match="no valid photo URLs"):
        await evaluator.evaluate(listing, pref)


@pytest.mark.asyncio
async def test_multimodal_evaluator_errors_on_missing_api_key():
    pref = make_test_preference()
    pref.openrouter_api_key = None
    listing = make_test_listing()

    evaluator = MultimodalListingEvaluator()
    with pytest.raises(ValueError, match="No OpenRouter API key configured"):
        await evaluator.evaluate(listing, pref)
