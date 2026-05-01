"""Heuristic fallback scoring for listings when LLM is unavailable."""

import math
from dataclasses import dataclass


@dataclass
class HeuristicScore:
    """Result of heuristic scoring."""

    score: float
    reason: str


def score_heuristic(
    address: str,
    price: int | None,
    bedrooms: int | None,
    bathrooms: float | None,
    preference_max_price: int | None,
    preference_min_bedrooms: int | None,
    preference_min_bathrooms: float | None,
    preference_pets_required: bool | None,
    preference_walkable: bool | None,
) -> HeuristicScore:
    """
    Simple rule-based scoring fallback.

    Evaluates common filters without LLM. Returns score 0-1 + reason.
    """
    matches = []
    misses = []
    bonus_points = 0

    # Price: critical filter
    if price is not None and preference_max_price is not None:
        if price <= preference_max_price:
            matches.append(f"price ${price} ≤ ${preference_max_price} budget")
        else:
            overage_pct = ((price - preference_max_price) / preference_max_price) * 100
            if overage_pct < 10:
                matches.append(
                    f"price ${price} only {overage_pct:.0f}% over ${preference_max_price}"
                )
                bonus_points += 0.05
            else:
                misses.append(f"price ${price} is ${price - preference_max_price} over")

    # Bedrooms
    if bedrooms is not None and preference_min_bedrooms is not None:
        if bedrooms >= preference_min_bedrooms:
            matches.append(f"{bedrooms} bedrooms ≥ {preference_min_bedrooms} requested")
        else:
            misses.append(f"{bedrooms} bedrooms < {preference_min_bedrooms} requested")

    # Bathrooms
    if bathrooms is not None and preference_min_bathrooms is not None:
        if bathrooms >= preference_min_bathrooms:
            matches.append(
                f"{bathrooms} bathrooms ≥ {preference_min_bathrooms} requested"
            )
        else:
            misses.append(f"{bathrooms} baths < {preference_min_bathrooms} requested")

    # Walkability signal (crude: check address for common walkable neighborhood keywords)
    walkable_keywords = ["downtown", "mission", "inner", "central", "commercial"]
    if preference_walkable and any(kw in address.lower() for kw in walkable_keywords):
        matches.append("appears in walkable neighborhood (keyword match)")
        bonus_points += 0.05

    # Pets: binary check (can't really verify from listing data)
    if preference_pets_required is not None:
        if preference_pets_required:
            misses.append("pet requirement noted but not verifiable from listing data")
        else:
            matches.append("no pet requirement")

    # Calculate score
    if not matches and misses:
        base_score = 0.2  # Some credit for having listing data
    elif matches and not misses:
        base_score = 0.80 + bonus_points  # Strong match
    elif matches and misses:
        # Partial match: scale by ratio
        match_ratio = len(matches) / (len(matches) + len(misses))
        base_score = 0.4 + (match_ratio * 0.4) + bonus_points
    else:
        base_score = 0.5  # No strong signal

    base_score = min(1.0, max(0.0, base_score))

    reason_parts = []
    if matches:
        reason_parts.append("; ".join(matches))
    if misses:
        reason_parts.append("concerns: " + "; ".join(misses))

    reason = " | ".join(reason_parts) if reason_parts else "No strong match or mismatch signals"

    return HeuristicScore(score=base_score, reason=reason)
