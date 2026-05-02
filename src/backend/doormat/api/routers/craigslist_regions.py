"""Suggest nearest Craigslist regional sites from geocoded city + state."""

from __future__ import annotations

import re
from typing import Annotated, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.db.base import get_db
from doormat.geocoding.nominatim import geocode_place
from doormat.security.auth import require_bearer_auth
from doormat.sources.craigslist_regions import nearest_regions, region_by_subdomain

router = APIRouter(
    prefix="/api/craigslist/regions",
    tags=["craigslist"],
    dependencies=[Depends(require_bearer_auth)],
)
DbSession = Annotated[AsyncSession, Depends(get_db)]


class GeocodedOut(BaseModel):
    lat: float
    lon: float
    display_name: str


class SuggestionOut(BaseModel):
    subdomain: str
    label: str
    url: str
    distance_mi: float


class RegionsResponse(BaseModel):
    geocoded: GeocodedOut
    suggestions: list[SuggestionOut]


class ParseUrlBody(BaseModel):
    url: str = Field(min_length=4, max_length=512)


class ParseUrlResponse(BaseModel):
    subdomain: str
    label: str
    url: str
    valid: bool
    error: Optional[str] = None


def _parse_cl_subdomain(raw: str) -> tuple[str, str, str] | None:
    """Return (subdomain, canonical_url, label) or None if invalid."""
    s = raw.strip()
    if not s:
        return None
    if "://" not in s:
        s = "https://" + s
    try:
        p = urlparse(s)
    except ValueError:
        return None
    if p.scheme not in ("http", "https"):
        return None
    host = (p.netloc or "").lower()
    if not host.endswith(".craigslist.org"):
        return None
    parts = host.split(".")
    if len(parts) < 3 or parts[0] == "":
        return None
    sub = parts[0]
    if not re.match(r"^[a-z0-9-]+$", sub):
        return None
    canon = f"https://{sub}.craigslist.org"
    reg = region_by_subdomain(sub)
    label = reg.label if reg else sub
    return sub, canon, label


@router.get("", response_model=RegionsResponse)
async def suggest_regions(
    session: DbSession,
    city: str = Query(..., min_length=1, max_length=100),
    state: str = Query(..., min_length=2, max_length=32),
) -> RegionsResponse:
    st = state.strip().upper()
    if len(st) == 2:
        q = f"{city.strip()}, {st}, USA"
    else:
        q = f"{city.strip()}, {state.strip()}"
    geo = await geocode_place(session, q)
    if geo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not geocode that place. Try a more specific city and state.",
        )
    lat, lon = float(geo["lat"]), float(geo["lon"])
    ranked = nearest_regions(lat, lon, k=3)
    if not ranked:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Craigslist region catalog failed to load",
        )
    suggestions = [
        SuggestionOut(
            subdomain=r.subdomain,
            label=r.label,
            url=r.url,
            distance_mi=round(d, 1),
        )
        for r, d in ranked
    ]
    return RegionsResponse(
        geocoded=GeocodedOut(
            lat=lat,
            lon=lon,
            display_name=str(geo.get("display_name") or q),
        ),
        suggestions=suggestions,
    )


@router.post("/parse", response_model=ParseUrlResponse)
async def parse_region_url(body: ParseUrlBody) -> ParseUrlResponse:
    parsed = _parse_cl_subdomain(body.url)
    if parsed is None:
        return ParseUrlResponse(
            subdomain="",
            label="",
            url="",
            valid=False,
            error="Enter a craigslist.org URL or subdomain (e.g. inlandempire or https://inlandempire.craigslist.org).",
        )
    sub, canon, label = parsed
    return ParseUrlResponse(subdomain=sub, label=label, url=canon, valid=True, error=None)
