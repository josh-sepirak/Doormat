"""Eval suite: Mode A listing extraction.

Pass-rate threshold: 80% of test cases must produce a ListingExtractionResult
with confidence != "low" and all required fields populated.

Run:
    uv run pytest evals/extraction/ -v
    EVAL_LIVE=1 uv run pytest evals/extraction/ -v  # real LLM calls
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

# Ensure the backend package is importable when running from repo root
sys.path.insert(0, str(Path(__file__).parents[3] / "src" / "backend"))

from doormat.extraction.mode_a import run_mode_a
from doormat.extraction.schemas import ExtractedListing, ListingExtractionResult
from doormat.llm.prompt_registry import PromptKey, get_prompt_version

from evals.conftest import EVAL_LIVE, SAMPLE_LISTING_HTML, write_eval_result

PASS_THRESHOLD = 0.80

# ---------------------------------------------------------------------------
# Test fixtures: cases the extractor must handle
# ---------------------------------------------------------------------------

EXTRACTION_CASES: list[dict[str, Any]] = [
    {
        "name": "standard_apartment",
        "html": SAMPLE_LISTING_HTML,
        "url": "https://oakcreekapartments.example.com/units/101",
        "source_id": "oakcreek",
        "expected_price_range": (1800, 1900),
        "expected_bedrooms": 2,
        "expected_pets_keyword": "cats",
    },
    {
        "name": "minimal_listing",
        "html": """
        <html><body>
        <h1>Studio for rent - $950/month</h1>
        <p>1234 Main St, Austin TX 78701</p>
        <p>Studio, 1 bath. No pets. Available now.</p>
        </body></html>
        """,
        "url": "https://example-pm.com/studio",
        "source_id": "example_pm",
        "expected_price_range": (900, 1000),
        "expected_bedrooms": 0,
        "expected_pets_keyword": None,
    },
    {
        "name": "multi_bedroom_listing",
        "html": """
        <html><body>
        <h1>3BR/2BA House - $2,400/mo</h1>
        <p>Address: 789 Oak Lane, Austin TX 78745</p>
        <p>3 beds, 2 full baths, 1450 sq ft. Dogs and cats welcome. Yard.</p>
        <ul><li>In-unit laundry</li><li>Private garage</li><li>Backyard</li></ul>
        </body></html>
        """,
        "url": "https://austinrentals.example.com/oak-lane",
        "source_id": "austin_rentals",
        "expected_price_range": (2300, 2500),
        "expected_bedrooms": 3,
        "expected_pets_keyword": "dog",
    },
]


def _make_mock_result(case: dict[str, Any]) -> ListingExtractionResult:
    """Build a plausible mock LLM response for a test case."""
    price_low, price_high = case["expected_price_range"]
    rent = (price_low + price_high) // 2
    pets_policy = (
        "cats_only"
        if case["expected_pets_keyword"] == "cats"
        else "allowed_with_small_dog"
        if case["expected_pets_keyword"] == "dog"
        else "none_allowed"
    )
    return ListingExtractionResult(
        listing=ExtractedListing(
            address="4512 Shoal Creek Blvd, Austin, TX 78756",
            rent=rent,
            bedrooms=case["expected_bedrooms"],
            bathrooms=1.0,
            sqft=920,
            pets_policy=pets_policy,
            amenities=["pool", "in-unit laundry"],
            photos=[],
            description="Sample description.",
        ),
        confidence="high",
        mode="A",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extraction_prompt_has_required_placeholders() -> None:
    """System and user prompts must contain expected format placeholders."""
    from doormat.llm.prompt_registry import DEFAULT_PROMPTS, PromptKey

    user_prompt = DEFAULT_PROMPTS[PromptKey.EXTRACTION_MODE_A_USER]
    assert "{html}" in user_prompt, "user prompt must contain {html} placeholder"
    assert "{url}" in user_prompt, "user prompt must contain {url} placeholder"
    assert "{source}" in user_prompt, "user prompt must contain {source} placeholder"

    system_prompt = DEFAULT_PROMPTS[PromptKey.EXTRACTION_MODE_A_SYSTEM]
    assert len(system_prompt) >= 100, "system prompt suspiciously short"


@pytest.mark.asyncio
async def test_extraction_prompt_version_registered() -> None:
    """Prompt version must be registered in PROMPT_VERSIONS."""
    version = get_prompt_version(PromptKey.EXTRACTION_MODE_A_SYSTEM)
    assert version, "EXTRACTION_MODE_A_SYSTEM version must not be empty"
    user_version = get_prompt_version(PromptKey.EXTRACTION_MODE_A_USER)
    assert user_version, "EXTRACTION_MODE_A_USER version must not be empty"


@pytest.mark.skipif(EVAL_LIVE, reason="mocked-only test")
@pytest.mark.asyncio
async def test_extraction_mode_a_pass_rate_mocked() -> None:
    """All mocked cases must return a valid ListingExtractionResult."""
    results: dict[str, Any] = {}
    passed = 0

    for case in EXTRACTION_CASES:
        mock_result = _make_mock_result(case)
        mock_client = AsyncMock(return_value=mock_result)

        with patch("doormat.extraction.mode_a.get_llm_client") as mock_factory:
            client_instance = AsyncMock()
            client_instance.complete = mock_client
            mock_factory.return_value = client_instance

            result = await run_mode_a(
                html=case["html"],
                url=case["url"],
                source_id=case["source_id"],
                strategy=None,
            )

        ok = (
            result.listing is not None
            and result.listing.rent > 0
            and result.listing.bedrooms >= 0
            and result.confidence in {"high", "medium", "low"}
            and result.mode == "A"
        )
        if ok:
            passed += 1
        results[case["name"]] = {
            "passed": ok,
            "confidence": result.confidence,
            "rent": result.listing.rent,
            "bedrooms": result.listing.bedrooms,
        }

    pass_rate = passed / len(EXTRACTION_CASES)
    results["_summary"] = {
        "pass_rate": pass_rate,
        "threshold": PASS_THRESHOLD,
        "passed": passed,
        "total": len(EXTRACTION_CASES),
    }
    write_eval_result("extraction", get_prompt_version(PromptKey.EXTRACTION_MODE_A_SYSTEM), results)

    assert pass_rate >= PASS_THRESHOLD, (
        f"Extraction pass rate {pass_rate:.0%} below threshold {PASS_THRESHOLD:.0%}"
    )


@pytest.mark.skipif(not EVAL_LIVE, reason="requires EVAL_LIVE=1 and OPENROUTER_API_KEY")
@pytest.mark.asyncio
async def test_extraction_mode_a_pass_rate_live() -> None:
    """Live LLM eval against real SAMPLE_LISTING_HTML. Requires OPENROUTER_API_KEY."""
    result = await run_mode_a(
        html=SAMPLE_LISTING_HTML,
        url="https://oakcreekapartments.example.com/units/101",
        source_id="oakcreek_eval",
        strategy=None,
    )

    assert result.listing is not None
    assert result.listing.bedrooms == 2, f"Expected 2BR, got {result.listing.bedrooms}"
    assert 1800 <= result.listing.rent <= 1900, f"Expected ~$1850, got {result.listing.rent}"
    assert result.confidence in {"high", "medium"}, f"Unexpected confidence: {result.confidence}"
    assert result.mode == "A"

    write_eval_result(
        "extraction_live",
        get_prompt_version(PromptKey.EXTRACTION_MODE_A_SYSTEM),
        {
            "rent": result.listing.rent,
            "bedrooms": result.listing.bedrooms,
            "confidence": result.confidence,
            "pets_policy": result.listing.pets_policy,
        },
    )
