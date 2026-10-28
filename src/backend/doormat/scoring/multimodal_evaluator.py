"""Multimodal listing evaluator using Gemini 2.0 Flash to verify physical criteria from photos."""

from __future__ import annotations

import json
from typing import Any, cast

import structlog

from doormat.llm.client import get_llm_client
from doormat.models.orm import Listing, Preference
from doormat.scoring.schemas import MultimodalEvaluationResult
from doormat.security.secrets import decrypt_secret

logger = structlog.get_logger(__name__)

DEFAULT_MULTIMODAL_MODEL = "google/gemini-2.0-flash-001"
MAX_EVALUATION_PHOTOS = 4


def extract_photo_urls(listing: Listing, max_photos: int = MAX_EVALUATION_PHOTOS) -> list[str]:
    """Extract up to max_photos valid HTTP/HTTPS image URLs from listing.photos JSON."""
    if not listing.photos:
        return []
    try:
        raw = json.loads(listing.photos)
        if isinstance(raw, list):
            urls = [
                u.strip()
                for u in raw
                if isinstance(u, str) and u.strip().startswith(("http://", "https://"))
            ]
            # shortcut: caps at 4 photos to keep latency <350ms and token costs <$0.0002, upgrade if gallery search needed
            return urls[:max_photos]
    except Exception as e:
        logger.debug("extract_photo_urls_failed", listing_id=listing.id, error=str(e))
    return []


def extract_visual_criteria(preference_text: str | None) -> list[str]:
    """Extract physical and visual lifestyle criteria from user preference text."""
    text = (preference_text or "").lower()
    criteria: list[str] = []

    if any(k in text for k in ("trampoline", "12ft", "15ft")):
        criteria.append("12ft+ trampoline fit (flat open grass lawn clearance)")
    elif any(k in text for k in ("yard", "lawn", "grass", "backyard")):
        criteria.append("Backyard space (flat grass lawn, private outdoor area)")

    if any(k in text for k in ("dog", "fenced", "pet yard", "dog run")):
        criteria.append("Dog outdoor space (fenced private yard, secure boundary)")

    if any(k in text for k in ("laundry", "washer", "dryer", "w/d", "in-unit")):
        criteria.append("In-unit laundry (washer/dryer appliances or dedicated hookup closet)")

    if any(k in text for k in ("light", "sun", "window", "bright", "exposure")):
        criteria.append("Natural light (large windows, bright daytime illumination)")

    if any(k in text for k in ("desk", "office", "wfh", "workspace", "den")):
        criteria.append("Dedicated workspace (desk nook, office area, or quiet work corner)")

    if any(k in text for k in ("balcony", "patio", "deck")):
        criteria.append("Outdoor patio / balcony (private usable outdoor seating)")

    if any(k in text for k in ("ground floor", "private entry", "private entrance")):
        criteria.append("Ground floor / private entry (no shared high-rise corridors)")

    if not criteria:
        # Default lifestyle baseline for visual inspection
        criteria = [
            "Outdoor space (fenced yard, grass lawn, or private patio)",
            "In-unit laundry (washer and dryer appliances visible)",
            "Natural light (window size and daylight in living spaces)",
        ]

    return criteria


class MultimodalListingEvaluator:
    """Evaluates rental listing photos and description against physical/visual criteria."""

    async def evaluate(
        self,
        listing: Listing,
        preference: Preference,
        photos: list[str] | None = None,
    ) -> MultimodalEvaluationResult:
        """Run multimodal evaluation on listing photos and details."""
        photo_urls = photos if photos is not None else extract_photo_urls(listing)
        if not photo_urls:
            raise ValueError(f"Listing {listing.id} has no valid photo URLs for visual evaluation")

        api_key = decrypt_secret(preference.openrouter_api_key)
        if not api_key:
            raise ValueError("No OpenRouter API key configured for multimodal scoring")

        criteria = extract_visual_criteria(preference.description)
        model = (
            preference.smart_model
            if preference.smart_model and ("gemini" in preference.smart_model or "gpt-4o" in preference.smart_model)
            else DEFAULT_MULTIMODAL_MODEL
        )

        system_prompt = (
            "You are an expert rental property visual evaluator. "
            "Your task is to inspect listing photos and description against the renter's physical and lifestyle criteria. "
            "For each criterion, determine:\n"
            "- criterion: criterion name\n"
            "- verdict: 'confirmed' (clearly visible & satisfies requirement), 'likely_compromise' (partially satisfies or has tradeoffs like paved patio instead of grass), 'not_possible' (clearly cannot satisfy, e.g. upper-floor balcony when yard required), or 'unclear' (cannot be determined from provided photos)\n"
            "- confidence: 'high', 'medium', or 'low'\n"
            "- plain_label: concise consumer badge (e.g. 'Fits 12ft Trampoline', 'Fenced Yard for Dogs', 'Full Washer & Dryer')\n"
            "- evidence: factual visual citation stating what is visible and citing the photo index (e.g. 'Photo 2 shows a flat grassy backyard (~35ft wide) with no overhead tree canopy.')\n"
            "- photo_index: 1-based integer of the photo showing the strongest evidence (e.g. 1 for Photo 1, 2 for Photo 2), or null if not visible in photos\n\n"
            "Also provide:\n"
            "- match_score: overall suitability score from 0.0 to 1.0\n"
            "- headline: a concise 1-sentence summary of how well this home matches the renter's visual and physical needs"
        )

        listing_summary = (
            f"Address: {listing.address}\n"
            f"Price: ${listing.price:.0f}/mo\n"
            f"Bedrooms: {listing.bedrooms if listing.bedrooms is not None else 'Unknown'}\n"
            f"Bathrooms: {listing.bathrooms if listing.bathrooms is not None else 'Unknown'}\n"
            f"Pets policy: {listing.pets_policy}\n"
            f"Description: {listing.description or 'No description provided'}\n\n"
            f"Renter Wishlist: {preference.description or 'Standard rental requirements'}\n"
            f"Criteria to evaluate:\n" + "\n".join(f"- {c}" for c in criteria) + "\n\n"
            f"Photos provided in order ({len(photo_urls)} total): Photo 1 to Photo {len(photo_urls)}. "
            "Cite photos by their 1-based index (e.g. Photo 1, Photo 2)."
        )

        user_content: list[dict[str, Any]] = [{"type": "text", "text": listing_summary}]
        for url in photo_urls:
            user_content.append({"type": "image_url", "image_url": {"url": url}})

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        llm = get_llm_client(api_key=api_key)
        logger.info(
            "multimodal_evaluator_calling_llm",
            listing_id=listing.id,
            model=model,
            photo_count=len(photo_urls),
            criteria_count=len(criteria),
        )

        result = await llm.complete(
            messages=messages,
            response_model=MultimodalEvaluationResult,
            model=model,
            task="scoring",
            component="multimodal_scoring",
            city=preference.city,
            max_tokens=600,
            temperature=0.0,
        )
        return cast(MultimodalEvaluationResult, result)
