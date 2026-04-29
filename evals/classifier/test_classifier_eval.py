"""Eval suite: Property manager classifier.

Pass-rate threshold: 80% of test cases must produce correct is_valid classification
(true positives identified as valid, clear negatives rejected).

Run:
    uv run pytest evals/classifier/ -v
    EVAL_LIVE=1 uv run pytest evals/classifier/ -v  # real LLM calls
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "src" / "backend"))

from doormat.discovery.classifier import PropertyManagerClassifier
from doormat.discovery.models import DiscoveryCandidate, ValidationResult
from doormat.llm.prompt_registry import PromptKey, get_prompt_version

from evals.conftest import EVAL_LIVE, SAMPLE_CANDIDATE, write_eval_result

PASS_THRESHOLD = 0.80

# ---------------------------------------------------------------------------
# Test cases: (candidate, expected_valid)
# ---------------------------------------------------------------------------

CLASSIFIER_CASES: list[dict[str, Any]] = [
    {
        "name": "legitimate_pm",
        "candidate": DiscoveryCandidate(
            name="Oak Creek Property Management",
            website="https://oakcreekapartments.example.com",
            city="Austin",
            confidence=0.85,
            source="llm_search",
        ),
        "expected_valid": True,
    },
    {
        "name": "large_pm_company",
        "candidate": DiscoveryCandidate(
            name="Austin Premier Properties LLC",
            website="https://austinpremierproperties.example.com",
            city="Austin",
            confidence=0.75,
            source="llm_search",
        ),
        "expected_valid": True,
    },
    {
        "name": "obvious_non_pm",
        "candidate": DiscoveryCandidate(
            name="Random Blog About Austin",
            website="https://austinblog.example.com",
            city="Austin",
            confidence=0.2,
            source="llm_search",
        ),
        "expected_valid": False,
    },
    {
        "name": "aggregator_not_pm",
        "candidate": DiscoveryCandidate(
            name="Austin Apartments dot com listing page",
            website="https://aggregator.example.com/austin-listings",
            city="Austin",
            confidence=0.3,
            source="browser",
        ),
        "expected_valid": False,
    },
    {
        "name": "low_confidence_candidate",
        "candidate": DiscoveryCandidate(
            name="Maybe Rentals Austin",
            website="https://mayberentals.example.com",
            city="Austin",
            confidence=0.4,
            source="llm_search",
        ),
        "expected_valid": True,
    },
]


def _make_mock_result(expected_valid: bool) -> ValidationResult:
    return ValidationResult(
        is_valid=expected_valid,
        reason="legit property manager" if expected_valid else "not a property manager",
        confidence=0.9 if expected_valid else 0.85,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classifier_prompt_content() -> None:
    """System prompt must mention key classifier concepts."""
    from doormat.llm.prompt_registry import DEFAULT_PROMPTS, PromptKey

    system = DEFAULT_PROMPTS[PromptKey.DISCOVERY_CLASSIFIER_SYSTEM]
    assert len(system) >= 100, "classifier system prompt suspiciously short"
    # Should reference the concept of property management validation
    lower = system.lower()
    assert any(word in lower for word in ("property", "manager", "valid", "rental")), (
        "system prompt should reference property management concepts"
    )


@pytest.mark.asyncio
async def test_classifier_prompt_version_registered() -> None:
    version = get_prompt_version(PromptKey.DISCOVERY_CLASSIFIER_SYSTEM)
    assert version, "DISCOVERY_CLASSIFIER_SYSTEM version must not be empty"


@pytest.mark.asyncio
async def test_classifier_user_prompt_includes_candidate_fields() -> None:
    """_build_user_prompt must include name, website, and city."""
    candidate = DiscoveryCandidate(**SAMPLE_CANDIDATE)
    prompt = PropertyManagerClassifier._build_user_prompt(candidate)
    assert candidate.name in prompt
    assert candidate.website in prompt
    assert candidate.city in prompt


@pytest.mark.skipif(EVAL_LIVE, reason="mocked-only test")
@pytest.mark.asyncio
async def test_classifier_pass_rate_mocked() -> None:
    """Mocked classifier must return correct is_valid for all test cases."""
    results: dict[str, Any] = {}
    passed = 0

    for case in CLASSIFIER_CASES:
        mock_result = _make_mock_result(case["expected_valid"])

        with patch("doormat.discovery.classifier.get_llm_client") as mock_factory:
            client_instance = AsyncMock()
            client_instance.complete = AsyncMock(return_value=mock_result)
            mock_factory.return_value = client_instance

            classifier = PropertyManagerClassifier()
            result = await classifier.classify(case["candidate"])

        ok = (
            result.is_valid == case["expected_valid"]
            and 0.0 <= result.confidence <= 1.0
            and len(result.reason) > 0
        )
        if ok:
            passed += 1
        results[case["name"]] = {
            "passed": ok,
            "is_valid": result.is_valid,
            "expected": case["expected_valid"],
            "confidence": result.confidence,
        }

    pass_rate = passed / len(CLASSIFIER_CASES)
    results["_summary"] = {
        "pass_rate": pass_rate,
        "threshold": PASS_THRESHOLD,
        "passed": passed,
        "total": len(CLASSIFIER_CASES),
    }
    write_eval_result("classifier", get_prompt_version(PromptKey.DISCOVERY_CLASSIFIER_SYSTEM), results)

    assert pass_rate >= PASS_THRESHOLD, (
        f"Classifier pass rate {pass_rate:.0%} below threshold {PASS_THRESHOLD:.0%}"
    )


@pytest.mark.asyncio
async def test_classifier_error_handling() -> None:
    """Classifier must return is_valid=False on LLM error (not raise)."""
    candidate = DiscoveryCandidate(**SAMPLE_CANDIDATE)

    with patch("doormat.discovery.classifier.get_llm_client") as mock_factory:
        client_instance = AsyncMock()
        client_instance.complete = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        mock_factory.return_value = client_instance

        classifier = PropertyManagerClassifier()
        result = await classifier.classify(candidate)

    assert result.is_valid is False
    assert "classification_error" in result.reason


@pytest.mark.skipif(not EVAL_LIVE, reason="requires EVAL_LIVE=1 and OPENROUTER_API_KEY")
@pytest.mark.asyncio
async def test_classifier_live_legitimate_pm() -> None:
    """Live LLM: sample candidate should be classified as a valid PM."""
    candidate = DiscoveryCandidate(**SAMPLE_CANDIDATE)
    classifier = PropertyManagerClassifier()
    result = await classifier.classify(candidate)

    assert result.confidence >= 0.5, f"Expected confidence >= 0.5, got {result.confidence}"
    write_eval_result(
        "classifier_live",
        get_prompt_version(PromptKey.DISCOVERY_CLASSIFIER_SYSTEM),
        {
            "candidate": SAMPLE_CANDIDATE["name"],
            "is_valid": result.is_valid,
            "confidence": result.confidence,
            "reason": result.reason,
        },
    )
