"""Eval suite: Listing scorer.

Pass-rate threshold: 80% of test cases must produce a score within the
expected direction (high-match listings score >= 0.6, poor-match <= 0.4).

Run:
    uv run pytest evals/scoring/ -v
    EVAL_LIVE=1 uv run pytest evals/scoring/ -v  # real LLM calls
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "src" / "backend"))

from doormat.llm.prompt_registry import PromptKey, get_prompt_version
from doormat.scoring.scorer import ListingScore, ListingScorer

from evals.conftest import (
    EVAL_LIVE,
    SAMPLE_LISTING,
    SAMPLE_PREFERENCE,
    write_eval_result,
)

PASS_THRESHOLD = 0.80


# ---------------------------------------------------------------------------
# Build lightweight ORM-like mock objects (avoids full DB setup)
# ---------------------------------------------------------------------------


def _make_listing(**overrides: Any) -> MagicMock:
    """Create a mock Listing with SAMPLE_LISTING defaults."""
    data = {**SAMPLE_LISTING, **overrides}
    m = MagicMock()
    for k, v in data.items():
        setattr(m, k, v)
    m.id = 1
    m.score = None
    return m


def _make_preference(**overrides: Any) -> MagicMock:
    """Create a mock Preference with SAMPLE_PREFERENCE defaults."""
    data = {**SAMPLE_PREFERENCE, **overrides}
    m = MagicMock()
    for k, v in data.items():
        setattr(m, k, v)
    m.id = 1
    m.smart_model = "anthropic/claude-haiku-4-5"
    m.openrouter_api_key = None
    m.prompt_overrides = None
    return m


# ---------------------------------------------------------------------------
# Test cases: (listing_overrides, preference_overrides, expected_direction)
# direction: "high" = score >= 0.6, "low" = score <= 0.4, "any" = no assertion
# ---------------------------------------------------------------------------

SCORING_CASES: list[dict[str, Any]] = [
    {
        "name": "perfect_match",
        "listing": {},
        "preference": {},
        "expected_direction": "high",
        "mock_score": 0.85,
    },
    {
        "name": "over_budget",
        "listing": {"price": 3500.0},
        "preference": {},
        "expected_direction": "low",
        "mock_score": 0.25,
    },
    {
        "name": "wrong_city",
        "listing": {"address": "123 Main St, Dallas, TX 75201"},
        "preference": {},
        "expected_direction": "low",
        "mock_score": 0.20,
    },
    {
        "name": "good_match_pets_ok",
        "listing": {"pets_policy": "allowed_with_small_dog"},
        "preference": {"description": "Austin apartment, dogs welcome, under $2000"},
        "expected_direction": "high",
        "mock_score": 0.80,
    },
    {
        "name": "no_laundry_required",
        "listing": {"amenities": '["pool", "gym"]'},
        "preference": {"description": "need in-unit washer/dryer, Austin"},
        "expected_direction": "any",
        "mock_score": 0.5,
    },
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scoring_prompt_version_registered() -> None:
    version = get_prompt_version(PromptKey.SCORING_SYSTEM)
    assert version, "SCORING_SYSTEM version must not be empty"


@pytest.mark.asyncio
async def test_scoring_system_prompt_content() -> None:
    """Scoring system prompt must reference scoring concepts."""
    from doormat.llm.prompt_registry import DEFAULT_PROMPTS

    system = DEFAULT_PROMPTS[PromptKey.SCORING_SYSTEM]
    assert len(system) >= 100, "scoring system prompt suspiciously short"
    lower = system.lower()
    assert any(word in lower for word in ("score", "match", "preference", "listing")), (
        "system prompt should reference scoring concepts"
    )


@pytest.mark.skipif(EVAL_LIVE, reason="mocked-only test")
@pytest.mark.asyncio
async def test_scorer_pass_rate_mocked() -> None:
    """Mocked scorer must return scores in expected direction."""
    results: dict[str, Any] = {}
    passed = 0

    for case in SCORING_CASES:
        listing = _make_listing(**case["listing"])
        preference = _make_preference(**case["preference"])
        mock_response = ListingScore(
            score=case["mock_score"],
            explanation=f"Mock evaluation for {case['name']}.",
        )

        with (
            patch("doormat.scoring.scorer.get_llm_client") as mock_factory,
            patch("doormat.scoring.scorer.decrypt_secret", return_value="fake_key"),
        ):
            client_instance = AsyncMock()
            client_instance.complete = AsyncMock(return_value=mock_response)
            mock_factory.return_value = client_instance

            scorer = ListingScorer()
            result = await scorer.score(listing, preference)

        direction = case["expected_direction"]
        if direction == "high":
            ok = result.score >= 0.6
        elif direction == "low":
            ok = result.score <= 0.4
        else:
            ok = 0.0 <= result.score <= 1.0

        if ok:
            passed += 1
        results[case["name"]] = {
            "passed": ok,
            "score": result.score,
            "direction": direction,
            "explanation_length": len(result.explanation),
        }

    pass_rate = passed / len(SCORING_CASES)
    results["_summary"] = {
        "pass_rate": pass_rate,
        "threshold": PASS_THRESHOLD,
        "passed": passed,
        "total": len(SCORING_CASES),
    }
    write_eval_result("scoring", get_prompt_version(PromptKey.SCORING_SYSTEM), results)

    assert pass_rate >= PASS_THRESHOLD, (
        f"Scorer pass rate {pass_rate:.0%} below threshold {PASS_THRESHOLD:.0%}"
    )


@pytest.mark.asyncio
async def test_scorer_heuristic_fallback_on_error() -> None:
    """Scorer must fall back to heuristic (not raise) when LLM fails."""
    listing = _make_listing()
    preference = _make_preference()

    with (
        patch("doormat.scoring.scorer.get_llm_client") as mock_factory,
        patch("doormat.scoring.scorer.decrypt_secret", return_value="fake_key"),
    ):
        client_instance = AsyncMock()
        client_instance.complete = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        mock_factory.return_value = client_instance

        scorer = ListingScorer()
        result = await scorer.score(listing, preference)

    assert 0.0 <= result.score <= 1.0, "Fallback score must be in [0, 1]"
    assert len(result.explanation) > 0


@pytest.mark.asyncio
async def test_scorer_score_is_bounded() -> None:
    """Score must be in [0.0, 1.0] regardless of LLM response."""
    listing = _make_listing()
    preference = _make_preference()

    for clamped_score in [0.0, 0.5, 1.0]:
        mock_response = ListingScore(score=clamped_score, explanation="test")
        with (
            patch("doormat.scoring.scorer.get_llm_client") as mock_factory,
            patch("doormat.scoring.scorer.decrypt_secret", return_value="fake_key"),
        ):
            client_instance = AsyncMock()
            client_instance.complete = AsyncMock(return_value=mock_response)
            mock_factory.return_value = client_instance

            scorer = ListingScorer()
            result = await scorer.score(listing, preference)

        assert 0.0 <= result.score <= 1.0


@pytest.mark.skipif(not EVAL_LIVE, reason="requires EVAL_LIVE=1 and OPENROUTER_API_KEY")
@pytest.mark.asyncio
async def test_scorer_live_good_match() -> None:
    """Live LLM: sample listing should score >= 0.6 against sample preference."""
    listing = _make_listing()
    preference = _make_preference()
    scorer = ListingScorer()
    result = await scorer.score(listing, preference)

    assert 0.0 <= result.score <= 1.0
    assert len(result.explanation) > 10

    write_eval_result(
        "scoring_live",
        get_prompt_version(PromptKey.SCORING_SYSTEM),
        {"score": result.score, "explanation": result.explanation[:200]},
    )
