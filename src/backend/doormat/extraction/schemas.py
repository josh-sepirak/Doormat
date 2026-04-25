"""Schemas for listing extraction."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl

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


class StrategyUpdate(BaseModel):
    """A patch to a source's cached extraction strategy.

    Only emitted in Mode B. Contains selectors or interaction steps that
    are verified to work on the current page. The runtime merges this
    into the source's strategy after validating it on a held-out sample.
    """

    field_selectors: dict[str, str] = Field(
        default_factory=dict,
        description="CSS or XPath selectors per field name. "
        "Example: {'rent': 'dd.price', 'bedrooms': '.beds-baths .beds'}",
    )
    pre_extraction_actions: list[str] = Field(
        default_factory=list,
        description="Click/scroll actions needed before extraction. "
        "Example: ['click .show-all-amenities', 'scroll down 800']",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Free-form notes about the source's quirks, for the next "
        "engineer (or the agent) reviewing this strategy.",
    )


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
