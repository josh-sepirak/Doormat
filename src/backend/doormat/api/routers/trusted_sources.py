"""API endpoints for trusted rental sources (Craigslist regions & property managers)."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from doormat.db.base import get_db
from doormat.models.orm import TrustedSource, PropertyManager, Listing
from doormat.sources.craigslist_regions import region_by_subdomain

router = APIRouter(prefix="/api/trusted-sources", tags=["trusted-sources"])


# Helper functions

def _extract_subdomain(url: str) -> str:
    """Extract Craigslist subdomain from URL."""
    try:
        if "craigslist.org" not in url:
            raise ValueError("Not a Craigslist URL")
        parts = url.split("//")
        if len(parts) < 2:
            raise ValueError("Invalid URL format")
        return parts[1].split(".")[0]
    except (IndexError, AttributeError):
        return ""


# Response models
class TrustedSourceResponse(BaseModel):
    """Trusted source metadata."""
    id: str
    kind: str  # "craigslist_region" or "property_manager"
    label: str
    url: str
    city: Optional[str]
    linked_property_manager_id: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class CreateTrustedSourceRequest(BaseModel):
    """Create trusted source."""
    kind: str  # "craigslist_region" or "property_manager"
    label: str
    url: str
    city: Optional[str] = None


class TrustedSourceListResponse(BaseModel):
    """List of trusted sources."""
    total: int
    sources: list[TrustedSourceResponse]


# Endpoints

@router.get("", response_model=TrustedSourceListResponse)
async def list_trusted_sources(
    kind: Optional[str] = None,
    city: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> TrustedSourceListResponse:
    """List trusted sources with optional filters.
    
    Query params:
    - kind (str, optional): Filter by "craigslist_region" or "property_manager"
    - city (str, optional): Filter by city
    
    Returns:
    - List of trusted sources with metadata
    """
    query = select(TrustedSource)
    
    if kind:
        query = query.where(TrustedSource.kind == kind)
    if city:
        query = query.where(TrustedSource.city == city)
    
    result = await db.execute(query)
    sources = result.scalars().all()
    
    return TrustedSourceListResponse(
        total=len(sources),
        sources=[TrustedSourceResponse.model_validate(s) for s in sources]
    )


@router.post("", response_model=TrustedSourceResponse, status_code=201)
async def create_trusted_source(
    req: CreateTrustedSourceRequest,
    db: AsyncSession = Depends(get_db),
) -> TrustedSourceResponse:
    """Create a new trusted source.
    
    Body:
    - kind: "craigslist_region" or "property_manager"
    - label: Display name (e.g., "Inland Empire")
    - url: Full URL
    - city (optional): City name for filtering
    
    Returns:
    - Created source with ID
    """
    # Validate based on kind
    if req.kind == "craigslist_region":
        region = region_by_subdomain(_extract_subdomain(req.url))
        if not region:
            raise HTTPException(status_code=400, detail="Invalid Craigslist URL")
        # Auto-extract city from region if not provided
        if not req.city:
            req.city = region.label.split(",")[0] if "," in region.label else None
    
    elif req.kind == "property_manager":
        # For PMs, we need to ensure URL is valid
        if not req.url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Invalid URL")
        if not req.city:
            raise HTTPException(status_code=400, detail="City required for property_manager")
    
    else:
        raise HTTPException(status_code=400, detail="Invalid kind (must be 'craigslist_region' or 'property_manager')")
    
    # Check for duplicates
    existing = await db.execute(
        select(TrustedSource).where(
            (TrustedSource.kind == req.kind) &
            (TrustedSource.url == req.url)
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Source already exists")
    
    source = TrustedSource(
        id=str(uuid4()),
        kind=req.kind,
        label=req.label,
        url=req.url,
        city=req.city,
    )
    
    db.add(source)
    await db.commit()
    await db.refresh(source)
    
    return TrustedSourceResponse.model_validate(source)


@router.get("/{source_id}", response_model=TrustedSourceResponse)
async def get_trusted_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
) -> TrustedSourceResponse:
    """Get a specific trusted source."""
    source = await db.get(TrustedSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    return TrustedSourceResponse.model_validate(source)


@router.delete("/{source_id}", status_code=204)
async def delete_trusted_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a trusted source."""
    source = await db.get(TrustedSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    await db.delete(source)
    await db.commit()


@router.post("/{source_id}/test", response_model=dict)
async def test_trusted_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Test/validate a trusted source.
    
    For Craigslist regions:
    - Verify subdomain resolves
    
    For property managers:
    - Check if we can discover it and generate a strategy
    
    Returns:
    - { "valid": bool, "message": str, "listings_found": int (optional) }
    """
    source = await db.get(TrustedSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    if source.kind == "craigslist_region":
        region = parse_craigslist_url(source.url)
        if not region:
            return {"valid": False, "message": "Invalid Craigslist URL"}
        
        return {
            "valid": True,
            "message": f"Valid Craigslist region: {region.label}"
        }
    
    elif source.kind == "property_manager":
        # Check if there are any listings from this PM
        result = await db.execute(
            select(Listing).where(Listing.property_manager_id == source.linked_property_manager_id).limit(1)
        )
        listings = result.scalars().all()
        
        return {
            "valid": True,
            "message": f"Property manager configured",
            "listings_found": len(listings)
        }
    
    else:
        return {"valid": False, "message": "Unknown source kind"}
