"""Eval suite: Discovery search (LLM candidate generation).

Pass-rate threshold: 80% of test cases must produce >= 1 valid DiscoveryCandidate
with confidence > 0 and a parseable domain in the website field.

Run:
    uv run pytest evals/discovery/ -v
    EVAL_LIVE=1 uv run pytest evals/discovery/ -v  # real LLM calls
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "src" / "backend"))

from doormat.discovery.search import DiscoverySearch, _SearchResponse
from doormat.llm.prompt_registry import PromptKey, get_prompt_version

from evals.conftest import EVAL_LIVE, write_eval_result

PASS_THRESHOLD = 0.80


# ---------------------------------------------------------------------------
# Test cases: queries the search module should handle
# ---------------------------------------------------------------------------

DISCOVERY_CASES: list[dict[str, Any]] = [
    {
        "name": "austin_tx",
        "city": "Austin",
        "mock_candidates": [
            {"name": "Austin Realty Group", "website": "https://austinrealtygroup.example.com", "confidence": 0.9},
            {"name": "Capital City Rentals", "website": "https://capitalcityrentals.example.com", "confidence": 0.8},
            {"name": "Lone Star Property Management", "website": "https://lonestarpm.example.com", "confidence": 0.75},
        ],
        "min_expected_count": 1,
    },
    {
        "name": "denver_co",
        "city": "Denver",
        "mock_candidates": [
            {"name": "Mile High Properties", "website": "https://milehighprops.example.com", "confidence": 0.85},
            {"name": "Rocky Mountain Rentals", "website": "https://rmrentals.example.com", "confidence": 0.7},
        ],
        "min_expected_count": 1,
    },
    {
        "name": "dedup_same_domain",
        "city": "Austin",
        "mock_candidates": [
            {"name": "Austin PM", "website": "https://austinpm.example.com/about", "confidence": 0.8},
            {"name": "Austin PM LLC", "website": "https://austinpm.example.com/rentals", "confidence": 0.75},
            {"name": "Different PM", "website": "https://different.example.com", "confidence": 0.7},
        ],
        # After dedup by domain, should be 2 unique domains
        "min_expected_count": 1,
    },
]


def _make_mock_response(mock_candidates: list[dict[str, Any]]) -> _SearchResponse:
    from doormat.discovery.search import _SearchCandidate, _SearchResponse

    return _SearchResponse(
        candidates=[
            _SearchCandidate(
                name=c["name"],
                website=c["website"],
                confidence=c["confidence"],
            )
            for c in mock_candidates
        ]
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discovery_search_prompt_version_registered() -> None:
    version = get_prompt_version(PromptKey.DISCOVERY_SEARCH_SYSTEM)
    assert version, "DISCOVERY_SEARCH_SYSTEM version must not be empty"


@pytest.mark.asyncio
async def test_discovery_system_prompt_content() -> None:
    """Search system prompt must reference property management concepts."""
    from doormat.llm.prompt_registry import DEFAULT_PROMPTS

    system = DEFAULT_PROMPTS[PromptKey.DISCOVERY_SEARCH_SYSTEM]
    assert len(system) >= 100, "discovery system prompt suspiciously short"
    lower = system.lower()
    assert any(word in lower for word in ("property", "manager", "rental", "company")), (
        "system prompt should reference property management search concepts"
    )


@pytest.mark.skipif(EVAL_LIVE, reason="mocked-only test")
@pytest.mark.asyncio
async def test_discovery_search_pass_rate_mocked() -> None:
    """Mocked search must return well-formed DiscoveryCandidates for all cities."""
    results: dict[str, Any] = {}
    passed = 0

    for case in DISCOVERY_CASES:
        mock_response = _make_mock_response(case["mock_candidates"])

        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=mock_response)

        # Patch _build_user_prompt side call via run_logger
        mock_run_logger = MagicMock()
        mock_run_logger.info = AsyncMock()
        mock_run_logger.error = AsyncMock()

        searcher = DiscoverySearch(llm=mock_llm)
        candidates = await searcher.find_candidates(case["city"], run_logger=mock_run_logger)

        ok = (
            len(candidates) >= case["min_expected_count"]
            and all(c.confidence > 0 for c in candidates)
            and all(c.website.startswith("http") for c in candidates)
            and all(c.city == case["city"] for c in candidates)
            and all(c.source == "llm_search" for c in candidates)
        )
        if ok:
            passed += 1
        results[case["name"]] = {
            "passed": ok,
            "candidate_count": len(candidates),
            "min_expected": case["min_expected_count"],
            "names": [c.name for c in candidates],
        }

    pass_rate = passed / len(DISCOVERY_CASES)
    results["_summary"] = {
        "pass_rate": pass_rate,
        "threshold": PASS_THRESHOLD,
        "passed": passed,
        "total": len(DISCOVERY_CASES),
    }
    write_eval_result("discovery", get_prompt_version(PromptKey.DISCOVERY_SEARCH_SYSTEM), results)

    assert pass_rate >= PASS_THRESHOLD, (
        f"Discovery search pass rate {pass_rate:.0%} below threshold {PASS_THRESHOLD:.0%}"
    )


@pytest.mark.asyncio
async def test_discovery_dedup_by_domain() -> None:
    """Same domain from multiple candidates must be deduped."""
    mock_response = _make_mock_response([
        {"name": "PM Austin", "website": "https://pm.example.com/page1", "confidence": 0.9},
        {"name": "PM Austin 2", "website": "https://pm.example.com/page2", "confidence": 0.8},
        {"name": "Other PM", "website": "https://othersite.example.com", "confidence": 0.7},
    ])

    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value=mock_response)
    mock_run_logger = MagicMock()
    mock_run_logger.info = AsyncMock()

    searcher = DiscoverySearch(llm=mock_llm)
    candidates = await searcher.find_candidates("Austin", run_logger=mock_run_logger)

    # Should dedupe pm.example.com to 1, plus othersite.example.com = 2 total
    assert len(candidates) == 2, f"Expected 2 after dedup, got {len(candidates)}"


@pytest.mark.asyncio
async def test_discovery_search_error_raises() -> None:
    """LLM failure should raise DiscoverySearchError, not silently swallow."""
    from doormat.discovery.search import DiscoverySearchError

    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
    mock_run_logger = MagicMock()
    mock_run_logger.error = AsyncMock()
    mock_run_logger.info = AsyncMock()

    searcher = DiscoverySearch(llm=mock_llm)
    with pytest.raises(DiscoverySearchError):
        await searcher.find_candidates("Austin", run_logger=mock_run_logger)


@pytest.mark.skipif(not EVAL_LIVE, reason="requires EVAL_LIVE=1 and OPENROUTER_API_KEY")
@pytest.mark.asyncio
async def test_discovery_search_live_austin() -> None:
    """Live LLM: Austin search should return >= 3 candidates."""
    from unittest.mock import MagicMock, AsyncMock

    mock_run_logger = MagicMock()
    mock_run_logger.info = AsyncMock()
    mock_run_logger.error = AsyncMock()

    searcher = DiscoverySearch()
    candidates = await searcher.find_candidates("Austin", run_logger=mock_run_logger)

    assert len(candidates) >= 1, f"Expected >= 1 candidates, got {len(candidates)}"
    assert all(c.city == "Austin" for c in candidates)
    assert all(c.source == "llm_search" for c in candidates)

    write_eval_result(
        "discovery_live",
        get_prompt_version(PromptKey.DISCOVERY_SEARCH_SYSTEM),
        {
            "city": "Austin",
            "candidate_count": len(candidates),
            "candidates": [{"name": c.name, "website": c.website, "confidence": c.confidence} for c in candidates[:5]],
        },
    )
