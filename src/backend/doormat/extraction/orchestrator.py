"""Extraction orchestrator."""

import json
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.extraction.mode_a import run_mode_a
from doormat.extraction.mode_b import run_mode_b
from doormat.extraction.schemas import ExtractedListing, ListingExtractionResult
from doormat.extraction.strategy import StrategyCache
from doormat.models.orm import Listing, PropertyManager

logger = structlog.get_logger(__name__)


async def extract_listing(
    session: AsyncSession,
    html: str,
    url: str,
    property_manager: PropertyManager,
) -> ListingExtractionResult:
    """Extract a listing using Mode A, falling back to Mode B if necessary."""

    source_id = property_manager.id
    strategy_cache = StrategyCache(session)
    strategy = await strategy_cache.get(source_id)

    # Mode A: trust the cached strategy (or attempt extraction if none exists yet).
    result = await run_mode_a(html, url, source_id, strategy)

    if _is_persistable_result(result):
        return await _save_listing(session, result, property_manager, url)

    # Mode A failed quality gates; escalate to Mode B with concrete failure context.
    logger.info("extraction_escalating_to_mode_b", source_id=source_id, url=url)

    # Provide the prior failure context to Mode B
    prior_failure = {
        "confidence": result.confidence,
        "reasoning": result.reasoning,
        "missing_fields": _identify_missing_fields(result.listing),
    }

    mode_b_result = await run_mode_b(url, source_id, prior_failure=prior_failure)

    if mode_b_result.strategy_update:
        # We don't have a listing ID yet, but we'll merge it.
        await strategy_cache.merge(source_id, mode_b_result.strategy_update)

    if _is_persistable_result(mode_b_result):
        return await _save_listing(session, mode_b_result, property_manager, url)

    logger.warning(
        "extraction_not_persisted_low_quality",
        source_id=source_id,
        url=url,
        confidence=mode_b_result.confidence,
        missing_fields=_identify_missing_fields(mode_b_result.listing),
    )
    return mode_b_result


def _identify_missing_fields(listing: ExtractedListing) -> list[str]:
    """Helper to figure out what was missing in Mode A."""
    missing = []
    if listing.rent == 0:
        missing.append("rent")
    if not listing.address or "Unknown" in listing.address:
        missing.append("address")
    if listing.bedrooms == 0:
        missing.append("bedrooms")
    return missing


def _is_persistable_result(result: ListingExtractionResult) -> bool:
    """Return True when an extraction is good enough to become user-facing data."""
    if result.confidence == "low":
        return False
    missing = set(_identify_missing_fields(result.listing))
    return "rent" not in missing and "address" not in missing


async def _save_listing(
    session: AsyncSession,
    result: ListingExtractionResult,
    property_manager: PropertyManager,
    url: str,
) -> ListingExtractionResult:
    """Persist the extracted listing to the database."""
    listing_data = result.listing
    listing_id = str(uuid.uuid4())

    db_listing = Listing(
        id=listing_id,
        property_manager_id=property_manager.id,
        address=listing_data.address,
        bedrooms=listing_data.bedrooms,
        bathrooms=listing_data.bathrooms,
        sqft=listing_data.sqft,
        price=listing_data.rent,
        url=url,
        pets_policy=listing_data.pets_policy.value,
        amenities=json.dumps(listing_data.amenities),
        photos=json.dumps([str(p) for p in listing_data.photos]),
        description=listing_data.description,
        extraction_timestamp=datetime.now(UTC),
        extraction_model="gpt-4o-mini" if result.mode == "A" else "gpt-4o",
        validation_passed=(result.confidence == "high"),
    )

    session.add(db_listing)
    await session.commit()

    logger.info("listing_saved", listing_id=listing_id, property_manager_id=property_manager.id)
    return result
