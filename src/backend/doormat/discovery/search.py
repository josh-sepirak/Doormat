"""LLM-driven property manager search.

Asks the LLM to brainstorm candidate property managers serving a city based on
its training knowledge. Output is parsed via instructor as a Pydantic list.
"""

from __future__ import annotations

from typing import Optional, cast
from urllib.parse import urlparse

import structlog
from pydantic import BaseModel, Field

from doormat.discovery.models import DiscoveryCandidate
from doormat.llm.client import LLMClient, get_llm_client

logger = structlog.get_logger(__name__)

# v1 - initial search prompt
SEARCH_SYSTEM_PROMPT = """You are an expert at identifying real property management companies operating in US cities.

Given a city, list candidate property management companies most likely to manage rental units there. For each, provide:
- name: company name
- website: most likely public website URL (use https://)
- confidence: 0.0-1.0 - how certain are you this PM operates in the city

Bias toward locally-active mid-size PMs over national portals. Avoid aggregators (Zillow, Apartments.com).

Return between 5 and 15 candidates.
"""

DEFAULT_SEARCH_MODEL = "google/gemma-4-31b-it:free"


class _SearchCandidate(BaseModel):
    """Internal Pydantic shape used as LLM response_model."""

    name: str = Field(..., min_length=1, max_length=255)
    website: str = Field(..., min_length=1, max_length=512)
    confidence: float = Field(..., ge=0.0, le=1.0)


class _SearchResponse(BaseModel):
    """Wrapper Pydantic for the LLM list response."""

    candidates: list[_SearchCandidate] = Field(default_factory=list)


class DiscoverySearch:
    """LLM-backed search for candidate PMs in a city."""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        model: str = DEFAULT_SEARCH_MODEL,
    ) -> None:
        self._llm = llm or get_llm_client()
        self._model = model

    async def find_candidates(
        self, city: str, refinement: str | None = None
    ) -> list[DiscoveryCandidate]:
        """Return deduplicated candidates for a city; empty list on error."""
        logger.info("search_start", city=city, refinement=bool(refinement))

        user_prompt = self._build_user_prompt(city, refinement)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self._llm.complete(
                messages=messages,
                model=self._model,
                response_model=_SearchResponse,
            )
            parsed = cast(_SearchResponse, response)
        except Exception as exc:
            logger.error("search_failed", city=city, error=str(exc))
            return []

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
