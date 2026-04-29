"""FastMCP server exposing Doormat as an MCP tool provider.

Run with:
    doormat-mcp              # stdio transport (default, for Claude Desktop)
    doormat-mcp --http       # HTTP/SSE transport on http://localhost:8001

Tools exposed:
    search_listings  — query listings with optional filters
    get_listing      — fetch a single listing by ID
    explain_score    — explain why a listing got its score
    trigger_scrape   — launch a discovery run for a city+preference
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, Optional

import structlog
from fastmcp import FastMCP

from doormat.db.base import AsyncSessionLocal
from doormat.models.orm import Listing, Preference, PropertyManager
from doormat.runs import filters as run_filters
from doormat.scoring.scorer import ListingScorer, build_listing_scoring_prompt

logger = structlog.get_logger(__name__)

mcp = FastMCP(
    name="doormat",
    instructions=(
        "Doormat is an AI-first rental finder. "
        "Use search_listings to query saved listings, get_listing for detail, "
        "explain_score to understand a match score, and trigger_scrape to kick off "
        "a new discovery run for a city."
    ),
)


# ---------------------------------------------------------------------------
# search_listings
# ---------------------------------------------------------------------------


@mcp.tool()
async def search_listings(
    city: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_bedrooms: Optional[int] = None,
    pets_allowed: Optional[bool] = None,
    min_score: Optional[float] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search saved rental listings with optional filters.

    Returns up to *limit* listings ordered by score descending.
    All filter arguments are optional.

    Args:
        city: Filter by city name (case-insensitive substring match).
        min_price: Minimum monthly rent in USD.
        max_price: Maximum monthly rent in USD.
        min_bedrooms: Minimum number of bedrooms.
        pets_allowed: If True, exclude listings with pets_policy=none_allowed.
        min_score: Minimum match score (0.0–1.0).
        limit: Maximum number of results to return (default 20, max 100).
    """
    from sqlalchemy import select

    limit = min(limit, 100)

    async with AsyncSessionLocal() as session:
        stmt = select(Listing)

        if city is not None:
            stmt = stmt.join(PropertyManager).where(PropertyManager.city.ilike(f"%{city.strip()}%"))
        if min_price is not None:
            stmt = stmt.where(Listing.price >= min_price)
        if max_price is not None:
            stmt = stmt.where(Listing.price <= max_price)
        if min_bedrooms is not None:
            stmt = stmt.where(Listing.bedrooms >= min_bedrooms)
        if pets_allowed is True:
            stmt = stmt.where(Listing.pets_policy != "none_allowed")
        if min_score is not None:
            stmt = stmt.where(Listing.score >= min_score)

        stmt = stmt.order_by(
            Listing.score.desc().nulls_last(),
            Listing.extraction_timestamp.desc(),
        ).limit(limit)

        result = await session.execute(stmt)
        listings = result.scalars().all()

    return [_listing_summary(listing) for listing in listings]


# ---------------------------------------------------------------------------
# get_listing
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_listing(listing_id: str) -> dict[str, Any]:
    """Fetch a single listing by its ID.

    Returns full listing detail including score, explanation, amenities, and photos.

    Args:
        listing_id: The UUID of the listing.
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Listing).where(Listing.id == listing_id))
        listing = result.scalar_one_or_none()

    if listing is None:
        return {"error": f"Listing {listing_id!r} not found"}

    return _listing_detail(listing)


# ---------------------------------------------------------------------------
# explain_score
# ---------------------------------------------------------------------------


@mcp.tool()
async def explain_score(listing_id: str, preference_id: str) -> dict[str, Any]:
    """Explain why a listing received its match score against a preference.

    If the listing has not been scored yet, scores it on demand (requires an
    OpenRouter API key stored in the preference).

    Args:
        listing_id: UUID of the listing to explain.
        preference_id: UUID of the preference to score against.
    """
    async with AsyncSessionLocal() as session:
        listing = await session.get(Listing, listing_id)
        preference = await session.get(Preference, preference_id)

    if listing is None:
        return {"error": f"Listing {listing_id!r} not found"}
    if preference is None:
        return {"error": f"Preference {preference_id!r} not found"}

    if listing.score is not None and listing.score_explanation:
        return {
            "listing_id": listing_id,
            "score": listing.score,
            "explanation": listing.score_explanation,
            "preference_summary": preference.description[:200],
            "prompt_used": build_listing_scoring_prompt(listing, preference)[:500] + "...",
        }

    # Score on demand
    try:
        scorer = ListingScorer()
        scored = await scorer.score(listing, preference)

        async with AsyncSessionLocal() as session:
            db_listing = await session.get(Listing, listing_id)
            if db_listing is not None:
                db_listing.score = scored.score
                db_listing.score_explanation = scored.explanation
                await session.commit()

        return {
            "listing_id": listing_id,
            "score": scored.score,
            "explanation": scored.explanation,
            "preference_summary": preference.description[:200],
            "freshly_scored": True,
        }
    except Exception as exc:
        logger.error("mcp_explain_score_failed", listing_id=listing_id, error=str(exc))
        return {"error": f"Scoring failed: {exc}"}


# ---------------------------------------------------------------------------
# trigger_scrape
# ---------------------------------------------------------------------------


@mcp.tool()
async def trigger_scrape(
    city: str,
    preference_id: Optional[str] = None,
) -> dict[str, Any]:
    """Launch a discovery run to find property managers and listings for a city.

    Creates a SearchRun + DiscoveryRun in the database and starts the pipeline
    in the background. Returns immediately with a run_id.

    Poll progress via the REST API at /api/runs/{run_id}.

    Args:
        city: City to search (e.g. "Austin, TX").
        preference_id: Optional preference UUID — used to apply the stored
            OpenRouter key and scoring model.
    """
    import uuid
    from datetime import UTC, datetime

    from doormat.models.orm import DiscoveryRun, SearchRun
    from doormat.runs import events as run_events

    cleaned = city.strip()
    if not cleaned:
        return {"error": "city must not be empty"}

    if preference_id:
        async with AsyncSessionLocal() as session:
            pref = await session.get(Preference, preference_id)
        if pref is None:
            return {"error": f"Preference {preference_id!r} not found"}

    discovery_id = str(uuid.uuid4())
    search_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        pref = None
        if preference_id:
            pref = await session.get(Preference, preference_id)
        filter_snapshot = run_filters.build_run_filter_snapshot(pref)
        session.add(
            DiscoveryRun(
                id=discovery_id,
                city=cleaned,
                preference_id=preference_id,
                status="running",
                started_at=now,
            )
        )
        session.add(
            SearchRun(
                id=search_id,
                discovery_run_id=discovery_id,
                city=cleaned,
                preference_id=preference_id,
                status="running",
                current_stage="discovery",
                cancel_requested=False,
                started_at=now,
                filters_json=json.dumps(filter_snapshot),
            )
        )
        await session.commit()

    await run_events.append_search_run_event_standalone(
        run_id=search_id,
        event_type="run_started",
        message=f"MCP-triggered scrape for {cleaned}",
        stage="discovery",
        payload={"city": cleaned, "preference_id": preference_id, "triggered_by": "mcp"},
    )

    async def _run() -> None:
        try:
            async with AsyncSessionLocal():
                from doormat.api.routers.search_runs import _run_discovery_background

                await _run_discovery_background(discovery_id, cleaned, preference_id, search_id)
        except Exception as exc:
            logger.error(
                "mcp_trigger_scrape_failed", city=cleaned, search_id=search_id, error=str(exc)
            )

    asyncio.create_task(_run())

    logger.info("mcp_trigger_scrape_started", city=cleaned, search_id=search_id)
    return {
        "status": "started",
        "city": cleaned,
        "search_run_id": search_id,
        "discovery_run_id": discovery_id,
        "poll_url": f"/api/runs/{search_id}",
    }


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed: Any = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if isinstance(item, str)]


def _listing_summary(listing: Listing) -> dict[str, Any]:
    return {
        "id": listing.id,
        "address": listing.address,
        "price": listing.price,
        "bedrooms": listing.bedrooms,
        "bathrooms": listing.bathrooms,
        "pets_policy": listing.pets_policy,
        "score": listing.score,
        "score_explanation": listing.score_explanation,
        "url": listing.url,
        "source": listing.source or "pm_direct",
    }


def _listing_detail(listing: Listing) -> dict[str, Any]:
    return {
        **_listing_summary(listing),
        "sqft": listing.sqft,
        "description": listing.description,
        "amenities": _json_list(listing.amenities),
        "photos": _json_list(listing.photos),
        "latitude": listing.latitude,
        "longitude": listing.longitude,
        "extraction_timestamp": (
            listing.extraction_timestamp.isoformat() if listing.extraction_timestamp else None
        ),
        "extraction_model": listing.extraction_model,
        "validation_passed": listing.validation_passed,
        "saved": listing.saved,
        "property_manager_id": listing.property_manager_id,
        "preference_id": listing.preference_id,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run() -> None:
    """Console-script entry point for doormat-mcp."""
    parser = argparse.ArgumentParser(description="Doormat MCP server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run HTTP/SSE transport on http://localhost:8001 instead of stdio",
    )
    parser.add_argument("--port", type=int, default=8001, help="Port for --http mode")
    args = parser.parse_args()

    if args.http:
        mcp.run(transport="sse", port=args.port)
    else:
        mcp.run()
