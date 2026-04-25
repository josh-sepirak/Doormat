"""Pydantic models for the discovery agent (no DB)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class DiscoveryCandidate(BaseModel):
    """A candidate property manager discovered from a search source."""

    name: str = Field(..., min_length=1, max_length=255)
    website: str = Field(..., min_length=1, max_length=512)
    city: str = Field(..., min_length=1, max_length=100)
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: str = Field(..., min_length=1, max_length=64)

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        """Ensure source is a known origin string."""
        allowed = {"llm_search", "browser"}
        if value not in allowed:
            raise ValueError(f"source must be one of {allowed}, got {value!r}")
        return value


class ValidationResult(BaseModel):
    """Output of property manager classification."""

    is_valid: bool
    reason: str = Field(..., min_length=1, max_length=512)
    confidence: float = Field(..., ge=0.0, le=1.0)


class DiscoveryResult(BaseModel):
    """Aggregate result of a city discovery run."""

    city: str = Field(..., min_length=1, max_length=100)
    candidates_found: int = Field(..., ge=0)
    validated_count: int = Field(..., ge=0)
    cached: bool = False
    cost_usd: float = Field(..., ge=0.0)
    duration_seconds: float = Field(..., ge=0.0)
