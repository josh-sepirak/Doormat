"""Mode A: Deterministic-first extraction."""

from typing import Optional, cast

import structlog

from doormat.extraction.schemas import ListingExtractionResult
from doormat.llm.client import get_llm_client
from doormat.llm.prompt_registry import DEFAULT_PROMPTS, PromptKey, get_effective_prompt
from doormat.models.orm import ExtractionStrategy, Preference

logger = structlog.get_logger(__name__)

MAX_MODE_A_HTML_CHARS = 120_000

SYSTEM_PROMPT = DEFAULT_PROMPTS[PromptKey.EXTRACTION_MODE_A_SYSTEM]
USER_TEMPLATE = DEFAULT_PROMPTS[PromptKey.EXTRACTION_MODE_A_USER]


def prepare_html_for_prompt(html: str) -> str:
    """Bound untrusted HTML before placing it in an LLM prompt."""
    if len(html) <= MAX_MODE_A_HTML_CHARS:
        return html
    omitted = len(html) - MAX_MODE_A_HTML_CHARS
    return f"{html[:MAX_MODE_A_HTML_CHARS]}\n\n[truncated {omitted} characters]"


async def run_mode_a(
    html: str,
    url: str,
    source_id: str,
    strategy: ExtractionStrategy | None,
    city: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    preference: Preference | None = None,
) -> ListingExtractionResult:
    """Run Mode A deterministic extraction against raw HTML.

    Uses `instructor` to extract a structured payload.
    """
    logger.info("extraction_mode_a_start", source_id=source_id, url=url, city=city)

    llm = get_llm_client(api_key=api_key)

    strategy_version = strategy.id if strategy else "none"

    system_prompt = get_effective_prompt(PromptKey.EXTRACTION_MODE_A_SYSTEM, preference)
    user_tpl = get_effective_prompt(PromptKey.EXTRACTION_MODE_A_USER, preference)
    prompt = user_tpl.format(
        source=source_id,
        url=url,
        strategy_version=strategy_version,
        html=prepare_html_for_prompt(html),
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    result = cast(
        ListingExtractionResult,
        await llm.complete(
            messages=messages,
            model=model,
            task="extraction",
            component="extraction",
            city=city,
            response_model=ListingExtractionResult,
            max_tokens=1000,
            temperature=0.0,
            cache_system_prompt=True,
        ),
    )

    result.mode = "A"

    logger.info(
        "extraction_mode_a_complete",
        source_id=source_id,
        confidence=result.confidence,
    )
    return result
