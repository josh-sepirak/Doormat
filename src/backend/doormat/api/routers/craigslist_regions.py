"""API endpoints for Craigslist region geocoding and suggestions."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from doormat.sources.craigslist_regions import (
    region_by_subdomain,
    nearest_regions,
)

router = APIRouter(prefix="/api/craigslist", tags=["craigslist"])


class CraigslistRegionResponse(BaseModel):
    """Craigslist region suggestion."""
    subdomain: str
    label: str
    url: str
    distance_mi: float


class RegionSuggestionsResponse(BaseModel):
    """Response for region suggestions."""
    geocoded_lat: float
    geocoded_lon: float
    suggestions: list[CraigslistRegionResponse]


class ParseRegionResponse(BaseModel):
    """Parsed Craigslist region URL."""
    subdomain: str
    label: str
    url: str
    country: str


@router.get("/regions", response_model=RegionSuggestionsResponse)
async def suggest_regions_endpoint(
    city: str,
    state: str,
    limit: int = 5,
) -> RegionSuggestionsResponse:
    """Suggest Craigslist regions based on city + state.
    
    Uses Nominatim geocoding to find representative lat/lon, then suggests
    closest Craigslist regions by distance.
    
    Query params:
    - city (str): City name (e.g., "Lancaster")
    - state (str): Two-letter state code (e.g., "CA")
    - limit (int): Max suggestions to return (default 5)
    
    Returns:
    - geocoded_lat/lon: Representative coordinates for the city
    - suggestions: List of regions sorted by distance
    """
    from doormat.geocoding.nominatim import forward_geocode
    
    # Geocode the city
    try:
        result = await forward_geocode(city, state)
        if not result:
            raise HTTPException(
                status_code=400,
                detail=f"Could not geocode {city}, {state}"
            )
        lat, lon = result
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Geocoding failed: {str(e)}"
        )
    
    # Suggest regions by distance
    scored_regions = nearest_regions(lat, lon, limit)
    
    return RegionSuggestionsResponse(
        geocoded_lat=lat,
        geocoded_lon=lon,
        suggestions=[
            CraigslistRegionResponse(
                subdomain=r.subdomain,
                label=r.label,
                url=r.url,
                distance_mi=d,
            )
            for r, d in scored_regions
        ]
    )


@router.post("/regions/parse", response_model=ParseRegionResponse)
async def parse_region_url(url: str) -> ParseRegionResponse:
    """Parse a Craigslist URL and return region metadata.
    
    Query params:
    - url (str): Full Craigslist URL (e.g., "https://inlandempire.craigslist.org")
    
    Returns:
    - subdomain, label, url, country of matched region
    """
    # Extract subdomain from URL
    try:
        if "craigslist.org" not in url:
            raise ValueError("Not a Craigslist URL")
        
        # Extract subdomain
        parts = url.split("//")
        if len(parts) < 2:
            raise ValueError("Invalid URL format")
        
        domain_part = parts[1].split(".")[0]
        region = region_by_subdomain(domain_part)
        
        if not region:
            raise ValueError(f"Unknown Craigslist subdomain: {domain_part}")
        
        return ParseRegionResponse(
            subdomain=region.subdomain,
            label=region.label,
            url=region.url,
            country=region.country,
        )
    except (IndexError, AttributeError, ValueError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid or unknown Craigslist URL: {str(e)}"
        )
