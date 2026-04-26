"""Listing API endpoints."""

import asyncio
import json
from typing import AsyncIterator, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.db.base import get_db
from doormat.models.orm import Listing
from doormat.schemas import ListingResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/listings", tags=["listings"])


def _serialize_listing(listing: Listing) -> dict:
    amenities: list[str] = json.loads(listing.amenities or "[]")
    photos: list[str] = json.loads(listing.photos or "[]")
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
    city: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_bedrooms: Optional[int] = Query(None, ge=0),
    max_bedrooms: Optional[int] = Query(None, ge=0),
    saved_only: bool = Query(False),
    min_score: Optional[float] = Query(None, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return paginated, filterable listings."""
    stmt = select(Listing)

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

    return [_serialize_listing(l) for l in listings]


@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: str,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return a single listing by ID."""
    result = await session.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return _serialize_listing(listing)


@router.post("/{listing_id}/save", response_model=ListingResponse)
async def toggle_save_listing(
    listing_id: str,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Toggle the saved state of a listing."""
    result = await session.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing.saved = not listing.saved
    await session.commit()

    logger.info("listing_save_toggled", listing_id=listing_id, saved=listing.saved)
    return _serialize_listing(listing)


@router.get("/stream", response_class=StreamingResponse)
async def stream_listings(
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """SSE stream — push new listings as they arrive."""

    async def _event_generator() -> AsyncIterator[str]:
        last_seen_id: str | None = None
        while True:
            stmt = select(Listing).order_by(Listing.extraction_timestamp.desc()).limit(20)
            result = await session.execute(stmt)
            listings = result.scalars().all()

            for listing in reversed(listings):
                if last_seen_id is None or listing.id != last_seen_id:
                    payload = json.dumps(_serialize_listing(listing), default=str)
                    yield f"data: {payload}\n\n"

            if listings:
                last_seen_id = listings[0].id

            await asyncio.sleep(5)

    return StreamingResponse(_event_generator(), media_type="text/event-stream")
