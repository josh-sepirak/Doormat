"""Mode B: Agentic recovery extraction using Browser-Use."""

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Optional
from urllib.parse import urlparse

import structlog

from doormat.config import settings
from doormat.cost_tracking import track_cost
from doormat.extraction.network_capture import NetworkCapture
from doormat.extraction.schemas import ApiRecipe, ExtractedListing, ListingExtractionResult
from doormat.llm.client import MODEL_REASONING
from doormat.llm.prompt_registry import DEFAULT_PROMPTS, PromptKey, get_effective_prompt
from doormat.models.orm import Preference
from doormat.schemas import PetsPolicy

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = DEFAULT_PROMPTS[PromptKey.EXTRACTION_MODE_B_SYSTEM]
USER_TEMPLATE = DEFAULT_PROMPTS[PromptKey.EXTRACTION_MODE_B_USER]

try:
    from browser_use import Agent, BrowserSession
    from browser_use.llm.litellm.chat import ChatLiteLLM

    BROWSER_USE_AVAILABLE = True
except ImportError:
    BROWSER_USE_AVAILABLE = False


def _low_confidence_result(reason: str) -> ListingExtractionResult:
    """Return a structured failure result without persisting guessed data."""
    return ListingExtractionResult(
        reasoning=reason,
        listing=ExtractedListing(
            address="Unknown - see source URL",
            rent=0,
            bedrooms=0,
            bathrooms=0,
            pets_policy=PetsPolicy.UNKNOWN,
            description="",
        ),
        confidence="low",
        mode="B",
    )


def _allowed_domains(url: str) -> list[str]:
    """Restrict Browser-Use navigation to the listing host."""
    host = urlparse(url).netloc.lower()
    return [host] if host else []


def _token_usage_from_history(history: Any) -> tuple[int, int]:
    """Best-effort extraction of token usage from Browser-Use/LiteLLM history objects."""
    visited: set[int] = set()

    def visit(value: Any, depth: int = 0) -> tuple[int, int]:
        if value is None or depth > 5:
            return (0, 0)
        value_id = id(value)
        if value_id in visited:
            return (0, 0)
        visited.add(value_id)

        prompt_tokens = _extract_token_count(value, "prompt_tokens", "input_tokens", "tokens_in")
        completion_tokens = _extract_token_count(
            value, "completion_tokens", "output_tokens", "tokens_out"
        )
        if prompt_tokens or completion_tokens:
            return (prompt_tokens, completion_tokens)

        if isinstance(value, Mapping):
            nested = (
                "usage",
                "token_usage",
                "model_usage",
                "llm_usage",
                "metadata",
                "history",
                "steps",
            )
            return _sum_usage(visit(value.get(key), depth + 1) for key in nested if key in value)

        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return _sum_usage(visit(item, depth + 1) for item in value)

        nested_attrs = (
            "usage",
            "token_usage",
            "model_usage",
            "llm_usage",
            "metadata",
            "history",
            "steps",
        )
        return _sum_usage(
            visit(getattr(value, attr), depth + 1) for attr in nested_attrs if hasattr(value, attr)
        )

    return visit(history)


def _sum_usage(usages: Any) -> tuple[int, int]:
    prompt_tokens = 0
    completion_tokens = 0
    for prompt, completion in usages:
        prompt_tokens += prompt
        completion_tokens += completion
    return prompt_tokens, completion_tokens


def _extract_token_count(value: Any, *keys: str) -> int:
    for key in keys:
        raw = value.get(key) if isinstance(value, Mapping) else getattr(value, key, None)
        parsed = _parse_token_count(raw)
        if parsed is not None:
            return parsed
    return 0


def _parse_token_count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float):
        return max(int(value), 0)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _try_synthesize_recipe(
    capture: NetworkCapture,
    url: str,
    source_id: str,
    extracted_listing: ExtractedListing,
) -> Optional[ApiRecipe]:
    """Attempt to synthesize an ApiRecipe from captured network traffic.

    If Mode B successfully extracted a listing, check if we captured any
    JSON API calls that match the extracted fields. If so, create an
    ApiRecipe for fast replay on future listings from this source.

    Args:
        capture: NetworkCapture with recorded network calls.
        url: Source URL that was processed.
        source_id: Property manager ID.
        extracted_listing: The ExtractedListing that Mode B produced.

    Returns:
        An ApiRecipe if synthesis succeeds, None otherwise.
    """
    candidates = capture.get_listing_candidates()
    if not candidates:
        logger.debug("no_network_candidates_for_recipe", source_id=source_id)
        return None

    # Try to synthesize a recipe from the first candidate
    # (In production, could score all candidates and pick the best)
    for call in candidates:
        try:
            recipe = _synthesize_recipe_from_call(
                call,
                url,
                extracted_listing,
            )
            if recipe:
                logger.info(
                    "recipe_synthesized",
                    source_id=source_id,
                    url=call.request.url,
                    captured_fields=len(recipe.field_paths),
                )
                return recipe
        except Exception as e:
            logger.debug(
                "recipe_synthesis_failed",
                source_id=source_id,
                error=str(e),
            )
            continue

    return None


def _synthesize_recipe_from_call(
    call: Any,  # CapturedNetworkCall
    listing_url: str,
    extracted_listing: ExtractedListing,
) -> Optional[ApiRecipe]:
    """Synthesize an ApiRecipe from a captured network call.

    Args:
        call: CapturedNetworkCall with request/response.
        listing_url: The original listing URL.
        extracted_listing: The listing extracted by Mode B.

    Returns:
        An ApiRecipe with field_paths that can reproduce the extracted listing, or None.
    """
    response_json = call.response_json
    if not response_json:
        return None

    # Try to map extracted fields to paths in the response
    field_paths = _map_listing_fields_to_paths(response_json, extracted_listing)
    if not field_paths:
        return None

    # Compute response_root (how to navigate from root to the listing object)
    response_root = _compute_response_root(response_json, field_paths)

    # Determine extractable_fields (which fields we can reliably extract)
    extractable = list(field_paths.keys())

    recipe = ApiRecipe(
        method=call.request.method,
        url_template=call.request.url,
        headers=call.request.headers or {},
        body_template=call.request.body,
        response_root=response_root,
        field_paths=field_paths,
        extractable_fields=extractable,
        captured_at=datetime.now(UTC),
        captured_from_listing_id=_extract_listing_id(listing_url),
        confidence="medium",  # Will be elevated to "high" after held-out validation
        capture_notes=f"Synthesized from Mode B extraction on {listing_url}",
    )

    return recipe


def _map_listing_fields_to_paths(
    response_json: dict[str, Any],
    extracted_listing: ExtractedListing,
) -> dict[str, str]:
    """Map ExtractedListing fields to JSONPath expressions in the response.

    Uses simple heuristics to find where listing fields are located
    in the response JSON structure.

    Args:
        response_json: The full response JSON from the API.
        extracted_listing: The listing extracted by Mode B.

    Returns:
        Dict mapping field name → JSONPath (e.g., {"rent": "$.price", "bedrooms": "$.beds"})
    """
    field_paths = {}

    # Extract the listing object from the response (may be nested)
    # Try common nesting patterns
    listing_obj = response_json
    if "listing" in response_json and isinstance(response_json["listing"], dict):
        listing_obj = response_json["listing"]
    elif "property" in response_json and isinstance(response_json["property"], dict):
        listing_obj = response_json["property"]
    elif "data" in response_json and isinstance(response_json["data"], dict):
        potential_listing = response_json["data"]
        if isinstance(potential_listing, dict) and len(potential_listing) > 0:
            # If data has a "listing" subkey, use that
            if "listing" in potential_listing:
                listing_obj = potential_listing["listing"]
            else:
                listing_obj = potential_listing

    # Map each field name to a path in the listing object
    if isinstance(listing_obj, dict):
        # Try exact matches first
        for key in listing_obj.keys():
            key_lower = key.lower()
            if key_lower == "address" and extracted_listing.address:
                field_paths["address"] = f"$.{key}"
            elif key_lower in ("rent", "price") and extracted_listing.rent > 0:
                field_paths["rent"] = f"$.{key}"
            elif key_lower in ("bedrooms", "beds") and extracted_listing.bedrooms > 0:
                field_paths["bedrooms"] = f"$.{key}"
            elif (
                key_lower
                in (
                    "bathrooms",
                    "baths",
                    "bath",
                )
                and extracted_listing.bathrooms > 0
            ):
                field_paths["bathrooms"] = f"$.{key}"

    return field_paths


def _compute_response_root(
    response_json: dict[str, Any],
    field_paths: dict[str, str],
) -> str:
    """Compute the response_root path given the response JSON and field mappings.

    Args:
        response_json: The full response JSON.
        field_paths: Mapped field paths (e.g., {"rent": "$.price"}).

    Returns:
        A JSONPath root accessor (e.g., "$" or "$.listing" or "$.data.property").
    """
    # If field_paths have paths like "$.rent", they're already at root
    if all(p.startswith("$.") for p in field_paths.values()):
        # All fields are at top level; root is "$"
        return "$"

    # If all paths start with "$.listing.", the root is "$.listing"
    if all(p.startswith("$.listing.") for p in field_paths.values()):
        return "$.listing"

    # Default to root
    return "$"


def _extract_listing_id(url: str) -> str:
    """Extract a likely listing ID from the URL for reference.

    Args:
        url: The listing URL.

    Returns:
        The URL itself (will be used in replay validation).
    """
    return url


async def run_mode_b(
    url: str,
    source_id: str,
    prior_failure: dict[str, Any],
    city: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    preference: Preference | None = None,
) -> ListingExtractionResult:
    """Run Mode B agentic recovery extraction using Browser-Use.

    Includes network capture to record JSON API calls, which can be
    synthesized into ApiRecipe for faster Mode A0 extraction on future listings.
    """
    model = model or MODEL_REASONING
    logger.info("extraction_mode_b_start", source_id=source_id, url=url, city=city)

    if not BROWSER_USE_AVAILABLE:
        logger.warning("browser_use_unavailable_for_mode_b", source_id=source_id)
        return _low_confidence_result("browser-use not available locally")

    resolved_api_key = api_key or settings.OPENROUTER_API_KEY
    if not resolved_api_key:
        logger.warning("mode_b_missing_openrouter_key", source_id=source_id)
        return _low_confidence_result("OPENROUTER_API_KEY is not configured")

    llm = ChatLiteLLM(
        model=model,
        api_key=resolved_api_key,
        api_base=settings.OPENROUTER_BASE_URL,
        temperature=0.0,
    )

    browser_session = BrowserSession(headless=True, allowed_domains=_allowed_domains(url))

    # Initialize network capture for this session
    capture = NetworkCapture()
    capture.start()

    system_prompt = get_effective_prompt(PromptKey.EXTRACTION_MODE_B_SYSTEM, preference)
    user_tpl = get_effective_prompt(PromptKey.EXTRACTION_MODE_B_USER, preference)
    task_prompt = user_tpl.format(
        source=source_id,
        url=url,
        prior_failure_json=json.dumps(prior_failure, indent=2),
    )

    agent: Any = Agent(
        task=f"{system_prompt}\n\n{task_prompt}",
        llm=llm,
        browser_session=browser_session,
        max_actions_per_step=2,
        max_failures=2,
    )

    result = None
    try:
        async with track_cost(
            service="openrouter",
            model=model,
            component="extraction",
            city=city,
        ) as cost:
            history: Any = await agent.run()
            prompt_tokens, completion_tokens = _token_usage_from_history(history)
            cost.prompt_tokens = prompt_tokens
            cost.completion_tokens = completion_tokens
        # Extract the final result from the agent history
        final_state = history.history[-1]
        result_text = final_state.result[0].extracted_content
        if not isinstance(result_text, str):
            raise ValueError("Browser-Use did not return extracted JSON content")
        # parse json
        data = json.loads(result_text)
        result = ListingExtractionResult.model_validate(data)
    except Exception as e:
        logger.error(
            "extraction_mode_b_failed",
            error=str(e),
            error_type=type(e).__name__,
            source_id=source_id,
        )
        capture.stop()
        return _low_confidence_result(f"Mode B failed: {type(e).__name__}")
    finally:
        close = getattr(browser_session, "close", None)
        if close is not None:
            maybe_awaitable = close()
            if hasattr(maybe_awaitable, "__await__"):
                await maybe_awaitable

    result.mode = "B"
    logger.info("extraction_mode_b_complete", source_id=source_id, confidence=result.confidence)

    # Try to synthesize a recipe from captured network traffic
    if result.confidence in ("high", "medium") and result.listing:
        recipe = _try_synthesize_recipe(capture, url, source_id, result.listing)
        if recipe:
            # Attach recipe to strategy_update so it gets merged later
            if not result.strategy_update:
                from doormat.extraction.schemas import StrategyUpdate

                result.strategy_update = StrategyUpdate()
            result.strategy_update.api_recipe = recipe

    capture.stop()
    return result
