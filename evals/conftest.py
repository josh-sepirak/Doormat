"""Shared fixtures for the Doormat eval harness.

Each suite imports what it needs from here.  LLM calls are mocked by default —
the evals exercise prompt construction, output parsing, and module contracts,
not live network calls.  To run against a real model:

    EVAL_LIVE=1 uv run pytest evals/

(Requires OPENROUTER_API_KEY in the environment.)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

EVAL_LIVE = bool(os.getenv("EVAL_LIVE"))


# ---------------------------------------------------------------------------
# Sample HTML fixture — a trimmed realistic apartment listing page
# ---------------------------------------------------------------------------

SAMPLE_LISTING_HTML = """\
<!DOCTYPE html>
<html>
<head><title>2BR/1BA - $1850/mo - Oak Creek Apartments</title></head>
<body>
<h1>Oak Creek Apartments</h1>
<div class="price">$1,850/month</div>
<div class="details">
  <span class="beds">2 bedrooms</span>
  <span class="baths">1 bathroom</span>
  <span class="sqft">920 sq ft</span>
</div>
<p class="address">4512 Shoal Creek Blvd, Austin, TX 78756</p>
<p class="description">
  Spacious 2-bed unit in a quiet complex. Recently renovated kitchen with
  stainless appliances. In-unit washer/dryer hookups. Covered parking included.
  Cats welcome — no dogs. Non-smoking community. Lease terms: 12 months.
</p>
<ul class="amenities">
  <li>In-unit laundry hookups</li>
  <li>Covered parking</li>
  <li>Pool</li>
  <li>Fitness center</li>
</ul>
<a href="https://oakcreekapartments.example.com/apply">Apply Now</a>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Sample classifier candidate
# ---------------------------------------------------------------------------

SAMPLE_CANDIDATE = {
    "name": "Oak Creek Property Management",
    "website": "https://oakcreekapartments.example.com",
    "city": "Austin",
    "confidence": 0.85,
    "source": "llm_search",
}


# ---------------------------------------------------------------------------
# Sample listing / preference for scoring
# ---------------------------------------------------------------------------

SAMPLE_LISTING = {
    "address": "4512 Shoal Creek Blvd, Austin, TX 78756",
    "price": 1850.0,
    "bedrooms": 2,
    "bathrooms": 1.0,
    "sqft": 920,
    "pets_policy": "cats_only",
    "amenities": '["in-unit laundry hookups", "covered parking", "pool"]',
    "description": "Spacious 2-bed unit, renovated kitchen, cats welcome.",
}

SAMPLE_PREFERENCE = {
    "description": "2BR under $2000/mo near downtown Austin, laundry in unit, cats OK",
    "city": "Austin",
}


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_html() -> str:
    return SAMPLE_LISTING_HTML


@pytest.fixture
def sample_candidate() -> dict[str, Any]:
    return SAMPLE_CANDIDATE.copy()


@pytest.fixture
def sample_listing_data() -> dict[str, Any]:
    return SAMPLE_LISTING.copy()


@pytest.fixture
def sample_preference_data() -> dict[str, Any]:
    return SAMPLE_PREFERENCE.copy()


@pytest.fixture
def mock_llm_client():
    """Return an LLMClient mock that returns configurable structured responses."""
    client = MagicMock()
    client.complete = AsyncMock()
    return client


def write_eval_result(key: str, version: str, results: dict[str, Any]) -> Path:
    """Persist eval results to evals/results/<key>/<version>.json."""
    key_dir = RESULTS_DIR / key
    key_dir.mkdir(exist_ok=True)
    out = key_dir / f"{version}.json"
    out.write_text(json.dumps(results, indent=2))
    return out
