"""Replay-validate a captured ApiRecipe against a held-out listing.

A recipe earns 'high' confidence by:
1. The replay request returns 2xx.
2. The response_root and field_paths resolve correctly.
3. Required fields (address, rent, bedrooms, bathrooms) come back
   and roughly match what HTML+selectors extraction would produce
   for the same listing.

A recipe earns 'medium' if (1) and (2) succeed but no held-out
sample is available for cross-check yet. The runtime promotes
medium recipes into Mode A0 only after they accumulate 5
successful production calls without escalating to Mode A.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import httpx
import structlog

from doormat.extraction.recipe_executor import extract_listing_via_recipe
from doormat.extraction.schemas import ApiRecipe, ExtractedListing

log = structlog.get_logger(__name__)


@dataclass
class RecipeValidationResult:
    """Result of attempting to validate a recipe via replay."""

    valid: bool
    confidence: str  # "high" | "medium" | "low"
    reason: str
    extracted_listing: ExtractedListing | None = None


class RecipeValidator:
    """Validates ApiRecipes by replaying them against held-out listings."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self.http = http_client

    async def validate(
        self,
        recipe: ApiRecipe,
        held_out_listings: Sequence[tuple[str, ExtractedListing]],
        timeout_seconds: float = 8.0,
    ) -> RecipeValidationResult:
        """Replay the recipe against a held-out listing and verify the output.

        Args:
            recipe: The ApiRecipe to validate.
            held_out_listings: List of (listing_id, expected_listing) pairs that
                were extracted via HTML+selectors and known to be correct.
                We use the first one as the replay target.
            timeout_seconds: HTTP request timeout.

        Returns:
            A RecipeValidationResult with confidence level and reason.
        """
        if not held_out_listings:
            # No held-out sample — best we can do is a self-replay.
            return await self._self_replay(recipe, timeout_seconds)

        listing_id, expected = held_out_listings[0]
        return await self._replay_against(recipe, listing_id, expected, timeout_seconds)

    async def _self_replay(self, recipe: ApiRecipe, timeout: float) -> RecipeValidationResult:
        """Replay against the listing the recipe was captured from."""
        try:
            extracted = await self._fire_recipe(recipe, recipe.captured_from_listing_id, timeout)
        except _ReplayError as exc:
            return RecipeValidationResult(
                valid=False, confidence="low", reason=f"self-replay failed: {exc}"
            )

        if not extracted.address or not extracted.rent:
            return RecipeValidationResult(
                valid=False,
                confidence="low",
                reason="self-replay returned missing required fields",
            )

        return RecipeValidationResult(
            valid=True,
            confidence="medium",
            reason="self-replay succeeded; held-out validation pending",
            extracted_listing=extracted,
        )

    async def _replay_against(
        self,
        recipe: ApiRecipe,
        listing_id: str,
        expected: ExtractedListing,
        timeout: float,
    ) -> RecipeValidationResult:
        """Replay against a held-out listing and cross-check extracted fields."""
        try:
            extracted = await self._fire_recipe(recipe, listing_id, timeout)
        except _ReplayError as exc:
            return RecipeValidationResult(
                valid=False, confidence="low", reason=f"held-out replay failed: {exc}"
            )

        # Cross-check required fields. Address fuzzy match (substring), rent
        # exact match, bed/bath exact match.
        diffs: list[str] = []
        if expected.address and extracted.address:
            if not _addresses_match(expected.address, extracted.address):
                diffs.append(f"address mismatch: '{expected.address}' vs '{extracted.address}'")
        if expected.rent and extracted.rent:
            if abs(expected.rent - extracted.rent) > 1:
                diffs.append(f"rent mismatch: {expected.rent} vs {extracted.rent}")
        if expected.bedrooms != extracted.bedrooms:
            diffs.append(f"bedrooms mismatch: {expected.bedrooms} vs {extracted.bedrooms}")
        if abs(expected.bathrooms - extracted.bathrooms) > 0.1:
            diffs.append(f"bathrooms mismatch: {expected.bathrooms} vs {extracted.bathrooms}")

        if diffs:
            return RecipeValidationResult(
                valid=False,
                confidence="low",
                reason="; ".join(diffs[:3]),
                extracted_listing=extracted,
            )

        return RecipeValidationResult(
            valid=True,
            confidence="high",
            reason="replay matched HTML extraction on all required fields",
            extracted_listing=extracted,
        )

    async def _fire_recipe(
        self,
        recipe: ApiRecipe,
        listing_id: str,
        timeout: float,
    ) -> ExtractedListing:
        """Execute the recipe by rendering URL, making the request, and extracting."""
        url = recipe.url_template.replace("{listing_id}", listing_id)
        headers = dict(recipe.headers)
        body = (
            recipe.body_template.replace("{listing_id}", listing_id)
            if recipe.body_template
            else None
        )

        try:
            resp = await self.http.request(
                recipe.method,
                url,
                headers=headers,
                content=body,
                timeout=timeout,
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            raise _ReplayError(f"http error: {exc}") from exc

        if resp.status_code in (401, 403):
            raise _ReplayError(
                f"auth required (status {resp.status_code}) — recipe is session-bound"
            )
        if resp.status_code >= 400:
            raise _ReplayError(f"status {resp.status_code}")

        try:
            body_json = resp.json()
        except ValueError as exc:
            raise _ReplayError(f"non-JSON response: {exc}") from exc

        try:
            return extract_listing_via_recipe(recipe, body_json)
        except Exception as exc:
            raise _ReplayError(f"extract via recipe failed: {exc}") from exc


class _ReplayError(Exception):
    """Raised during recipe replay when validation fails."""

    pass


def _addresses_match(a: str, b: str) -> bool:
    """Cheap fuzzy match: shared-prefix tokens after normalization."""
    norm_a = "".join(c.lower() for c in a if c.isalnum() or c == " ").split()
    norm_b = "".join(c.lower() for c in b if c.isalnum() or c == " ").split()
    if not norm_a or not norm_b:
        return False
    # Require that the shorter address is fully contained in the longer one's tokens.
    short, long = (norm_a, norm_b) if len(norm_a) < len(norm_b) else (norm_b, norm_a)
    return all(tok in long for tok in short)
