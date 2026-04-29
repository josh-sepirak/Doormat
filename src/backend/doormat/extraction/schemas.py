"""Schemas for listing extraction."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator

from doormat.schemas import PetsPolicy


class ExtractedListing(BaseModel):
    """The listing object extracted by the LLM."""

    address: str = Field(
        description="Full street address, including city, state, ZIP when available. "
        "If unrecoverable, set to 'Unknown — see source URL'."
    )
    rent: int = Field(
        ge=0,
        le=50_000,
        description="Monthly rent in USD. Integer dollars only. "
        "Use 0 only when the rent is unrecoverable.",
    )
    bedrooms: int = Field(ge=0, le=20)
    bathrooms: float = Field(ge=0, le=20)
    sqft: Optional[int] = Field(
        default=None,
        ge=100,
        le=20_000,
        description="Square feet. Null if not stated. Never estimate.",
    )
    pets_policy: PetsPolicy = Field(
        description="See system prompt for the four valid values and their precedence rules."
    )
    amenities: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Lowercase short tags. Examples: 'pool', 'rv parking', "
        "'fenced yard', 'in-unit laundry', 'garage', 'central ac'. "
        "Skip generic adjectives like 'modern', 'spacious', 'beautiful'.",
    )
    photos: list[HttpUrl] = Field(
        default_factory=list,
        max_length=20,
        description="Photo URLs from the listing's image gallery. "
        "Skip thumbnails of agent profiles or PM logos.",
    )
    description: str = Field(
        max_length=2000,
        description="The listing's narrative description, cleaned of HTML and "
        "trimmed to 2000 chars. Preserve paragraph breaks where present.",
    )


class ApiRecipe(BaseModel):
    """A reusable HTTP recipe for fetching listing data without a browser.

    Captured by Mode B when it observes the source fetching listing data
    via JSON XHR. Promoted to a fast Mode A0 path via the strategy merge
    gate after a replay validation succeeds against a held-out listing.

    Once promoted, Mode A0 skips both Browser-Use and HTML extraction:
    render the URL template, fire one httpx call, walk the JSON, build
    the Listing. Cost approaches zero per call (HTTP only, no LLM).
    """

    method: Literal["GET", "POST"] = "GET"
    url_template: str = Field(
        description="URL with optional placeholders. Supported: {listing_id}, {slug}. "
        "Example: 'https://acme-pm.com/api/listings/{listing_id}'"
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Request headers. Auth headers (Cookie, Authorization, X-CSRF-*, etc.) "
        "are stripped at capture time. Only safe headers needed to make the request work survive.",
    )
    body_template: Optional[str] = Field(
        default=None,
        description="POST body template, JSON-encoded. Same placeholder rules as url_template. "
        "None for GET requests.",
    )
    response_root: str = Field(
        default="$",
        description="JSONPath-style accessor pointing to the listing object within the response body. "
        "Examples: '$', '$.data.listing', '$.results[0]'. When the API returns a list, the recipe "
        "is valid only if the list has exactly one element matching the requested listing_id.",
    )
    field_paths: dict[str, str] = Field(
        description="Per-ExtractedListing-field JSONPath inside the object at response_root. "
        "Keys must align with ExtractedListing field names (use 'rent' not 'price'). "
        "Required keys: address, rent, bedrooms, bathrooms. Optional: sqft, pets_policy, amenities, "
        "photos, description."
    )
    extractable_fields: list[str] = Field(
        description="Which Listing fields this recipe can populate. Subset of field_paths.keys(). "
        "The runtime fills missing fields from any available HTML fallback or marks the listing "
        "as confidence: medium."
    )
    captured_at: datetime
    captured_from_listing_id: str = Field(
        description="The listing_id present in the capture URL, used for replay validation."
    )
    last_validated_at: Optional[datetime] = Field(default=None)
    last_failure_at: Optional[datetime] = Field(default=None)
    failure_count: int = Field(
        default=0,
        description="Increments when Mode A0 fails on this recipe. The runtime retires the recipe "
        "(sets it to None on the strategy) when failure_count >= 3 consecutive failures without "
        "an intervening success.",
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="high = recipe was replay-validated against a held-out listing and returned "
        "all extractable_fields. medium = matched extracted fields but not replay-validated. "
        "low = captured opportunistically; treated as not-yet-promoted until a future Mode B run "
        "validates it."
    )
    capture_notes: Optional[str] = Field(
        default=None,
        max_length=600,
        description="Free-form notes from Mode B about quirks. "
        "Example: 'API requires an X-Origin header that matches the page origin'.",
    )


class StrategyUpdate(BaseModel):
    """A patch to a source's cached extraction strategy.

    Only emitted in Mode B. Contains selectors or interaction steps that
    are verified to work on the current page. The runtime merges this
    into the source's strategy after validating it on a held-out sample.
    """

    field_selectors: dict[str, str] = Field(
        default_factory=dict,
        max_length=12,
        description="CSS or XPath selectors per field name. "
        "Example: {'rent': 'dd.price', 'bedrooms': '.beds-baths .beds'}",
    )
    pre_extraction_actions: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Click/scroll actions needed before extraction. "
        "Example: ['click .show-all-amenities', 'scroll down 800']",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Free-form notes about the source's quirks, for the next "
        "engineer (or the agent) reviewing this strategy.",
    )
    api_recipe: Optional["ApiRecipe"] = Field(
        default=None,
        description="If Mode B observed the page fetching listing data via JSON XHR/fetch, "
        "the captured recipe. None if Mode B used DOM extraction only or saw no usable JSON traffic. "
        "The runtime validates the recipe by replaying it against a held-out listing before merging "
        "into the cached strategy.",
    )

    @field_validator("field_selectors")
    @classmethod
    def validate_field_selector_keys(cls, value: dict[str, str]) -> dict[str, str]:
        """Restrict strategy patches to fields the extractor actually understands."""
        allowed_fields = {
            "address",
            "rent",
            "bedrooms",
            "bathrooms",
            "sqft",
            "pets_policy",
            "amenities",
            "photos",
            "description",
        }
        unknown = sorted(set(value) - allowed_fields)
        if unknown:
            raise ValueError(f"unknown strategy field selector keys: {unknown}")
        return value


class ListingExtractionResult(BaseModel):
    """The unified output schema for both Mode A and Mode B."""

    reasoning: Optional[str] = Field(
        default=None,
        max_length=600,
        description="Scratchpad for ambiguous fields. In Mode B, also briefly "
        "describe what you tried with the browser tools and what worked. "
        "Skip when listing is unambiguous.",
    )
    listing: ExtractedListing
    confidence: Literal["high", "medium", "low"] = Field(
        description="Your confidence that the listing matches what a human would "
        "extract. low triggers Mode B retry (in Mode A) or human review "
        "(in Mode B). Be honest."
    )
    strategy_update: Optional[StrategyUpdate] = Field(
        default=None,
        description="Only emit in Mode B. Set to None in Mode A. "
        "If Mode B did not learn anything new, also set to None.",
    )
    mode: Literal["A", "B"] = Field(
        description="The mode you ran in. Used by the runtime for cost tracking."
    )
