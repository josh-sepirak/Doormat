"""Pydantic request/response models for API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

# ============================================================================
# Preferences
# ============================================================================


class PreferenceCreate(BaseModel):
    """Create a new preference."""

    description: str = Field(..., min_length=10, max_length=1000)
    city: str = Field(..., min_length=2, max_length=100)


class PreferenceUpdate(BaseModel):
    """Update an existing preference."""

    description: Optional[str] = Field(None, min_length=10, max_length=1000)
    city: Optional[str] = Field(None, min_length=2, max_length=100)


class PreferenceResponse(BaseModel):
    """Preference response model."""

    id: str
    description: str
    city: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Property Managers
# ============================================================================


class PropertyManagerResponse(BaseModel):
    """Property manager response model."""

    id: str
    city: str
    name: str
    website: Optional[str] = None
    listing_page_url: Optional[str] = None
    validated: bool
    discovery_timestamp: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Extraction Strategies
# ============================================================================


class ExtractionStrategyResponse(BaseModel):
    """Extraction strategy response model."""

    id: str
    property_manager_id: str
    strategy_json: str
    tier1_model: Optional[str] = None
    tier2_model: Optional[str] = None
    validation_rate: float
    last_refined: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================================
# Listings
# ============================================================================


class ListingCreate(BaseModel):
    """Create a new listing."""

    property_manager_id: str
    address: str
    bedrooms: Optional[int] = None
    price: float = Field(..., gt=0)
    url: str
    raw_data: Optional[str] = None


class ListingResponse(BaseModel):
    """Listing response model."""

    id: str
    property_manager_id: str
    preference_id: Optional[str] = None
    address: str
    bedrooms: Optional[int] = None
    price: float
    url: str
    extraction_timestamp: datetime
    extraction_model: Optional[str] = None
    tier1_cost: Optional[float] = None
    tier2_cost: Optional[float] = None
    validation_passed: bool

    class Config:
        from_attributes = True


class ListingFilterParams(BaseModel):
    """Listing filter parameters."""

    city: Optional[str] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    min_bedrooms: Optional[int] = Field(None, ge=0)
    max_bedrooms: Optional[int] = Field(None, ge=0)
    validated_only: bool = False
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


# ============================================================================
# Costs
# ============================================================================


class CostResponse(BaseModel):
    """Cost tracking response model."""

    id: str
    component: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    cache_hit: bool
    timestamp: datetime
    city: Optional[str] = None

    class Config:
        from_attributes = True


class CostBreakdown(BaseModel):
    """Cost breakdown summary."""

    total_cost_usd: float
    call_count: int
    tokens_total: int
    cache_hit_count: int
    cache_hit_rate: float
    by_component: dict[str, float]
    by_model: dict[str, float]


# ============================================================================
# Health
# ============================================================================


class HealthCheck(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: Optional[str] = None
