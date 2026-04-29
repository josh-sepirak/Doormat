"""Deterministic filter classification tests (T051)."""

from datetime import UTC, datetime

from doormat.models.orm import Listing, Preference
from doormat.runs.filters import build_run_filter_snapshot, classify_listing, merge_filters


def _listing(**kw: object) -> Listing:
    defaults: dict[str, object] = {
        "id": "l1",
        "property_manager_id": "pm1",
        "address": "123 Main St, Austin, TX",
        "bedrooms": 2,
        "bathrooms": 1.0,
        "sqft": None,
        "price": 1800.0,
        "url": "https://example.com/l",
        "pets_policy": "unknown",
        "amenities": None,
        "photos": None,
        "description": None,
        "raw_data": None,
        "extraction_timestamp": datetime.now(UTC),
        "extraction_model": None,
        "tier1_cost": None,
        "tier2_cost": None,
        "validation_passed": True,
        "score": 0.85,
        "score_explanation": None,
        "saved": False,
    }
    defaults.update(kw)
    return Listing(**defaults)  # type: ignore[arg-type]


def test_merge_filters_defaults():
    merged = merge_filters({"max_price": 2000})
    assert merged["max_price"] == 2000
    assert merged["score_great_threshold"] == 0.8


def test_build_run_filter_snapshot_derives_preference_signals():
    pref = Preference(
        id="pref-1",
        description="2BR under $2500, pet-friendly, 1.5 bath",
        city="Austin",
        sources_enabled='["craigslist", "zillow"]',
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    snapshot = build_run_filter_snapshot(pref)

    assert snapshot["sources_enabled"] == ["craigslist", "zillow"]
    assert snapshot["max_price"] == 2500.0
    assert snapshot["min_bedrooms"] == 2
    assert snapshot["min_bathrooms"] == 1.5
    assert snapshot["pets_required"] is True


def test_great_match_when_hard_filters_pass_and_score_high():
    listing = _listing(price=1900, bedrooms=2, score=0.9)
    cat, reasons, _exp = classify_listing(
        listing, {"max_price": 2000, "min_bedrooms": 2}, effective_score=0.9
    )
    assert cat == "great_match"
    assert reasons == []


def test_filtered_out_when_rent_far_over_budget():
    listing = _listing(price=4000)
    cat, reasons, _exp = classify_listing(listing, {"max_price": 2000}, effective_score=0.9)
    assert cat == "filtered_out"
    assert any(r.get("filter_code") == "max_rent" for r in reasons)


def test_near_miss_when_rent_slightly_over_budget():
    listing = _listing(price=2150)
    cat, reasons, _exp = classify_listing(listing, {"max_price": 2000}, effective_score=0.9)
    assert cat == "near_miss"
    assert any(r.get("severity") == "near_miss" for r in reasons)


def test_pets_required_unknown_policy_is_near_miss():
    listing = _listing(pets_policy="unknown", score=0.9)
    cat, reasons, _exp = classify_listing(listing, {"pets_required": True}, effective_score=0.9)
    assert cat == "near_miss"
    assert any(r.get("filter_code") == "pets_unknown" for r in reasons)
