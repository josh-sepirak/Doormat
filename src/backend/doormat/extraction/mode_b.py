"""Mode B: Agentic recovery extraction using Browser-Use."""

import json
from collections.abc import Mapping, Sequence
from typing import Any, Optional
from urllib.parse import urlparse

import structlog

from doormat.config import settings
from doormat.cost_tracking import track_cost
from doormat.extraction.schemas import ExtractedListing, ListingExtractionResult
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


async def run_mode_b(
    url: str,
    source_id: str,
    prior_failure: dict[str, Any],
    city: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    preference: Preference | None = None,
) -> ListingExtractionResult:
    """Run Mode B agentic recovery extraction using Browser-Use."""
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
        return _low_confidence_result(f"Mode B failed: {type(e).__name__}")
    finally:
        close = getattr(browser_session, "close", None)
        if close is not None:
            maybe_awaitable = close()
            if hasattr(maybe_awaitable, "__await__"):
                await maybe_awaitable

    result.mode = "B"
    logger.info("extraction_mode_b_complete", source_id=source_id, confidence=result.confidence)
    return result
