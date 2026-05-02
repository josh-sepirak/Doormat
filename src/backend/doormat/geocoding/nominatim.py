"""Forward geocoding via Nominatim (OpenStreetMap).

Use a stable User-Agent and SQLite cache to stay within fair-use policy:
https://operations.osmfoundation.org/policies/nominatim/
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Optional

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


async def geocode_place(session: AsyncSession, query: str) -> dict[str, Any] | None:
    """Forward-geocode a free-text place (e.g. 'Lancaster, CA, USA'). Uses GeocodeCache."""
    q = " ".join(query.strip().split())
    if not q:
        return None
    key = _cache_key(q)
    cached = await session.get(GeocodeCache, key)
    if cached is not None:
        return {
            "lat": cached.latitude,
            "lon": cached.longitude,
            "display_name": cached.query_text[:200],
        }

    params = {"q": q, "format": "json", "limit": "1"}
    headers = {"User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("nominatim_place_geocode_failed", query=q[:120], error=str(exc))
        return None

    if not isinstance(data, list) or not data:
        logger.info("nominatim_place_no_results", query=q[:120])
        return None

    first = data[0]
    try:
        lat = float(first["lat"])
        lon = float(first["lon"])
    except (KeyError, TypeError, ValueError):
        logger.warning("nominatim_place_bad_payload", query=q[:120])
        return None
    display_name = str(first.get("display_name") or q)[:512]

    session.add(
        GeocodeCache(
            cache_key=key,
            query_text=q[:512],
            latitude=lat,
            longitude=lon,
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()

    return {"lat": lat, "lon": lon, "display_name": display_name}


async def forward_geocode(city: str, state: str) -> Optional[tuple[float, float]]:
    """Forward geocode city + state to lat/lon using Nominatim.
    
    Args:
        city: City name (e.g., "Lancaster")
        state: Two-letter state code (e.g., "CA")
    
    Returns:
        (lat, lon) tuple or None if geocoding fails
    """
    query = f"{city}, {state}, USA"
    key = _cache_key(query)
    
    # Check cache
    from doormat.db.base import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        cached = await session.get(GeocodeCache, key)
        if cached is not None:
            return (cached.latitude, cached.longitude)
    
    # Query Nominatim
    params = {"q": query, "format": "json", "limit": "1"}
    headers = {"User-Agent": USER_AGENT}
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("nominatim_forward_geocode_failed", query=query, error=str(exc))
        return None
    
    if not isinstance(data, list) or not data:
        logger.info("nominatim_forward_geocode_no_results", query=query)
        return None
    
    first = data[0]
    try:
        lat = float(first["lat"])
        lon = float(first["lon"])
    except (KeyError, TypeError, ValueError):
        logger.warning("nominatim_forward_geocode_bad_payload", query=query)
        return None
    
    # Cache result
    async with AsyncSessionLocal() as session:
        session.add(
            GeocodeCache(
                cache_key=key,
                query_text=query[:512],
                latitude=lat,
                longitude=lon,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
    
    logger.info("forward_geocoded", city=city, state=state, lat=lat, lon=lon)
    return (lat, lon)
