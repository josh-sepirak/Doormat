"""Deterministic hard filters, near-miss tolerances, and per-run listing classification."""

from __future__ import annotations

import json
import uuid
from typing import Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.models.orm import Listing, Preference, PropertyManager, RunListingResult, SearchRun
from doormat.preference_signals import derive_run_filter_overrides, normalize_sources_enabled
from doormat.runs import events as run_events
from doormat.runs import suggestions as run_suggestions
from doormat.scoring.scorer import heuristic_listing_score

logger = structlog.get_logger(__name__)

DEFAULT_FILTERS: dict[str, Any] = {
    "max_price": None,
    "min_bedrooms": None,
    "min_bathrooms": None,
    "pets_required": False,
    "score_great_threshold": 0.8,
    "score_worth_threshold": 0.5,
}


def merge_filters(base: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(DEFAULT_FILTERS)
    if base:
        out.update({k: v for k, v in base.items() if v is not None or k in base})
    return out


def build_run_filter_snapshot(preference: Preference | None) -> dict[str, Any]:
    """Snapshot the resolved filters and sources for a run."""
    snapshot = dict(DEFAULT_FILTERS)
    if preference is None:
        snapshot["sources_enabled"] = normalize_sources_enabled(None)
        return snapshot

    overrides = derive_run_filter_overrides(preference.description, preference.sources_enabled)
    snapshot.update(overrides)
    snapshot["sources_enabled"] = normalize_sources_enabled(
        overrides.get("sources_enabled"),
        default=normalize_sources_enabled(preference.sources_enabled),
    )
    return snapshot


def _rent_near_miss_tolerance(max_price: float) -> float:
    return max(max_price * 0.1, 200.0)


def classify_listing(  # noqa: C901
    listing: Listing,
    filters: dict[str, Any],
    *,
    effective_score: float | None,
) -> tuple[str, list[dict[str, Any]], str]:
    """Return (category, structured_reasons, short_explanation)."""
    f = merge_filters(filters)
    reasons: list[dict[str, Any]] = []

    max_price = f.get("max_price")
    if isinstance(max_price, (int, float)) and max_price > 0:
        over_by = float(listing.price) - float(max_price)
        if over_by > _rent_near_miss_tolerance(float(max_price)):
            reasons.append(
                {
                    "filter_code": "max_rent",
                    "label": "Max rent",
                    "expected": f"<=${max_price:.0f}",
                    "actual": f"${listing.price:.0f}",
                    "severity": "hard_fail",
                    "suggestion": "Raise max rent or tighten search to smaller units",
                }
            )
            return "filtered_out", reasons, "Outside max rent tolerance"
        if over_by > 0:
            reasons.append(
                {
                    "filter_code": "max_rent_near",
                    "label": "Max rent (near miss)",
                    "expected": f"<=${max_price:.0f}",
                    "actual": f"${listing.price:.0f}",
                    "severity": "near_miss",
                    "suggestion": f"Raising budget by ~${over_by:.0f} would include this listing",
                }
            )

    min_bedrooms = f.get("min_bedrooms")
    if isinstance(min_bedrooms, int) and min_bedrooms > 0:
        beds = listing.bedrooms
        if beds is None:
            reasons.append(
                {
                    "filter_code": "bedrooms_unknown",
                    "label": "Bedrooms",
                    "expected": f">={min_bedrooms}",
                    "actual": "unknown",
                    "severity": "near_miss",
                    "suggestion": "Confirm bedroom count on the listing page",
                }
            )
        elif beds < min_bedrooms - 1:
            reasons.append(
                {
                    "filter_code": "min_bedrooms",
                    "label": "Bedrooms",
                    "expected": f">={min_bedrooms}",
                    "actual": str(beds),
                    "severity": "hard_fail",
                    "suggestion": "Lower bedroom minimum slightly if flex space works",
                }
            )
            return "filtered_out", reasons, "Too few bedrooms"
        elif beds < min_bedrooms:
            reasons.append(
                {
                    "filter_code": "min_bedrooms_near",
                    "label": "Bedrooms (near miss)",
                    "expected": f">={min_bedrooms}",
                    "actual": str(beds),
                    "severity": "near_miss",
                    "suggestion": "One fewer bedroom may unlock similar locations",
                }
            )

    min_bathrooms = f.get("min_bathrooms")
    if isinstance(min_bathrooms, (int, float)) and float(min_bathrooms) > 0:
        min_b = float(min_bathrooms)
        baths = listing.bathrooms
        if baths is None:
            reasons.append(
                {
                    "filter_code": "bathrooms_unknown",
                    "label": "Bathrooms",
                    "expected": f">={min_bathrooms}",
                    "actual": "unknown",
                    "severity": "near_miss",
                    "suggestion": "Confirm bathroom count on the listing page",
                }
            )
        elif baths < min_b - 0.5:
            reasons.append(
                {
                    "filter_code": "min_bathrooms",
                    "label": "Bathrooms",
                    "expected": f">={min_bathrooms}",
                    "actual": str(baths),
                    "severity": "hard_fail",
                    "suggestion": "Relax bathroom minimum if acceptable",
                }
            )
            return "filtered_out", reasons, "Too few bathrooms"
        elif baths < min_b:
            reasons.append(
                {
                    "filter_code": "min_bathrooms_near",
                    "label": "Bathrooms (near miss)",
                    "expected": f">={min_bathrooms}",
                    "actual": str(baths),
                    "severity": "near_miss",
                    "suggestion": "Half-bath flexibility may be enough day-to-day",
                }
            )

    if f.get("pets_required"):
        if listing.pets_policy == "unknown":
            reasons.append(
                {
                    "filter_code": "pets_unknown",
                    "label": "Pet policy",
                    "expected": "pet-friendly",
                    "actual": "unknown",
                    "severity": "near_miss",
                    "suggestion": "Review unknown pet policies instead of assuming failure",
                }
            )
        elif listing.pets_policy == "none_allowed":
            reasons.append(
                {
                    "filter_code": "pets",
                    "label": "Pet policy",
                    "expected": "pet-friendly",
                    "actual": listing.pets_policy,
                    "severity": "hard_fail",
                    "suggestion": "Pet-friendly listings only",
                }
            )
            return "filtered_out", reasons, "Pets not allowed"

    if any(r.get("severity") == "near_miss" for r in reasons):
        return "near_miss", reasons, "Borderline on one or more filters"

    score = effective_score if effective_score is not None else 0.55
    great = float(f.get("score_great_threshold", 0.8))
    worth = float(f.get("score_worth_threshold", 0.5))
    if score >= great:
        return "great_match", [], f"Strong match (score {score:.2f})"
    if score >= worth:
        return "worth_a_look", [], f"Decent match (score {score:.2f})"
    reasons.append(
        {
            "filter_code": "low_score",
            "label": "Preference match",
            "expected": f">={worth:.2f}",
            "actual": f"{score:.2f}",
            "severity": "soft_fail",
            "suggestion": "Tune scored preferences or rescore after extraction stabilizes",
        }
    )
    return "filtered_out", reasons, "Below match threshold"


async def persist_listing_classification(
    session: AsyncSession,
    *,
    run: SearchRun,
    listing: Listing,
    preference: Preference | None,
    emitter: run_events.SearchRunEventEmitter | None = None,
) -> RunListingResult:
    await session.execute(
        delete(RunListingResult).where(
            RunListingResult.run_id == run.id,
            RunListingResult.listing_id == listing.id,
            RunListingResult.revision == run.active_revision,
        )
    )
    filters = {}
    if run.filters_json:
        try:
            filters = json.loads(run.filters_json)
        except json.JSONDecodeError:
            filters = {}
    eff_score = listing.score
    if eff_score is None and preference is not None:
        eff_score = heuristic_listing_score(listing, preference).score

    category, reasons, explanation = classify_listing(listing, filters, effective_score=eff_score)
    row = RunListingResult(
        id=str(uuid.uuid4()),
        run_id=run.id,
        listing_id=listing.id,
        revision=run.active_revision,
        category=category,
        score=eff_score,
        filter_reasons_json=json.dumps(reasons) if reasons else None,
        explanation=explanation,
    )
    session.add(row)
    await _refresh_category_counters(session, run)
    if emitter:
        # Demote the internal filter event to developer-only
        await emitter.emit(
            "hard_filters_applied",
            "Hard filters evaluated",
            payload={"listing_id": listing.id, "category": category},
            visibility="developer",
        )
        short_addr = (listing.address or "listing")[:50]
        price_str = f"${listing.price:,.0f}/mo" if listing.price else ""
        if category == "great_match":
            await emitter.emit(
                "listing_found",
                f"✓ Great match: {short_addr} {price_str}",
                stage="scraping",
                payload={
                    "listing_id": listing.id,
                    "category": category,
                    "address": listing.address,
                    "price": listing.price,
                },
            )
        elif category == "worth_a_look":
            await emitter.emit(
                "listing_found",
                f"Worth a look: {short_addr} {price_str}",
                stage="scraping",
                payload={
                    "listing_id": listing.id,
                    "category": category,
                    "address": listing.address,
                    "price": listing.price,
                },
            )
        elif category == "near_miss":
            await emitter.emit(
                "listing_classified_near_miss",
                explanation,
                payload={"listing_id": listing.id, "category": category},
                visibility="developer",
            )
        else:
            await emitter.emit(
                "listing_classified_rejected",
                explanation,
                payload={"listing_id": listing.id, "category": category},
                visibility="developer",
            )
    await run_suggestions.refresh_suggestions(session, run_id=run.id, emitter=emitter)
    await session.flush()
    return row


async def _refresh_category_counters(session: AsyncSession, run: SearchRun) -> None:
    rev = run.active_revision
    stmt = select(RunListingResult).where(
        RunListingResult.run_id == run.id, RunListingResult.revision == rev
    )
    rows = list((await session.execute(stmt)).scalars().all())
    gm = wo = nm = fo = 0
    for r in rows:
        if r.category == "great_match":
            gm += 1
        elif r.category == "worth_a_look":
            wo += 1
        elif r.category == "near_miss":
            nm += 1
        elif r.category == "filtered_out":
            fo += 1
    run.great_matches = gm
    run.worth_a_look = wo
    run.near_misses = nm
    run.filtered_out = fo
    session.add(run)


async def classify_city_listings_for_run(
    session: AsyncSession,
    *,
    run: SearchRun,
    city: str,
    preference: Preference | None,
    emitter: run_events.SearchRunEventEmitter | None = None,
) -> int:
    """Classify all listings for a city under the current revision; returns rows written."""
    await session.execute(
        delete(RunListingResult).where(
            RunListingResult.run_id == run.id,
            RunListingResult.revision == run.active_revision,
        )
    )
    stmt = (
        select(Listing)
        .join(PropertyManager, Listing.property_manager_id == PropertyManager.id)
        .where(PropertyManager.city == city)
    )
    listings = list((await session.execute(stmt)).scalars().all())
    count = 0
    for listing in listings:
        await persist_listing_classification(
            session, run=run, listing=listing, preference=preference, emitter=emitter
        )
        count += 1
    await session.flush()
    logger.info("run_listings_classified", run_id=run.id, city=city, count=count)
    return count
