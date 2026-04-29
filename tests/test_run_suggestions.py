"""Deterministic suggestion aggregation tests (T062, T063)."""

from doormat.models.orm import RunListingResult
from doormat.runs.suggestions import aggregate_suggestions_from_results


def test_aggregate_budget_suggestion_from_rent_misses():
    rows = [
        RunListingResult(
            id="1",
            run_id="r1",
            listing_id="l1",
            revision=1,
            category="filtered_out",
            score=None,
            filter_reasons_json='[{"filter_code":"max_rent_near","label":"rent"}]',
            explanation=None,
        ),
        RunListingResult(
            id="2",
            run_id="r1",
            listing_id="l2",
            revision=1,
            category="filtered_out",
            score=None,
            filter_reasons_json='[{"filter_code":"max_rent","label":"rent"}]',
            explanation=None,
        ),
    ]
    out = aggregate_suggestions_from_results(rows)
    kinds = {s["kind"] for s in out}
    assert "raise_budget" in kinds


def test_aggregate_pets_unknown_suggestion():
    rows = [
        RunListingResult(
            id="1",
            run_id="r1",
            listing_id="l1",
            revision=1,
            category="near_miss",
            score=None,
            filter_reasons_json='[{"filter_code":"pets_unknown"}]',
            explanation=None,
        )
    ]
    out = aggregate_suggestions_from_results(rows)
    assert any(s["kind"] == "review_pet_policy" for s in out)


def test_suggestions_use_only_structured_reasons_no_llm():
    """T063: aggregation is pure JSON — no LLM client involved in this module."""
    import doormat.runs.suggestions as mod

    assert not hasattr(mod, "get_llm_client")
