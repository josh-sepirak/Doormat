"""LLM-driven property manager search.

Asks the LLM to brainstorm candidate property managers serving a city based on
its training knowledge. Output is parsed via instructor as a Pydantic list.
"""

from __future__ import annotations

from typing import Optional, cast
from urllib.parse import urlparse

import structlog
from pydantic import BaseModel, Field

from doormat.discovery.models import DiscoveryCandidate, RunLoggerProtocol
from doormat.llm.client import LLMClient, get_llm_client
from doormat.llm.prompt_registry import DEFAULT_PROMPTS, PromptKey, get_effective_prompt
from doormat.models.orm import Preference

logger = structlog.get_logger(__name__)

# Back-compat default text (effective prompts may come from Preference overrides).
SEARCH_SYSTEM_PROMPT = DEFAULT_PROMPTS[PromptKey.DISCOVERY_SEARCH_SYSTEM]


class _SearchCandidate(BaseModel):
    """Internal Pydantic shape used as LLM response_model."""

    name: str = Field(..., min_length=1, max_length=255)
    website: str = Field(..., min_length=1, max_length=512)
    confidence: float = Field(..., ge=0.0, le=1.0)


class _SearchResponse(BaseModel):
    """Wrapper Pydantic for the LLM list response."""

    candidates: list[_SearchCandidate] = Field(default_factory=list)


class DiscoverySearchError(RuntimeError):
    """Raised when provider failure prevents candidate discovery."""


class DiscoverySearch:
    """LLM-backed search for candidate PMs in a city."""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        model: Optional[str] = None,
    ) -> None:
        self._llm = llm or get_llm_client()
        self._model = model

    async def find_candidates(
        self,
        city: str,
        refinement: str | None = None,
        run_logger: Optional[RunLoggerProtocol] = None,
        preference: Preference | None = None,
    ) -> list[DiscoveryCandidate]:
        """Return deduplicated candidates for a city."""
        model_label = self._model or "default"
        logger.info("search_start", city=city, refinement=bool(refinement))
        if run_logger:
            msg = f"Asking LLM for property managers in {city}"
            if refinement:
                msg += " (refined search)"
            await run_logger.info(f"{msg} — model: {model_label}", component="search")

        user_prompt = self._build_user_prompt(city, refinement)
        system_prompt = get_effective_prompt(PromptKey.DISCOVERY_SEARCH_SYSTEM, preference)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self._llm.complete(
                messages=messages,
                model=self._model,
                task="discovery",
                component="discovery",
                city=city,
                response_model=_SearchResponse,
                cache_system_prompt=True,
            )
            parsed = cast(_SearchResponse, response)
        except Exception as exc:
            logger.error("search_failed", city=city, error=str(exc))
            if run_logger:
                await run_logger.error(
                    f"LLM search failed: {type(exc).__name__}: {exc}", component="search"
                )
            raise DiscoverySearchError("candidate search provider failed") from exc

        candidates = [
            DiscoveryCandidate(
                name=c.name,
                website=c.website,
                city=city,
                confidence=c.confidence,
                source="llm_search",
            )
            for c in parsed.candidates
        ]

        deduped = _dedupe_by_domain(candidates)
        logger.info(
            "search_complete",
            city=city,
            raw_count=len(candidates),
            deduped_count=len(deduped),
        )
        if run_logger:
            await run_logger.info(
                f"LLM returned {len(candidates)} candidates ({len(deduped)} after dedup)",
                component="search",
            )
        return deduped

    @staticmethod
    def _build_user_prompt(city: str, refinement: str | None) -> str:
        """Build the per-city search prompt; appends refinement if given."""
        prompt = (
            f"List candidate property management companies that serve rentals in {city}. "
            "Return real companies you know exist."
        )
        if refinement:
            prompt += f"\n\nRefinement based on prior attempt: {refinement}"
        return prompt


def _dedupe_by_domain(candidates: list[DiscoveryCandidate]) -> list[DiscoveryCandidate]:
    """Deduplicate candidates by website registrable domain (host)."""
    seen: set[str] = set()
    out: list[DiscoveryCandidate] = []
    for cand in candidates:
        host = _normalize_host(cand.website)
        if host in seen:
            continue
        seen.add(host)
        out.append(cand)
    return out


def _normalize_host(url: str) -> str:
    """Lowercase host, stripping leading 'www.' for dedup purposes."""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.hostname or url).lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return url.lower()
