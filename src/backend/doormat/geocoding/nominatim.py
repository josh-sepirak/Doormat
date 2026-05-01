"""Forward geocoding via Nominatim (OpenStreetMap).

Use a stable User-Agent and SQLite cache to stay within fair-use policy:
https://operations.osmfoundation.org/policies/nominatim/
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Optional

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.models.orm import GeocodeCache, Listing, PropertyManager

logger = structlog.get_logger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "DoormatRentalFinder/1.0 (self-hosted; https://github.com/)"
TIMEOUT_S = 12.0


def _cache_key(query: str) -> str:
    normalized = " ".join(query.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def geocode_listing(session: AsyncSession, listing_id: str) -> tuple[Optional[float], Optional[float]]:
    """Return (lat, lon) for a listing, using DB cache or Nominatim. Persists coords on success."""
    result = await session.execute(
        select(Listing, PropertyManager.city)
        .join(PropertyManager, Listing.property_manager_id == PropertyManager.id)
        .where(Listing.id == listing_id)
    )
    row = result.one_or_none()
    if row is None:
        return None, None
    listing, pm_city = row

    if listing.latitude is not None and listing.longitude is not None:
        return listing.latitude, listing.longitude

    query = f"{listing.address}, {pm_city}"
    key = _cache_key(query)

    cached = await session.get(GeocodeCache, key)
    if cached is not None:
        listing.latitude = cached.latitude
        listing.longitude = cached.longitude
        await session.commit()
        return cached.latitude, cached.longitude

    params = {"q": query, "format": "json", "limit": "1"}
    headers = {"User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("nominatim_request_failed", listing_id=listing_id, error=str(exc))
        return None, None

    if not isinstance(data, list) or not data:
        logger.info("nominatim_no_results", listing_id=listing_id, query=query[:120])
        return None, None

    first = data[0]
    try:
        lat = float(first["lat"])
        lon = float(first["lon"])
    except (KeyError, TypeError, ValueError):
        logger.warning("nominatim_bad_payload", listing_id=listing_id)
        return None, None

    session.add(
        GeocodeCache(
            cache_key=key,
            query_text=query[:512],
            latitude=lat,
            longitude=lon,
            created_at=datetime.now(UTC),
        )
    )
    listing.latitude = lat
    listing.longitude = lon
    await session.commit()
    logger.info("listing_geocoded", listing_id=listing_id, lat=lat, lon=lon)
    return lat, lon
