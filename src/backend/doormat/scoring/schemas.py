"""Pydantic schemas for listing scoring."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ScoringRequest(BaseModel):
    """Request to score a single listing against a preference."""

    listing_id: str
    address: str
    price: int | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None
    url: str
    property_manager: str | None = None

    preference_max_price: int | None = None
    preference_min_bedrooms: int | None = None
    preference_min_bathrooms: float | None = None
    preference_pets_required: bool | None = None
    preference_walkable: bool | None = None
    preference_description: str | None = None


class ScoringResult(BaseModel):
    """Result of scoring a listing against a preference."""

    listing_id: str
    score: float = Field(ge=0.0, le=1.0)
    reason: str
    used_llm: bool
    cost_usd: float = Field(ge=0.0)

    class Config:
        json_schema_extra = {
            "example": {
                "listing_id": "listing-123",
                "score": 0.92,
                "reason": "Matches budget, walkable neighborhood, 2 bedrooms as requested.",
                "used_llm": True,
                "cost_usd": 0.0045,
            }
        }


class ScorerConfig(BaseModel):
    """Configuration for the listing scorer."""

    model: str = "openrouter/anthropic/claude-3.5-sonnet"
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    timeout_seconds: int = Field(default=10, ge=1)
    fallback_on_error: bool = True
    track_costs: bool = True


class VisualCriterionVerdict(BaseModel):
    """Individual physical or lifestyle criterion verdict with visual evidence."""

    criterion: str
    verdict: Literal["confirmed", "likely_compromise", "not_possible", "unclear"]
    confidence: Literal["high", "medium", "low"]
    plain_label: str
    evidence: str
    photo_index: int | None = None

    def to_filter_reason(self) -> dict[str, Any]:
        """Format for inclusion in RunListingResult.filter_reasons_json."""
        slug = "".join(c if c.isalnum() else "_" for c in self.criterion.lower()).strip("_")[:30]
        return {
            "filter_code": f"visual_{slug}",
            "label": self.plain_label,
            "severity": self.verdict,
            "verdict": self.verdict,
            "evidence": self.evidence,
            "photo_index": self.photo_index,
            "confidence": self.confidence,
            "is_visual": True,
            "suggestion": self.evidence,
        }


class MultimodalEvaluationResult(BaseModel):
    """Overall multimodal scoring and visual criteria evaluation for a listing."""

    match_score: float = Field(ge=0.0, le=1.0)
    headline: str
    criteria: list[VisualCriterionVerdict] = Field(default_factory=list)
