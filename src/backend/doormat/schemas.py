"""Pydantic request/response models for API."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

# ============================================================================
# Preferences
# ============================================================================


class PreferenceCreate(BaseModel):
    """Create a new preference."""

    description: str = Field(..., min_length=10, max_length=1000)
    city: str = Field(..., min_length=2, max_length=100)
    api_provider: str = Field(default="openrouter", max_length=50)
    openrouter_api_key: Optional[str] = Field(None, max_length=255)
    apify_api_token: Optional[str] = Field(None, max_length=255)
    fast_model: Optional[str] = Field(None, max_length=150)
    smart_model: Optional[str] = Field(None, max_length=150)


class PreferenceUpdate(BaseModel):
    """Update an existing preference."""

    description: Optional[str] = Field(None, min_length=10, max_length=1000)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    api_provider: Optional[str] = Field(None, max_length=50)
    openrouter_api_key: Optional[str] = Field(None, max_length=255)
    apify_api_token: Optional[str] = Field(None, max_length=255)
    fast_model: Optional[str] = Field(None, max_length=150)
    smart_model: Optional[str] = Field(None, max_length=150)


class PreferenceResponse(BaseModel):
    """Preference response model."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    description: str
    city: str
    api_provider: str
    has_openrouter_api_key: bool = False
    openrouter_key_last4: Optional[str] = None
    has_apify_api_token: bool = False
    apify_token_last4: Optional[str] = None
    fast_model: Optional[str] = None
    smart_model: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Property Managers
# ============================================================================


class PropertyManagerResponse(BaseModel):
    """Property manager response model."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    city: str
    name: str
    website: Optional[str] = None
    listing_page_url: Optional[str] = None
    validated: bool
    discovery_timestamp: datetime


# ============================================================================
# Extraction Strategies
# ============================================================================


class ExtractionStrategyResponse(BaseModel):
    """Extraction strategy response model."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    property_manager_id: str
    strategy_json: str
    tier1_model: Optional[str] = None
    tier2_model: Optional[str] = None
    validation_rate: float
    last_refined: Optional[datetime] = None


# ============================================================================
# Listings
# ============================================================================


class PetsPolicy(str, Enum):
    ALLOWED_WITH_SMALL_DOG = "allowed_with_small_dog"
    CATS_ONLY = "cats_only"
    NONE_ALLOWED = "none_allowed"
    UNKNOWN = "unknown"


class ListingCreate(BaseModel):
    """Create a new listing."""

    property_manager_id: str
    address: str
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    sqft: Optional[int] = None
    price: float = Field(..., gt=0)
    url: Optional[str] = None
    pets_policy: PetsPolicy = Field(default=PetsPolicy.UNKNOWN)
    amenities: list[str] = Field(default_factory=list)
    photos: list[HttpUrl] = Field(default_factory=list)
    description: Optional[str] = None
    raw_data: Optional[str] = None


class ListingResponse(BaseModel):
    """Listing response model."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    property_manager_id: str
    preference_id: Optional[str] = None
    address: str
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    sqft: Optional[int] = None
    price: float
    url: str
    pets_policy: PetsPolicy
    amenities: list[str]
    photos: list[str]  # Serialized HttpUrl
    description: Optional[str] = None
    extraction_timestamp: datetime
    extraction_model: Optional[str] = None
    tier1_cost: Optional[float] = None
    tier2_cost: Optional[float] = None
    validation_passed: bool
    score: Optional[float] = None
    score_explanation: Optional[str] = None
    saved: bool = False


class ListingFilterParams(BaseModel):
    """Listing filter parameters."""

    city: Optional[str] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    min_bedrooms: Optional[int] = Field(None, ge=0)
    max_bedrooms: Optional[int] = Field(None, ge=0)
    min_bathrooms: Optional[float] = Field(None, ge=0)
    pets_policy: Optional[PetsPolicy] = None
    validated_only: bool = False
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


class ScoreListingsRequest(BaseModel):
    """Run preference scoring for persisted listings."""

    preference_id: str
    listing_ids: list[str] = Field(default_factory=list, max_length=100)
    limit: int = Field(50, ge=1, le=200)
    rescore: bool = False


class ScoreListingsResponse(BaseModel):
    """Summary of a listing scoring run."""

    preference_id: str
    scored_count: int
    listing_ids: list[str]


# ============================================================================
# Costs
# ============================================================================


class CostResponse(BaseModel):
    """Cost tracking response model."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    component: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    cache_hit: bool
    timestamp: datetime
    city: Optional[str] = None


class CostBreakdown(BaseModel):
    """Cost breakdown summary."""

    total_cost_usd: float
    call_count: int
    tokens_total: int
    cache_hit_count: int
    cache_hit_rate: float
    by_component: dict[str, float]
    by_model: dict[str, float]


class CostTimeseriesPoint(BaseModel):
    """A single data point for cost timeseries charts."""

    date: str  # YYYY-MM-DD
    cost_usd: float
    call_count: int
    tokens_total: int


class CostGroupedEntry(BaseModel):
    """A cost entry grouped by a dimension (component, model, city)."""

    group: str
    cost_usd: float
    call_count: int
    tokens_total: int


class CostSummaryResponse(BaseModel):
    """Full cost summary with budget info."""

    total_cost_usd: float
    total_calls: int
    total_tokens: int
    avg_cost_per_call: float
    cache_hit_rate: float
    budget_limit_usd: float
    budget_remaining_usd: float
    budget_exceeded: bool


# ============================================================================
# Health
# ============================================================================


class HealthCheck(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: Optional[str] = None


# ============================================================================
# Discovery Runs
# ============================================================================


class DiscoveryRunLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sequence: int
    level: str
    component: str
    message: str
    details: Optional[str] = None
    timestamp: datetime


class DiscoveryRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    city: str
    preference_id: Optional[str] = None
    status: str
    managers_found: Optional[int] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    logs: list[DiscoveryRunLogResponse] = []
