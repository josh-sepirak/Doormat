"""Pydantic request/response models for API."""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

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
    sources_enabled: Optional[list[str]] = Field(None)


class PreferenceUpdate(BaseModel):
    """Update an existing preference."""

    description: Optional[str] = Field(None, min_length=10, max_length=1000)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    sources_enabled: Optional[list[str]] = Field(None)
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
    sources_enabled: list[str] = Field(default_factory=lambda: ["craigslist"])
    prompt_overrides: Optional[dict[str, str]] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("prompt_overrides", mode="before")
    @classmethod
    def parse_prompt_overrides_field(cls, v: Any) -> Optional[dict[str, str]]:
        if v is None:
            return None
        if isinstance(v, dict):
            return {str(k): str(val) for k, val in v.items() if isinstance(val, str)}
        if isinstance(v, str):
            if not v.strip():
                return None
            try:
                parsed = json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return None
            if isinstance(parsed, dict):
                return {str(k): str(val) for k, val in parsed.items() if isinstance(val, str)}
        return None

    @field_validator("sources_enabled", mode="before")
    @classmethod
    def parse_sources_enabled(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
            return ["craigslist"]
        if isinstance(v, list):
            return v
        return ["craigslist"]


class PreferencePromptEntry(BaseModel):
    """One editable prompt with default vs effective text."""

    key: str
    title: str
    description: str
    max_length: int
    placeholders: list[str] = Field(default_factory=list)
    default_text: str
    effective_text: str
    is_custom: bool


class PreferencePromptsEnvelope(BaseModel):
    """GET /api/preferences/{id}/prompts"""

    prompts: list[PreferencePromptEntry]


class PreferencePromptsPatch(BaseModel):
    """PATCH /api/preferences/{id}/prompts"""

    overrides: Optional[dict[str, str]] = None
    reset_keys: Optional[list[str]] = None
    reset_all: bool = False


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
    url: Optional[str] = None
    source: str = "pm_direct"
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
    latitude: Optional[float] = None
    longitude: Optional[float] = None


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


# ============================================================================
# Search Runs (interactive parent runs)
# ============================================================================


class SearchRunCreate(BaseModel):
    """Start a wrapped discovery run under a durable parent `SearchRun`."""

    city: str = Field(..., min_length=2, max_length=100)
    preference_id: Optional[str] = None


class SearchRunSuggestion(BaseModel):
    """Deterministic, aggregated suggestion for UI display."""

    kind: str
    message: str
    count: int = 0


class SearchRunResponse(BaseModel):
    """Full parent run snapshot for polling and report."""

    id: str
    discovery_run_id: str
    city: str
    preference_id: Optional[str] = None
    status: str
    current_stage: str
    cancel_requested: bool
    sources_checked: int
    managers_validated: int
    listings_seen: int
    extraction_attempts: int = 0
    great_matches: int
    worth_a_look: int
    near_misses: int
    filtered_out: int
    cost_usd_so_far: float
    active_revision: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    filter_summary: dict[str, Any] = Field(default_factory=dict)
    suggestions: list[SearchRunSuggestion] = Field(default_factory=list)
    suggestions_early_signal: bool = True


class SearchRunActiveEnvelope(BaseModel):
    active: bool
    run: Optional[SearchRunResponse] = None


class SearchRunEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sequence: int
    event_type: str
    stage: Optional[str] = None
    message: str
    payload_json: Optional[str] = None
    visibility: str
    timestamp: datetime


class SearchRunFiltersPatch(BaseModel):
    """Mutable filters for the current run; disallows next-run-only scope changes."""

    model_config = ConfigDict(extra="ignore")

    max_price: Optional[float] = Field(default=None, gt=0)
    min_bedrooms: Optional[int] = Field(default=None, ge=0)
    min_bathrooms: Optional[float] = Field(default=None, ge=0.0)
    pets_required: Optional[bool] = None
    score_great_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    score_worth_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    next_run_city: Optional[str] = None
    next_run_change_openrouter_key: Optional[bool] = None

    @model_validator(mode="after")
    def reject_next_run_fields(self) -> "SearchRunFiltersPatch":
        if self.next_run_city is not None:
            raise ValueError("City changes apply to the next run, not the current run.")
        if self.next_run_change_openrouter_key is not None:
            raise ValueError("API key changes apply to the next run, not the current run.")
        return self


class RunListingResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    listing_id: str
    revision: int
    category: str
    score: Optional[float] = None
    filter_reasons_json: Optional[str] = None
    explanation: Optional[str] = None
