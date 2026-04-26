"""LLM-based listing scorer against user preferences."""

import structlog
from pydantic import BaseModel, Field

from doormat.llm.client import get_llm_client
from doormat.models.orm import Listing, Preference

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """\
You are a rental listing evaluator. Score how well a listing matches the user's preferences.
Return a score from 0.0 (terrible match) to 1.0 (perfect match) and a concise explanation.
Consider: price, bedrooms, pets policy, amenities, location, and any other stated preferences.
"""


class ListingScore(BaseModel):
    """LLM scoring output for a single listing."""

    score: float = Field(..., ge=0.0, le=1.0, description="Match score 0-1")
    explanation: str = Field(..., min_length=1, description="Why this score was assigned")


class ListingScorer:
    """Score listings against a user preference using LLM evaluation."""

    async def score(self, listing: Listing, preference: Preference) -> ListingScore:
        """Score a single listing against a preference."""
        llm = get_llm_client()
        user_content = (
            f"Preference: {preference.description}\n"
            f"City: {preference.city}\n\n"
            f"Listing:\n"
            f"  Address: {listing.address}\n"
            f"  Price: ${listing.price}/mo\n"
            f"  Bedrooms: {listing.bedrooms}\n"
            f"  Bathrooms: {listing.bathrooms}\n"
            f"  Sqft: {listing.sqft}\n"
            f"  Pets policy: {listing.pets_policy}\n"
            f"  Amenities: {listing.amenities}\n"
            f"  Description: {listing.description or 'N/A'}\n"
        )

        try:
            return await llm.complete(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                response_model=ListingScore,
                model="openai/gpt-4o-mini",
            )
        except Exception as e:
            logger.warning("listing_score_failed", listing_id=listing.id, error=str(e))
            return ListingScore(score=0.0, explanation=f"Scoring unavailable: {e}")

    async def score_batch(self, listings: list[Listing], preference: Preference) -> None:
        """Score all listings and update their score fields in place."""
        for listing in listings:
            result = await self.score(listing, preference)
            listing.score = result.score
            listing.score_explanation = result.explanation
