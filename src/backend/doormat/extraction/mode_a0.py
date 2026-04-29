"""Mode A0: Zero-cost API recipe extraction (fast path)."""

from datetime import UTC, datetime
from typing import Optional

import httpx
import structlog

from doormat.extraction.recipe_executor import extract_listing_via_recipe
from doormat.extraction.schemas import ApiRecipe, ExtractedListing, ListingExtractionResult
from doormat.models.orm import ExtractionStrategy

logger = structlog.get_logger(__name__)


async def run_mode_a0(
    url: str,
    source_id: str,
    strategy: ExtractionStrategy | None,
    http_client: httpx.AsyncClient,
) -> ListingExtractionResult | None:
    """Attempt zero-cost extraction via API recipe.

    Returns ListingExtractionResult if successful, None if no recipe or extraction fails.
    Automatically retire recipe after 3 consecutive failures.

    Args:
        url: Source URL (may be used in url_template).
        source_id: Property manager ID.
        strategy: Cached extraction strategy (may contain api_recipe).
        http_client: Async HTTP client for API calls.

    Returns:
        ListingExtractionResult with mode="A0" on success, None if recipe unavailable or fails.
    """
    if not strategy or not strategy.api_recipe:
        logger.debug("mode_a0_skipped_no_recipe", source_id=source_id)
        return None

    recipe = strategy.api_recipe
    if not recipe.confidence or recipe.confidence == "low":
        logger.debug(
            "mode_a0_skipped_low_confidence",
            source_id=source_id,
            confidence=recipe.confidence,
        )
        return None

    recipe_sig = f"{recipe.method}:{recipe.url_template}"
    logger.info("mode_a0_attempt", source_id=source_id, recipe_sig=recipe_sig)

    try:
        # Fetch from API using recipe
        response_json = await _fire_recipe(http_client, url, recipe)
        if not response_json:
            logger.warning(
                "mode_a0_http_request_failed",
                source_id=source_id,
            )
            return _handle_recipe_failure(recipe)

        # Extract listing from response
        listing = extract_listing_via_recipe(recipe, response_json)
        if not listing:
            logger.warning(
                "mode_a0_extraction_failed",
                source_id=source_id,
                reason="extract_listing_via_recipe returned None",
            )
            return _handle_recipe_failure(recipe)

        logger.info(
            "mode_a0_success",
            source_id=source_id,
            address=listing.address,
            rent=listing.rent,
        )

        # Reset failure count on success
        recipe.failure_count = 0
        recipe.last_failure_at = None

        return ListingExtractionResult(
            listing=listing,
            confidence="high",  # API recipes are high-confidence by definition
            mode="A",
            reasoning="Zero-cost API recipe extraction succeeded",
        )

    except httpx.HTTPError as exc:
        logger.warning(
            "mode_a0_http_error",
            source_id=source_id,
            error=str(exc),
        )
        return _handle_recipe_failure(recipe)
    except Exception as exc:
        logger.error(
            "mode_a0_unexpected_error",
            source_id=source_id,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return _handle_recipe_failure(recipe)


async def _fire_recipe(
    http_client: httpx.AsyncClient,
    url: str,
    recipe: ApiRecipe,
) -> dict | None:
    """Execute HTTP request via recipe template.

    Returns response JSON parsed at response_root, or None on error.

    Args:
        http_client: Async HTTP client.
        url: Listing URL (used for substitution in url_template).
        recipe: ApiRecipe with method, url_template, headers, body_template.

    Returns:
        Parsed JSON dict from response, or None if request fails or response is invalid.
    """
    # Substitute {url} in url_template
    api_url = recipe.url_template.replace("{url}", url)

    # Prepare headers
    headers = dict(recipe.headers) if recipe.headers else {}

    # Prepare body
    body = None
    if recipe.body_template:
        body = recipe.body_template.replace("{url}", url)

    try:
        response = await http_client.request(
            method=recipe.method,
            url=api_url,
            headers=headers,
            content=body,
            timeout=10.0,
        )
        response.raise_for_status()

        data = response.json()
        return data

    except (httpx.HTTPError, ValueError) as exc:
        logger.debug(
            "_fire_recipe_error",
            api_url=api_url,
            method=recipe.method,
            error=str(exc),
        )
        return None


def _handle_recipe_failure(recipe: ApiRecipe) -> ListingExtractionResult | None:
    """Increment failure counter; retire recipe if >= 3 failures.

    Returns None (callers should fall through to Mode A).
    Side effect: Mutates recipe.failure_count and may set recipe.confidence to None.
    """
    recipe.failure_count = (recipe.failure_count or 0) + 1
    recipe.last_failure_at = datetime.now(UTC)

    if recipe.failure_count >= 3:
        logger.warning(
            "mode_a0_recipe_retired",
            failure_count=recipe.failure_count,
        )
        recipe.confidence = None  # Retire recipe
    else:
        logger.debug(
            "mode_a0_recipe_failure_logged",
            failure_count=recipe.failure_count,
        )

    return None
