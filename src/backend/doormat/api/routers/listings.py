"""Listing API endpoints."""

import asyncio
import json
from collections.abc import Sequence
from typing import Annotated, Any, AsyncIterator, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.db.base import get_db
from doormat.models.orm import Listing, Preference, PropertyManager
from doormat.schemas import ListingResponse, ScoreListingsRequest, ScoreListingsResponse
from doormat.scoring.scorer import ListingScorer

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/listings", tags=["listings"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
SerializedListing = dict[str, Any]


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed: Any = json.loads(value)
    except json.JSONDecodeError:
        logger.warning("listing_json_decode_failed")
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if isinstance(item, str)]


def _serialize_listing(listing: Listing) -> SerializedListing:
    amenities = _json_list(listing.amenities)
    photos = _json_list(listing.photos)
    return {
        "id": listing.id,
        "property_manager_id": listing.property_manager_id,
        "preference_id": listing.preference_id,
        "address": listing.address,
        "bedrooms": listing.bedrooms,
        "bathrooms": listing.bathrooms,
        "sqft": listing.sqft,
        "price": listing.price,
        "url": listing.url,
        "pets_policy": listing.pets_policy,
        "amenities": amenities,
        "photos": photos,
        "description": listing.description,
        "extraction_timestamp": listing.extraction_timestamp,
        "extraction_model": listing.extraction_model,
        "tier1_cost": listing.tier1_cost,
        "tier2_cost": listing.tier2_cost,
        "validation_passed": listing.validation_passed,
        "score": listing.score,
        "score_explanation": listing.score_explanation,
        "saved": listing.saved,
    }


@router.get("", response_model=list[ListingResponse])
async def get_listings(
    session: DbSession,
    city: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_bedrooms: Optional[int] = Query(None, ge=0),
    max_bedrooms: Optional[int] = Query(None, ge=0),
    saved_only: bool = Query(False),
    min_score: Optional[float] = Query(None, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[SerializedListing]:
    """Return paginated, filterable listings."""
    stmt = select(Listing)

    if city is not None:
        stmt = stmt.join(PropertyManager).where(PropertyManager.city.ilike(f"%{city.strip()}%"))
    if min_price is not None:
        stmt = stmt.where(Listing.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Listing.price <= max_price)
    if min_bedrooms is not None:
        stmt = stmt.where(Listing.bedrooms >= min_bedrooms)
    if max_bedrooms is not None:
        stmt = stmt.where(Listing.bedrooms <= max_bedrooms)
    if saved_only:
        stmt = stmt.where(Listing.saved.is_(True))
    if min_score is not None:
        stmt = stmt.where(Listing.score >= min_score)

    stmt = stmt.order_by(Listing.score.desc().nulls_last(), Listing.extraction_timestamp.desc())
    stmt = stmt.offset(offset).limit(limit)

    result = await session.execute(stmt)
    listings = result.scalars().all()

    return [_serialize_listing(listing) for listing in listings]


@router.get("/stream", response_class=StreamingResponse)
async def stream_listings(
    session: DbSession,
) -> StreamingResponse:
    """SSE stream — push new listings as they arrive."""

    async def _event_generator() -> AsyncIterator[str]:
        seen_ids: set[str] = set()
        while True:
            stmt = select(Listing).order_by(Listing.extraction_timestamp.desc()).limit(20)
            result = await session.execute(stmt)
            listings: Sequence[Listing] = result.scalars().all()

            for listing in reversed(listings):
                if listing.id in seen_ids:
                    continue
                seen_ids.add(listing.id)
                payload = json.dumps(_serialize_listing(listing), default=str)
                yield f"data: {payload}\n\n"

            await asyncio.sleep(5)

    return StreamingResponse(_event_generator(), media_type="text/event-stream")


@router.post("/score", response_model=ScoreListingsResponse)
async def score_listings(
    body: ScoreListingsRequest,
    session: DbSession,
) -> ScoreListingsResponse:
    """Score persisted listings against a saved preference."""
    pref_result = await session.execute(
        select(Preference).where(Preference.id == body.preference_id)
    )
    preference = pref_result.scalar_one_or_none()
    if preference is None:
        raise HTTPException(status_code=404, detail="Preference not found")

    stmt = select(Listing).where(Listing.preference_id == body.preference_id)
    if body.listing_ids:
        stmt = stmt.where(Listing.id.in_(body.listing_ids))
    if not body.rescore:
        stmt = stmt.where(Listing.score.is_(None))
    stmt = stmt.order_by(Listing.extraction_timestamp.desc()).limit(body.limit)

    listing_result = await session.execute(stmt)
    listings = list(listing_result.scalars().all())
    await ListingScorer().score_batch(listings, preference)
    await session.commit()

    listing_ids = [listing.id for listing in listings]
    logger.info(
        "listings_scored",
        preference_id=preference.id,
        scored_count=len(listing_ids),
    )
    return ScoreListingsResponse(
        preference_id=preference.id,
        scored_count=len(listing_ids),
        listing_ids=listing_ids,
    )


@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: str,
    session: DbSession,
) -> SerializedListing:
    """Return a single listing by ID."""
    result = await session.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return _serialize_listing(listing)


@router.post("/{listing_id}/save", response_model=ListingResponse)
async def toggle_save_listing(
    listing_id: str,
    session: DbSession,
) -> SerializedListing:
    """Toggle the saved state of a listing."""
    result = await session.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing.saved = not listing.saved
    await session.commit()

    logger.info("listing_save_toggled", listing_id=listing_id, saved=listing.saved)
    return _serialize_listing(listing)
