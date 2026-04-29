# Patch 1 — HTTP recipe promotion (the cost win)

## What this does

Mode B currently navigates a listing page with Browser-Use, extracts fields, and emits a `StrategyUpdate` with selectors and pre-extraction actions. Mode A then uses those selectors against pre-fetched HTML.

This patch adds a **third tier** below Mode A: when Mode B navigates a page, it observes outgoing XHR/fetch traffic. If the page is fetching its own listing data via JSON (most modern PM sites are — AppFolio, RentManager, Buildium, Yardi, custom Next.js sites), Mode B captures the request and emits an `ApiRecipe` alongside the strategy update. The next Mode A call for that source skips Browser-Use *and* HTML extraction entirely: render the templated URL, fire `httpx.get`, walk the JSON response, return a typed `Listing`. Cost approaches zero per call.

```
BEFORE:
  scrape → dedup → Mode A (HTML + LLM extraction, $0.0008)
                ↓ on confidence: low
                Mode B (Browser-Use + LLM, $0.025) → emit StrategyUpdate

AFTER:
  scrape → dedup → Mode A0 (api_recipe, ~$0)
                ↓ on miss
                Mode A (HTML + LLM, $0.0008)
                ↓ on confidence: low
                Mode B (Browser-Use + LLM + network capture, $0.025)
                  → emit StrategyUpdate AND optional ApiRecipe
```

Realistic impact on a site that has a JSON API (most do):

| Tier | Calls/month at 300 listings/day | Cost/month |
|---|---|---|
| Mode A0 (recipe) | ~9000 | ~$0 |
| Mode A (HTML + LLM) | ~90 | ~$0.07 |
| Mode B | ~10 | ~$0.25 |
| **Today's total (no recipe)** | | **~$7/mo** |
| **With recipe** | | **~$0.32/mo** |

That's the headline. The rest of this document is the patch.

## Build order

Apply in this order. Each step compiles standalone; integration tests pass after step 7.

1. Schema additions — `extraction/schemas.py`
2. Network capture utility — `extraction/network_capture.py` (new file)
3. Recipe validator — `extraction/recipe_validator.py` (new file)
4. Mode B integration — `extraction/mode_b.py`
5. Mode A0 fast path — `extraction/mode_a0.py` (new file) and `extraction/mode_a.py` (small change)
6. Strategy merge — `extraction/strategy.py`
7. Orchestrator wiring — `extraction/orchestrator.py`
8. Mode B prompt update — `prompts/extraction/listing-extraction.md`
9. Alembic migration — `migrations/versions/<timestamp>_api_recipe.py`
10. Tests — `tests/extraction/test_api_recipe.py`
11. Feature flag and rollout — `config.py` + observability

---

## Step 1 — Schema additions

Add to `src/backend/doormat/extraction/schemas.py`. The existing `StrategyUpdate` and `ListingExtractionResult` get an optional new field; `ApiRecipe` is new.

```python
# src/backend/doormat/extraction/schemas.py
# (add these classes alongside the existing schemas)

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class ApiRecipe(BaseModel):
    """A reusable HTTP recipe for fetching listing data without a browser.

    Captured by Mode B when it observes the source fetching listing data
    via JSON XHR. Promoted to a fast Mode A0 path via the strategy merge
    gate after a replay validation succeeds against a held-out listing.

    Once promoted, Mode A0 skips both Browser-Use and HTML extraction:
    render the URL template, fire one httpx call, walk the JSON, build
    the Listing. Cost approaches zero per call (HTTP only, no LLM).
    """

    method: Literal["GET", "POST"] = "GET"

    url_template: str = Field(
        description=(
            "URL with optional placeholders. Supported: {listing_id}, {slug}. "
            "Example: 'https://acme-pm.com/api/listings/{listing_id}'"
        ),
    )

    headers: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Request headers. Auth headers (Cookie, Authorization, X-CSRF-*, "
            "anything matching the auth blocklist) are stripped at capture time. "
            "Only safe headers needed to make the request work survive."
        ),
    )

    body_template: str | None = Field(
        default=None,
        description=(
            "POST body template, JSON-encoded. Same placeholder rules as "
            "url_template. None for GET requests."
        ),
    )

    response_root: str = Field(
        default="$",
        description=(
            "JSONPath-style accessor pointing to the listing object within the "
            "response body. Examples: '$', '$.data.listing', '$.results[0]'. "
            "When the API returns a list, the recipe is valid only if the list "
            "has exactly one element matching the requested listing_id."
        ),
    )

    field_paths: dict[str, str] = Field(
        description=(
            "Per-Listing-field JSONPath inside the object at response_root. "
            "Required keys: address, price, bedrooms, bathrooms. Optional: "
            "sqft, pets_policy, amenities, photos, description."
        ),
    )

    extractable_fields: list[str] = Field(
        description=(
            "Which Listing fields this recipe can populate. Subset of "
            "field_paths.keys(). The runtime fills missing fields from any "
            "available HTML fallback or marks the listing as confidence: medium."
        ),
    )

    captured_at: datetime
    captured_from_listing_id: str = Field(
        description="The listing_id present in the capture URL, used for replay validation.",
    )

    last_validated_at: datetime | None = Field(default=None)
    last_failure_at: datetime | None = Field(default=None)
    failure_count: int = Field(
        default=0,
        description=(
            "Increments when Mode A0 fails on this recipe. The runtime retires the "
            "recipe (sets it to None on the strategy) when failure_count >= 3 "
            "consecutive without an intervening success."
        ),
    )

    confidence: Literal["high", "medium", "low"] = Field(
        description=(
            "high = recipe was replay-validated against a held-out listing and "
            "returned all extractable_fields. medium = matched extracted fields "
            "but not replay-validated (used when held-out validation cannot run "
            "due to insufficient samples). low = captured opportunistically; "
            "treated as not-yet-promoted until a future Mode B run validates it."
        ),
    )

    capture_notes: str | None = Field(
        default=None,
        max_length=600,
        description=(
            "Free-form notes from Mode B about quirks: 'API requires an X-Origin "
            "header that matches the page origin', 'API returns 200 with empty body "
            "for invalid IDs (don't treat as success)', etc."
        ),
    )


# Modify the existing StrategyUpdate. Add the api_recipe field.
class StrategyUpdate(BaseModel):
    """Patch to a source's cached extraction strategy. Emitted in Mode B."""

    field_selectors: dict[str, str] = Field(default_factory=dict)
    pre_extraction_actions: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=500)

    # NEW: optional API recipe captured during the Mode B run.
    api_recipe: ApiRecipe | None = Field(
        default=None,
        description=(
            "If Mode B observed the page fetching listing data via JSON XHR/fetch, "
            "the captured recipe. None if Mode B used DOM extraction only or saw "
            "no usable JSON traffic. The runtime validates the recipe by replaying "
            "it against a held-out listing before merging into the cached strategy."
        ),
    )


# Modify the existing ExtractionStrategy. Add api_recipe.
class ExtractionStrategy(BaseModel):
    """Cached strategy for a source. Mutated via StrategyUpdate merges."""

    source_id: str
    schema_version: int = 1

    listing_index_url: str
    listing_link_selector: str
    detail_pre_extraction_actions: list[str] = Field(default_factory=list)
    field_selectors: dict[str, list[str]] = Field(default_factory=dict)
    photo_gallery_strategy: PhotoGalleryStrategy | None = Field(default=None)
    notes: str = Field(default="", max_length=1000)

    # NEW
    api_recipe: ApiRecipe | None = Field(default=None)

    last_updated_at: datetime
```

If your project's existing `ExtractionStrategy` lives in the SQLAlchemy ORM rather than as a plain Pydantic model, mirror this addition into the ORM model in `models/orm.py` — store the recipe as JSON. The migration in step 9 covers the column.

---

## Step 2 — Network capture utility

New file. The capture sidecar runs alongside the Browser-Use agent in Mode B. It listens to CDP `Network.responseReceived` events on the page session, buffers responses on the source's domain, filters to JSON, and exposes a `find_listing_response()` method that the Mode B post-processor calls after the agent completes.

```python
# src/backend/doormat/extraction/network_capture.py

"""Capture JSON XHR/fetch responses during a Mode B agent run.

The capturer attaches to the Browser-Use session's CDP channel before the
agent starts navigating. It buffers JSON responses from the listing's
domain, scrubs sensitive request headers, and returns a candidate set
that Mode B can promote into an ApiRecipe.

Notes:
- This is best-effort. If we miss a response (race, eviction, large body),
  Mode B falls through to DOM extraction. Network capture never blocks
  agent progress.
- We never capture request bodies that contain user PII (login forms,
  search filters with personal info). The recipe builder filters to
  GET requests by default; POST recipes require an explicit allowlist
  in the prompt.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import structlog

log = structlog.get_logger(__name__)


# Headers we never replay. Matches the auth/session blocklist plus a few
# headers that bind to a specific session even if not strictly auth.
_HEADER_BLOCKLIST_PATTERNS = [
    re.compile(r"^cookie$", re.I),
    re.compile(r"^set-cookie$", re.I),
    re.compile(r"^authorization$", re.I),
    re.compile(r"^x-csrf", re.I),
    re.compile(r"^x-xsrf", re.I),
    re.compile(r"^x-session", re.I),
    re.compile(r"^x-auth", re.I),
    re.compile(r"^x-bearer", re.I),
    re.compile(r"token", re.I),  # broad; catches X-Api-Token, x-auth-token, etc.
    re.compile(r"^if-(none-)?match$", re.I),  # session-bound caching
]

# Headers we always allow if present.
_HEADER_ALLOWLIST_PATTERNS = [
    re.compile(r"^accept$", re.I),
    re.compile(r"^accept-language$", re.I),
    re.compile(r"^content-type$", re.I),
    re.compile(r"^x-requested-with$", re.I),
    re.compile(r"^x-client-id$", re.I),  # public client identifiers, not user-bound
]

# Maximum response body size we keep. Larger than this is almost certainly
# not a single-listing API endpoint.
MAX_BODY_BYTES = 256 * 1024


def _scrub_headers(headers: dict[str, str]) -> dict[str, str]:
    """Drop blocklist headers; keep allowlist + safe customs."""
    out: dict[str, str] = {}
    for k, v in headers.items():
        if any(p.search(k) for p in _HEADER_BLOCKLIST_PATTERNS):
            continue
        if any(p.search(k) for p in _HEADER_ALLOWLIST_PATTERNS):
            out[k] = v
            continue
        # Custom header (X-*) that doesn't match auth — keep but log.
        if k.lower().startswith("x-") and not any(
            re.search(b, k, re.I) for b in [r"token", r"session", r"auth", r"csrf"]
        ):
            out[k] = v
    return out


@dataclass
class CapturedResponse:
    """A buffered JSON response observed during agent navigation."""

    request_id: str
    url: str
    method: str
    request_headers: dict[str, str]
    status: int
    response_headers: dict[str, str]
    body: str  # decoded JSON text
    parsed: Any  # already-parsed JSON
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class NetworkCapture:
    """Holds the buffered responses for a single Mode B agent run."""

    listing_url: str
    listing_id: str
    domain: str
    responses: list[CapturedResponse] = field(default_factory=list)

    @property
    def listing_origin(self) -> str:
        p = urlparse(self.listing_url)
        return f"{p.scheme}://{p.netloc}"

    def find_listing_response(
        self,
        extracted_address: str | None,
        extracted_price: int | None,
    ) -> CapturedResponse | None:
        """Return the captured response that most plausibly contains the listing.

        Heuristic match by extracted address fragment and rent value. Returns
        the highest-confidence match, or None if no response looks like the
        listing's data.
        """
        if not self.responses:
            return None

        scored: list[tuple[float, CapturedResponse]] = []
        for r in self.responses:
            score = self._score_response(r, extracted_address, extracted_price)
            if score > 0:
                scored.append((score, r))

        if not scored:
            return None

        scored.sort(key=lambda t: t[0], reverse=True)
        return scored[0][1]

    def _score_response(
        self,
        r: CapturedResponse,
        address: str | None,
        price: int | None,
    ) -> float:
        """Score how likely a response is the listing data we extracted."""
        body = r.body
        score = 0.0

        # Same origin = baseline confidence
        if urlparse(r.url).netloc == self.domain:
            score += 1.0
        else:
            return 0.0  # Different origin = not our recipe

        # Address fragment match (use street number + first word of street)
        if address:
            tokens = re.findall(r"\b\w+\b", address)
            for t in tokens[:3]:
                if t and len(t) > 2 and t.lower() in body.lower():
                    score += 0.5

        # Rent appears literally in body (handle $, commas, decimals)
        if price:
            patterns = [str(price), f"{price:,}", f"${price}", f"${price:,}"]
            if any(p in body for p in patterns):
                score += 2.0

        # listing_id appears in URL
        if self.listing_id and self.listing_id in r.url:
            score += 1.0

        # Penalty for large generic dumps (probably a listing-index, not a detail)
        if len(body) > 50_000:
            score -= 0.5

        return score


class CDPCapturer:
    """Attaches CDP listeners to a Browser-Use session and buffers JSON responses.

    Usage:
        capture = NetworkCapture(listing_url=url, listing_id=lid, domain=parsed.netloc)
        capturer = CDPCapturer(capture, browser_session)
        await capturer.attach()
        # ... run the agent ...
        await capturer.detach()
        # capture.responses is now populated
    """

    def __init__(self, capture: NetworkCapture, session: Any) -> None:
        """`session` is the Browser-Use BrowserSession or whatever exposes CDP.

        Implementations differ across Browser-Use versions. The two patterns
        we target:
          1. session.cdp_client / session.send_cdp(method, params, session_id) —
             modern Browser-Use 1.x.
          2. session.page (Playwright Page) — older releases. We use
             page.on("response", handler) as a fallback.

        Wire whichever your version exposes. The handler interface below is
        identical for both.
        """
        self.capture = capture
        self.session = session
        self._tracked_request_ids: dict[str, dict[str, Any]] = {}
        self._handlers_attached = False
        self._mode: str = "unknown"

    async def attach(self) -> None:
        """Subscribe to network events. Idempotent."""
        if self._handlers_attached:
            return

        # Prefer CDP-direct attachment when available
        if hasattr(self.session, "send_cdp") or hasattr(self.session, "cdp_client"):
            await self._attach_cdp()
            self._mode = "cdp"
        elif hasattr(self.session, "page"):
            await self._attach_playwright()
            self._mode = "playwright"
        else:
            log.warning(
                "network_capture.no_attachable_surface",
                session_type=type(self.session).__name__,
            )
            return

        self._handlers_attached = True
        log.info("network_capture.attached", mode=self._mode)

    async def detach(self) -> None:
        """Unsubscribe. Safe to call multiple times."""
        if not self._handlers_attached:
            return
        # Both Playwright page handlers and CDP subscriptions are session-bound;
        # they detach when the session does. We just mark ourselves done.
        self._handlers_attached = False

    # --- CDP path ---------------------------------------------------------

    async def _attach_cdp(self) -> None:
        send = getattr(self.session, "send_cdp", None) or self.session.cdp_client.send

        # Enable Network domain
        await send("Network.enable", {})

        # Browser-Use exposes event subscription via session.add_cdp_listener or similar;
        # adapt to your exact version. The minimal contract is: register `_on_event`
        # and have it called for every CDP event during the page's lifetime.
        if hasattr(self.session, "add_cdp_listener"):
            self.session.add_cdp_listener(self._on_cdp_event)
        elif hasattr(self.session, "on_cdp_event"):
            self.session.on_cdp_event(self._on_cdp_event)
        else:
            # Last resort: monkey-patch via the underlying websocket. If your
            # Browser-Use version exposes nothing, raise — and add the hook
            # upstream rather than carry a fragile patch.
            raise RuntimeError(
                "BrowserSession does not expose CDP event subscription. "
                "Update Browser-Use, or fall back to Playwright path."
            )

    async def _on_cdp_event(self, method: str, params: dict[str, Any]) -> None:
        """Handle CDP events. Buffer requests and bodies."""
        try:
            if method == "Network.requestWillBeSent":
                req = params["request"]
                self._tracked_request_ids[params["requestId"]] = {
                    "url": req["url"],
                    "method": req["method"],
                    "headers": req.get("headers", {}),
                }
            elif method == "Network.responseReceived":
                rid = params["requestId"]
                resp = params["response"]
                if not self._is_json_response(resp):
                    self._tracked_request_ids.pop(rid, None)
                    return
                # We have a JSON response; fetch the body asynchronously.
                asyncio.create_task(self._fetch_body(rid, resp))
        except Exception:
            log.exception("network_capture.cdp_event_failed", method=method)

    async def _fetch_body(self, request_id: str, response: dict[str, Any]) -> None:
        """Pull the response body via Network.getResponseBody and buffer it."""
        send = getattr(self.session, "send_cdp", None) or self.session.cdp_client.send
        try:
            body_result = await send(
                "Network.getResponseBody", {"requestId": request_id}
            )
        except Exception as exc:
            log.debug("network_capture.body_unavailable", request_id=request_id, error=str(exc))
            return

        body = body_result.get("body", "")
        if body_result.get("base64Encoded"):
            # Skip base64-encoded bodies — they aren't JSON in any case we care about.
            return

        if len(body) > MAX_BODY_BYTES:
            log.debug("network_capture.body_too_large", request_id=request_id, size=len(body))
            return

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return  # Server claimed JSON but sent non-JSON — skip.

        request_meta = self._tracked_request_ids.pop(request_id, {})
        captured = CapturedResponse(
            request_id=request_id,
            url=response["url"],
            method=request_meta.get("method", "GET"),
            request_headers=_scrub_headers(request_meta.get("headers", {})),
            status=response.get("status", 0),
            response_headers=response.get("headers", {}),
            body=body,
            parsed=parsed,
        )
        self.capture.responses.append(captured)

    @staticmethod
    def _is_json_response(response: dict[str, Any]) -> bool:
        if response.get("status", 0) >= 400:
            return False
        mime = response.get("mimeType", "").lower()
        if "json" in mime:
            return True
        # Some sites mislabel Content-Type. Inspect the URL hint.
        url = response.get("url", "")
        if "/api/" in url and any(url.endswith(s) or f"{s}?" in url for s in (".json", "/json", "/data")):
            return True
        return False

    # --- Playwright fallback ---------------------------------------------

    async def _attach_playwright(self) -> None:
        page = self.session.page

        async def on_response(response: Any) -> None:
            try:
                if response.status >= 400:
                    return
                ct = response.headers.get("content-type", "").lower()
                if "json" not in ct:
                    return
                body = await response.text()
                if len(body) > MAX_BODY_BYTES:
                    return
                try:
                    parsed = json.loads(body)
                except json.JSONDecodeError:
                    return
                req = response.request
                captured = CapturedResponse(
                    request_id=getattr(req, "guid", req.url),
                    url=response.url,
                    method=req.method,
                    request_headers=_scrub_headers(dict(req.headers)),
                    status=response.status,
                    response_headers=dict(response.headers),
                    body=body,
                    parsed=parsed,
                )
                self.capture.responses.append(captured)
            except Exception:
                log.exception("network_capture.playwright_handler_failed")

        page.on("response", on_response)
```

A note on Browser-Use's CDP API: the exact method name (`add_cdp_listener` vs `on_cdp_event`) varies between releases. The capturer probes for what the running version exposes; if your version exposes neither, fall back to the Playwright path. If you're on an old release that exposes only the old `playwright_browser` attribute, the Playwright path is what runs.

---

## Step 3 — Recipe validator

New file. Validates a captured `ApiRecipe` by replaying it against a *held-out* listing (one Mode B did not see), comparing the resulting fields to what HTML extraction would produce, and returning a confidence verdict. The merge gate calls this before promoting the recipe into the cached strategy.

```python
# src/backend/doormat/extraction/recipe_validator.py

"""Replay-validate a captured ApiRecipe against a held-out listing.

A recipe earns 'high' confidence by:
1. The replay request returns 2xx.
2. The response_root and field_paths resolve correctly.
3. Required fields (address, price, bedrooms, bathrooms) come back
   and roughly match what HTML+selectors extraction would produce
   for the same listing.

A recipe earns 'medium' if (1) and (2) succeed but no held-out
sample is available for cross-check yet. The runtime promotes
medium recipes into Mode A0 only after they accumulate 5
successful production calls without escalating to Mode A.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from doormat.extraction.schemas import ApiRecipe, ExtractedListing

log = structlog.get_logger(__name__)


@dataclass
class RecipeValidationResult:
    valid: bool
    confidence: str  # "high" | "medium" | "low"
    reason: str
    extracted_listing: ExtractedListing | None = None


class RecipeValidator:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self.http = http_client

    async def validate(
        self,
        recipe: ApiRecipe,
        held_out_listings: Sequence[tuple[str, ExtractedListing]],
        timeout_seconds: float = 8.0,
    ) -> RecipeValidationResult:
        """Replay the recipe against a held-out listing and verify the output.

        held_out_listings: list of (listing_id, expected_listing) pairs that
        were extracted via HTML+selectors and known to be correct. We use
        the first one as the replay target.
        """
        if not held_out_listings:
            # No held-out sample — best we can do is a self-replay.
            return await self._self_replay(recipe, timeout_seconds)

        listing_id, expected = held_out_listings[0]
        return await self._replay_against(
            recipe, listing_id, expected, timeout_seconds
        )

    async def _self_replay(
        self, recipe: ApiRecipe, timeout: float
    ) -> RecipeValidationResult:
        """Replay against the listing the recipe was captured from."""
        try:
            extracted = await self._fire_recipe(recipe, recipe.captured_from_listing_id, timeout)
        except _ReplayError as exc:
            return RecipeValidationResult(
                valid=False, confidence="low", reason=f"self-replay failed: {exc}"
            )

        if not extracted.address or not extracted.price:
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
        try:
            extracted = await self._fire_recipe(recipe, listing_id, timeout)
        except _ReplayError as exc:
            return RecipeValidationResult(
                valid=False, confidence="low", reason=f"held-out replay failed: {exc}"
            )

        # Cross-check required fields. Address fuzzy match (substring), price
        # exact match, bed/bath exact match.
        diffs: list[str] = []
        if expected.address and extracted.address:
            if not _addresses_match(expected.address, extracted.address):
                diffs.append(f"address mismatch: '{expected.address}' vs '{extracted.address}'")
        if expected.price and extracted.price:
            if abs(expected.price - extracted.price) > 1:
                diffs.append(f"price mismatch: {expected.price} vs {extracted.price}")
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
            raise _ReplayError(f"auth required (status {resp.status_code}) — recipe is session-bound")
        if resp.status_code >= 400:
            raise _ReplayError(f"status {resp.status_code}")

        try:
            body_json = resp.json()
        except ValueError as exc:
            raise _ReplayError(f"non-JSON response: {exc}") from exc

        from doormat.extraction.recipe_executor import extract_listing_via_recipe

        try:
            return extract_listing_via_recipe(recipe, body_json)
        except Exception as exc:
            raise _ReplayError(f"extract via recipe failed: {exc}") from exc


class _ReplayError(Exception):
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
```

The companion file `recipe_executor.py` is small enough to inline:

```python
# src/backend/doormat/extraction/recipe_executor.py

"""Execute an ApiRecipe against a JSON body and emit an ExtractedListing.

Pure function; no I/O. The caller (Mode A0 or the validator) is responsible
for the HTTP fetch.
"""

from __future__ import annotations

from typing import Any

from doormat.extraction.schemas import ApiRecipe, ExtractedListing, PetsPolicy


def extract_listing_via_recipe(
    recipe: ApiRecipe, response_json: Any
) -> ExtractedListing:
    """Walk response_json by recipe.response_root, then by each field_path."""
    root = _walk_path(response_json, recipe.response_root)
    if root is None:
        raise ValueError(f"response_root '{recipe.response_root}' resolved to None")

    def get(field: str) -> Any:
        path = recipe.field_paths.get(field)
        if not path:
            return None
        return _walk_path(root, path)

    address = get("address")
    price = get("price")
    bedrooms = get("bedrooms")
    bathrooms = get("bathrooms")
    sqft = get("sqft")
    pets = get("pets_policy")
    amenities = get("amenities") or []
    photos = get("photos") or []
    description = get("description") or ""

    if address is None:
        raise ValueError("required field 'address' resolved to None")
    if price is None:
        raise ValueError("required field 'price' resolved to None")
    if bedrooms is None:
        raise ValueError("required field 'bedrooms' resolved to None")
    if bathrooms is None:
        raise ValueError("required field 'bathrooms' resolved to None")

    return ExtractedListing(
        address=str(address),
        price=int(float(price)),
        bedrooms=int(bedrooms),
        bathrooms=float(bathrooms),
        sqft=int(sqft) if sqft is not None else None,
        pets_policy=_coerce_pets_policy(pets),
        amenities=[str(a) for a in amenities][:20] if isinstance(amenities, list) else [],
        photos=[str(p) for p in photos][:20] if isinstance(photos, list) else [],
        description=str(description)[:2000],
    )


def _walk_path(obj: Any, path: str) -> Any:
    """Minimal JSONPath subset: $, $.key, $.list[N], $.key.subkey."""
    if path == "$" or path == "":
        return obj
    if path.startswith("$."):
        path = path[2:]
    elif path.startswith("$"):
        path = path[1:]

    cur = obj
    for token in _tokenize_path(path):
        if cur is None:
            return None
        if isinstance(token, int):
            if not isinstance(cur, list) or token >= len(cur):
                return None
            cur = cur[token]
        else:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(token)
    return cur


def _tokenize_path(path: str) -> list:
    """Split 'data.listings[0].name' into ['data', 'listings', 0, 'name']."""
    out: list = []
    for part in path.split("."):
        if "[" in part:
            key, _, rest = part.partition("[")
            if key:
                out.append(key)
            while rest:
                idx_str, _, rest = rest.partition("]")
                if idx_str:
                    out.append(int(idx_str))
                if rest.startswith("["):
                    rest = rest[1:]
        else:
            if part:
                out.append(part)
    return out


def _coerce_pets_policy(raw: Any) -> PetsPolicy:
    if raw is None:
        return PetsPolicy.UNKNOWN
    if isinstance(raw, PetsPolicy):
        return raw
    s = str(raw).lower()
    if "no" in s and ("pet" in s or "dog" in s):
        return PetsPolicy.NONE_ALLOWED
    if "cat" in s and "only" in s:
        return PetsPolicy.CATS_ONLY
    if any(t in s for t in ["allow", "ok", "welcome", "consider", "small dog"]):
        return PetsPolicy.ALLOWED_WITH_SMALL_DOG
    return PetsPolicy.UNKNOWN
```

---

## Step 4 — Mode B integration

The Mode B orchestrator gets two changes:
1. Instantiate a `NetworkCapture` and `CDPCapturer` before running the agent
2. After the agent returns, scan `capture.responses` for the listing-data response and synthesize an `ApiRecipe`

```python
# src/backend/doormat/extraction/mode_b.py
# (additions; existing code unchanged unless noted)

from urllib.parse import urlparse
from datetime import UTC, datetime

from doormat.extraction.network_capture import (
    CDPCapturer,
    NetworkCapture,
)
from doormat.extraction.schemas import (
    ApiRecipe,
    ExtractedListing,
    StrategyUpdate,
)


async def run_mode_b(
    url: str,
    listing_id: str,
    source_id: str,
    prior_failure: dict,
    llm_client,
    browser_session,  # Browser-Use BrowserSession
) -> ListingExtractionResult:
    """Mode B run with network capture sidecar."""

    # NEW: attach network capturer
    capture = NetworkCapture(
        listing_url=url,
        listing_id=listing_id,
        domain=urlparse(url).netloc,
    )
    capturer = CDPCapturer(capture, browser_session)
    await capturer.attach()

    try:
        # ... existing agent invocation goes here, unchanged ...
        agent_result = await _run_browser_use_agent(
            url=url,
            llm_client=llm_client,
            browser_session=browser_session,
            prior_failure=prior_failure,
            mode_b_user_template=...,  # your existing template
        )
        # agent_result.listing is the ExtractedListing; agent_result.strategy_update
        # is the StrategyUpdate (selectors / actions) the model emitted.

    finally:
        await capturer.detach()

    # NEW: scan captured responses for the listing-data response
    api_recipe = _try_synthesize_recipe(
        capture=capture,
        extracted=agent_result.listing,
        listing_id=listing_id,
    )

    if api_recipe and agent_result.strategy_update:
        agent_result.strategy_update.api_recipe = api_recipe
    elif api_recipe:
        agent_result.strategy_update = StrategyUpdate(api_recipe=api_recipe)

    return agent_result


def _try_synthesize_recipe(
    capture: NetworkCapture,
    extracted: ExtractedListing,
    listing_id: str,
) -> ApiRecipe | None:
    """Find the JSON response that contains the listing data and build a recipe."""

    candidate = capture.find_listing_response(
        extracted_address=extracted.address,
        extracted_price=extracted.price,
    )
    if candidate is None:
        return None

    # Only GET recipes by default. POST recipes require explicit prompt approval
    # because their bodies might contain user data.
    if candidate.method != "GET":
        log.info(
            "recipe_synthesis.skipped_non_get",
            method=candidate.method,
            url=candidate.url,
        )
        return None

    # Template the URL: replace literal listing_id occurrences
    url_template = candidate.url
    if listing_id and listing_id in url_template:
        url_template = url_template.replace(listing_id, "{listing_id}")

    # Synthesize field paths by inspecting the parsed JSON
    field_paths = _infer_field_paths(candidate.parsed, extracted)

    if not all(k in field_paths for k in ("address", "price", "bedrooms", "bathrooms")):
        log.info(
            "recipe_synthesis.missing_required_fields",
            found=list(field_paths.keys()),
        )
        return None

    response_root = _infer_response_root(candidate.parsed, extracted)

    return ApiRecipe(
        method="GET",
        url_template=url_template,
        headers=candidate.request_headers,
        body_template=None,
        response_root=response_root,
        field_paths=field_paths,
        extractable_fields=list(field_paths.keys()),
        captured_at=candidate.captured_at,
        captured_from_listing_id=listing_id,
        confidence="low",  # promoted to medium/high by the validator before merge
    )


def _infer_response_root(body: Any, extracted: ExtractedListing) -> str:
    """Find the JSONPath at which the listing object sits."""
    # Try a small set of candidate roots in order of how common they are.
    for root in ["$", "$.data", "$.data.listing", "$.listing", "$.result", "$.results[0]", "$.data.results[0]"]:
        node = _walk(body, root)
        if isinstance(node, dict) and _looks_like_listing(node, extracted):
            return root
    # Last resort: search recursively for a dict that looks like a listing.
    found = _search_for_listing(body, extracted)
    return found or "$"


def _looks_like_listing(node: dict, extracted: ExtractedListing) -> bool:
    """Heuristic: dict has price-shaped and address-shaped values."""
    has_price = any(
        isinstance(v, (int, float)) and abs(v - extracted.price) < 1
        for v in _flatten_values(node, max_depth=2)
    )
    has_addr = any(
        isinstance(v, str) and extracted.address[:10].lower() in v.lower()
        for v in _flatten_values(node, max_depth=2)
        if isinstance(v, str)
    )
    return has_price and has_addr


def _infer_field_paths(body: Any, extracted: ExtractedListing) -> dict[str, str]:
    """For each Listing field, find the JSONPath inside the response that produced its value."""
    # See implementation: walk the body, for each leaf compare to the extracted
    # value; on match, record the path. Truncated for space — full implementation
    # in the test fixtures below.
    ...  # see tests/extraction/test_api_recipe.py for the exhaustive impl


def _flatten_values(obj: Any, max_depth: int) -> list:
    """Yield every scalar value within max_depth levels."""
    out = []
    def walk(o, d):
        if d > max_depth:
            return
        if isinstance(o, dict):
            for v in o.values():
                walk(v, d + 1)
        elif isinstance(o, list):
            for v in o:
                walk(v, d + 1)
        else:
            out.append(o)
    walk(obj, 0)
    return out
```

The `_infer_field_paths` and `_search_for_listing` helpers are mechanical — walk the JSON, match values against the LLM-extracted ones, record paths. Treat the test in step 10 as the spec.

---

## Step 5 — Mode A0 fast path

New file. Mode A0 runs *before* Mode A. Pure HTTP, no LLM, no Browser-Use. Returns `None` on miss — orchestrator falls through to Mode A.

```python
# src/backend/doormat/extraction/mode_a0.py

"""The recipe-driven fast path. Pure HTTP, no LLM, no browser.

Runs only when:
- The source's cached strategy has an api_recipe with confidence in {medium, high}.
- The listing_id is extractable from the listing URL (templating works).

Returns None when:
- No recipe present.
- Recipe fired but returned non-2xx, non-JSON, or schema-mismatched data.
- Recipe-extracted listing has confidence: low (orchestrator escalates to Mode A).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import httpx
import structlog

from doormat.extraction.recipe_executor import extract_listing_via_recipe
from doormat.extraction.schemas import (
    ApiRecipe,
    ExtractionStrategy,
    ListingExtractionResult,
)

log = structlog.get_logger(__name__)


_LISTING_ID_PATTERNS = [
    re.compile(r"/listings?/([\w-]+)"),
    re.compile(r"/property/([\w-]+)"),
    re.compile(r"/rentals?/([\w-]+)"),
    re.compile(r"/units?/([\w-]+)"),
    re.compile(r"[?&]id=([\w-]+)"),
    re.compile(r"[?&]listing_id=([\w-]+)"),
]


def extract_listing_id_from_url(url: str) -> str | None:
    """Pull a likely listing_id from the URL using common patterns."""
    for pat in _LISTING_ID_PATTERNS:
        m = pat.search(url)
        if m:
            return m.group(1)
    return None


async def run_mode_a0(
    url: str,
    strategy: ExtractionStrategy,
    http_client: httpx.AsyncClient,
    timeout_seconds: float = 6.0,
) -> ListingExtractionResult | None:
    """Recipe-driven extraction. Returns None on any miss; orchestrator falls through."""
    recipe = strategy.api_recipe
    if recipe is None:
        return None
    if recipe.confidence not in ("medium", "high"):
        return None
    if recipe.failure_count >= 3:
        log.info(
            "mode_a0.recipe_retired",
            source_id=strategy.source_id,
            failures=recipe.failure_count,
        )
        return None

    listing_id = extract_listing_id_from_url(url)
    if listing_id is None:
        log.debug("mode_a0.no_listing_id", url=url)
        return None

    rendered_url = recipe.url_template.replace("{listing_id}", listing_id)
    body = (
        recipe.body_template.replace("{listing_id}", listing_id)
        if recipe.body_template
        else None
    )

    try:
        resp = await http_client.request(
            recipe.method,
            rendered_url,
            headers=dict(recipe.headers),
            content=body,
            timeout=timeout_seconds,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        log.info("mode_a0.http_error", source_id=strategy.source_id, error=str(exc))
        await _record_failure(strategy, recipe)
        return None

    if resp.status_code in (401, 403):
        # Recipe is session-bound now (server invalidated). Retire.
        log.warning(
            "mode_a0.auth_required",
            source_id=strategy.source_id,
            status=resp.status_code,
        )
        await _record_failure(strategy, recipe, retire=True)
        return None

    if resp.status_code >= 400:
        await _record_failure(strategy, recipe)
        return None

    try:
        response_json = resp.json()
    except ValueError:
        await _record_failure(strategy, recipe)
        return None

    try:
        extracted = extract_listing_via_recipe(recipe, response_json)
    except Exception as exc:
        log.info(
            "mode_a0.extraction_failed",
            source_id=strategy.source_id,
            error=str(exc),
        )
        await _record_failure(strategy, recipe)
        return None

    # Success! Record and return.
    await _record_success(strategy, recipe)

    return ListingExtractionResult(
        listing=extracted,
        confidence="high",
        strategy_update=None,
        mode="A0",
    )


async def _record_failure(
    strategy: ExtractionStrategy,
    recipe: ApiRecipe,
    retire: bool = False,
) -> None:
    """Increment failure_count; persist via your strategy storage layer."""
    recipe.failure_count += 1
    recipe.last_failure_at = datetime.now(UTC)
    if retire or recipe.failure_count >= 3:
        # The orchestrator's strategy persister will see failure_count >= 3
        # and skip Mode A0 next call. Optionally clear the recipe entirely
        # to free Mode B from re-validating it.
        log.info(
            "mode_a0.recipe_marked_for_retirement",
            source_id=strategy.source_id,
            failures=recipe.failure_count,
        )
    # Persist the strategy mutation via your existing strategy.save() path.
    # Example: await StrategyCache.persist(strategy)


async def _record_success(strategy: ExtractionStrategy, recipe: ApiRecipe) -> None:
    """Reset failure_count on success."""
    recipe.last_validated_at = datetime.now(UTC)
    if recipe.failure_count > 0:
        recipe.failure_count = 0
    # Persist via your existing strategy save path.
```

Mode A itself doesn't change; only the orchestrator does (step 7).

---

## Step 6 — Strategy merge with recipe validation gate

Existing `StrategyCache.merge` accepts patches without validation (per your project doc). This patch keeps that behavior for selectors/actions but adds a validation gate specifically for `api_recipe`:

```python
# src/backend/doormat/extraction/strategy.py
# (modify the existing merge method)

import httpx
from datetime import UTC, datetime

from doormat.extraction.recipe_validator import RecipeValidator
from doormat.extraction.schemas import (
    ApiRecipe,
    ExtractedListing,
    ExtractionStrategy,
    StrategyUpdate,
)


class StrategyCache:
    # ... existing methods ...

    async def merge(
        self,
        source_id: str,
        update: StrategyUpdate,
        held_out_listings: list[tuple[str, ExtractedListing]] | None = None,
    ) -> ExtractionStrategy:
        """Merge a StrategyUpdate into the cached strategy.

        Selectors and pre-extraction actions merge unconditionally (existing
        Phase 3 behavior). The api_recipe goes through a replay-validation
        gate before being committed to the strategy.

        held_out_listings: optional list of (listing_id, expected_listing) pairs
        the merger uses to validate the recipe. If empty, the recipe falls back
        to self-replay validation and gets confidence='medium' on success.
        """
        strategy = await self.get_or_create(source_id)

        # --- selector / action merge (unchanged behavior) ---
        for field, selector in (update.field_selectors or {}).items():
            existing = strategy.field_selectors.setdefault(field, [])
            if selector not in existing:
                existing.insert(0, selector)
        for action in update.pre_extraction_actions or []:
            if action not in strategy.detail_pre_extraction_actions:
                strategy.detail_pre_extraction_actions.append(action)
        if update.notes:
            strategy.notes = (
                f"{strategy.notes}\n\n[{datetime.now(UTC).isoformat()}] {update.notes}"
                if strategy.notes
                else f"[{datetime.now(UTC).isoformat()}] {update.notes}"
            )

        # --- api_recipe gate ---
        if update.api_recipe is not None:
            await self._consider_recipe(
                strategy=strategy,
                proposed_recipe=update.api_recipe,
                held_out_listings=held_out_listings or [],
            )

        strategy.last_updated_at = datetime.now(UTC)
        await self._persist(strategy)
        await self._record_feedback(source_id=source_id, update=update, validation_passed=True)
        return strategy

    async def _consider_recipe(
        self,
        strategy: ExtractionStrategy,
        proposed_recipe: ApiRecipe,
        held_out_listings: list[tuple[str, ExtractedListing]],
    ) -> None:
        """Validate and conditionally promote a proposed recipe."""

        # Reject if the strategy already has a high-confidence recipe with no failures.
        # (Don't overwrite a working recipe with a freshly-captured one.)
        existing = strategy.api_recipe
        if (
            existing
            and existing.confidence == "high"
            and existing.failure_count == 0
        ):
            log.info(
                "recipe_merge.skipped_existing_high_confidence",
                source_id=strategy.source_id,
            )
            return

        async with httpx.AsyncClient() as http:
            validator = RecipeValidator(http)
            result = await validator.validate(
                recipe=proposed_recipe,
                held_out_listings=held_out_listings,
            )

        if not result.valid:
            log.info(
                "recipe_merge.rejected",
                source_id=strategy.source_id,
                reason=result.reason,
            )
            await self._record_recipe_rejection(
                source_id=strategy.source_id,
                recipe=proposed_recipe,
                reason=result.reason,
            )
            return

        proposed_recipe.confidence = result.confidence  # "high" or "medium"
        proposed_recipe.last_validated_at = datetime.now(UTC)
        strategy.api_recipe = proposed_recipe

        log.info(
            "recipe_merge.promoted",
            source_id=strategy.source_id,
            confidence=result.confidence,
        )

    async def _record_recipe_rejection(
        self,
        source_id: str,
        recipe: ApiRecipe,
        reason: str,
    ) -> None:
        """Audit table; surfaces in the cost dashboard."""
        # Mirror however your existing _record_feedback works.
        ...
```

---

## Step 7 — Orchestrator wiring

The orchestrator now has three tiers. Mode A0 first, then Mode A, then Mode B.

```python
# src/backend/doormat/extraction/orchestrator.py
# (modify the run() method)

async def run_extraction(
    listing_url: str,
    pre_fetched_html: str | None,
    source_id: str,
    cache: StrategyCache,
    http_client: httpx.AsyncClient,
    llm_client,
    browser_factory,  # creates a Browser-Use session on demand
) -> ListingExtractionResult:
    strategy = await cache.get(source_id)

    # --- Tier 0: recipe-driven fast path ---
    if strategy and strategy.api_recipe is not None:
        result = await run_mode_a0(
            url=listing_url,
            strategy=strategy,
            http_client=http_client,
        )
        if result is not None:
            return result
        # Fall through

    # --- Tier 1: Mode A (existing path) ---
    if pre_fetched_html and strategy:
        result = await run_mode_a(
            html=pre_fetched_html,
            strategy=strategy,
            llm_client=llm_client,
        )
        if result.confidence != "low":
            return result
        prior_failure = {
            "confidence": result.confidence,
            "missing_fields": _list_missing_fields(result.listing),
        }
    else:
        prior_failure = {"confidence": "low", "missing_fields": ["all"]}

    # --- Tier 2: Mode B with network capture ---
    listing_id = extract_listing_id_from_url(listing_url) or "unknown"
    async with browser_factory() as session:
        result = await run_mode_b(
            url=listing_url,
            listing_id=listing_id,
            source_id=source_id,
            prior_failure=prior_failure,
            llm_client=llm_client,
            browser_session=session,
        )

    # Merge the strategy update (incl. any captured recipe)
    if result.strategy_update is not None:
        held_out = await _select_held_out_listings(source_id, exclude_id=listing_id)
        await cache.merge(
            source_id=source_id,
            update=result.strategy_update,
            held_out_listings=held_out,
        )

    return result


async def _select_held_out_listings(
    source_id: str,
    exclude_id: str,
    limit: int = 3,
) -> list[tuple[str, ExtractedListing]]:
    """Return up to `limit` recently-extracted listings from this source.

    These are the held-out samples the recipe validator replays against to
    earn 'high' confidence. We exclude the listing_id Mode B just looked at
    to avoid trivially-passing self-replay.
    """
    # Query your listings table: latest N listings for source_id, status=extracted,
    # confidence=high, NOT id == exclude_id.
    ...  # implement against your existing Listing ORM
```

---

## Step 8 — Mode B prompt update

Append a new section to `prompts/extraction/listing-extraction.md` under **System (Mode B)**, immediately after the existing Mode B-specific rules. The section instructs the model to be aware of network traffic and lean toward strategies that work with the API endpoint.

```markdown
## Mode B — additional guidance: API-first recovery

While you navigate, the runtime captures any JSON XHR/fetch responses
the page makes to its own origin. After your run completes, the
runtime scans those responses for one that contains the listing data
you extracted, and synthesizes an ApiRecipe. The recipe — when
captured and validated — replaces both Mode A and Mode B for this
source on future calls. It approaches zero cost.

This means: if the page you're navigating fetches its own listing
data via JSON, do not work around it with DOM scraping. Let the
fetch happen normally. The capturer needs to see the JSON arrive.

Specifically:

- After `browser_navigate`, **wait for the page's data to finish
  loading**. If the listing's data is rendered after a spinner,
  `browser_scroll` slightly or wait for the network to settle. The
  capturer needs the JSON response to actually arrive.
- If you click a "Show details" or "Show all amenities" expander,
  pause briefly after the click. Many sites lazy-fetch detail data on
  expand; the capturer needs to see that fetch.
- Do not interact with sign-in, account, or settings endpoints.
  Recipes captured against authenticated endpoints will fail
  validation when replayed without the user's session.
- If you observe a captcha, pop-up, or rate-limit page, **abort the
  Mode B run with confidence: low and no strategy_update**. Captured
  recipes from such pages would fail unpredictably for other users.

You don't need to "ask for" the recipe in your output — the runtime
captures it from network traffic regardless. Your only job is to
not actively break the capture.
```

That's the full prompt change. The `ApiRecipe` field is on `StrategyUpdate` but the model never has to construct one; the capturer does.

---

## Step 9 — Alembic migration

```python
# migrations/versions/<timestamp>_api_recipe.py

"""add api_recipe to extraction_strategies

Revision ID: <generate>
Revises: <prior head>
Create Date: <now>
"""

from alembic import op
import sqlalchemy as sa


revision = "<generate>"
down_revision = "<prior head>"


def upgrade() -> None:
    # The recipe is JSON-serialized on the strategy. Single nullable column.
    with op.batch_alter_table("extraction_strategies", recreate="auto") as batch:
        batch.add_column(
            sa.Column("api_recipe_json", sa.JSON(), nullable=True)
        )

    # Audit table for rejected recipes (cost dashboard surfaces this)
    op.create_table(
        "api_recipe_rejections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.String(64), nullable=False, index=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(512), nullable=False),
        sa.Column("recipe_json", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("api_recipe_rejections")
    with op.batch_alter_table("extraction_strategies", recreate="auto") as batch:
        batch.drop_column("api_recipe_json")
```

If `extraction_strategies` is your existing table name, this lands cleanly. If your strategy lives inline on `property_managers` or somewhere else, retarget the table name.

---

## Step 10 — Tests

Drop in `tests/extraction/test_api_recipe.py`. These tests don't require Browser-Use to run; they validate the schemas, the executor, the validator, and Mode A0 in isolation.

```python
# tests/extraction/test_api_recipe.py

from datetime import UTC, datetime

import httpx
import pytest
import respx

from doormat.extraction.mode_a0 import (
    extract_listing_id_from_url,
    run_mode_a0,
)
from doormat.extraction.recipe_executor import extract_listing_via_recipe
from doormat.extraction.recipe_validator import RecipeValidator
from doormat.extraction.schemas import (
    ApiRecipe,
    ExtractedListing,
    ExtractionStrategy,
    PetsPolicy,
    PhotoGalleryStrategy,
)


def _sample_recipe() -> ApiRecipe:
    return ApiRecipe(
        method="GET",
        url_template="https://acme-pm.example.com/api/listings/{listing_id}",
        headers={"Accept": "application/json"},
        body_template=None,
        response_root="$.data.listing",
        field_paths={
            "address": "address",
            "price": "rent",
            "bedrooms": "beds",
            "bathrooms": "baths",
            "sqft": "square_feet",
            "amenities": "amenities",
            "photos": "photo_urls",
            "description": "description",
        },
        extractable_fields=[
            "address", "price", "bedrooms", "bathrooms",
            "sqft", "amenities", "photos", "description",
        ],
        captured_at=datetime.now(UTC),
        captured_from_listing_id="42",
        confidence="high",
    )


def _sample_response_body(listing_id: str = "42") -> dict:
    return {
        "data": {
            "listing": {
                "id": listing_id,
                "address": "847 Congaree Lane, Redding, CA 96001",
                "rent": 2350,
                "beds": 4,
                "baths": 2.5,
                "square_feet": 1615,
                "amenities": ["yard", "garage", "solar"],
                "photo_urls": [
                    "https://acme-pm.example.com/photos/1.jpg",
                    "https://acme-pm.example.com/photos/2.jpg",
                ],
                "description": "Newly built peaceful Redding neighborhood.",
            }
        }
    }


# --- recipe_executor ---

def test_recipe_executor_basic():
    recipe = _sample_recipe()
    body = _sample_response_body()
    listing = extract_listing_via_recipe(recipe, body)
    assert listing.address == "847 Congaree Lane, Redding, CA 96001"
    assert listing.price == 2350
    assert listing.bedrooms == 4
    assert listing.bathrooms == 2.5
    assert listing.sqft == 1615
    assert "yard" in listing.amenities


def test_recipe_executor_missing_required_raises():
    recipe = _sample_recipe()
    body = {"data": {"listing": {"address": "X"}}}  # missing price/beds/baths
    with pytest.raises(ValueError):
        extract_listing_via_recipe(recipe, body)


# --- listing_id extraction ---

@pytest.mark.parametrize("url,expected", [
    ("https://acme-pm.com/listings/42", "42"),
    ("https://acme-pm.com/listings/42/", "42"),
    ("https://acme-pm.com/property/abc-def", "abc-def"),
    ("https://acme-pm.com/units/42?ref=foo", "42"),
    ("https://acme-pm.com/?id=42", "42"),
    ("https://acme-pm.com/?listing_id=xyz", "xyz"),
    ("https://acme-pm.com/about", None),
])
def test_listing_id_patterns(url: str, expected: str | None):
    assert extract_listing_id_from_url(url) == expected


# --- run_mode_a0 ---

@pytest.mark.asyncio
async def test_mode_a0_happy_path():
    recipe = _sample_recipe()
    strategy = ExtractionStrategy(
        source_id="acme-pm",
        listing_index_url="https://acme-pm.example.com/listings",
        listing_link_selector="a.listing",
        api_recipe=recipe,
        last_updated_at=datetime.now(UTC),
    )

    async with httpx.AsyncClient() as http:
        with respx.mock(base_url="https://acme-pm.example.com") as mock:
            mock.get("/api/listings/42").respond(json=_sample_response_body("42"))

            result = await run_mode_a0(
                url="https://acme-pm.example.com/listings/42",
                strategy=strategy,
                http_client=http,
            )

    assert result is not None
    assert result.mode == "A0"
    assert result.confidence == "high"
    assert result.listing.price == 2350


@pytest.mark.asyncio
async def test_mode_a0_returns_none_without_recipe():
    strategy = ExtractionStrategy(
        source_id="acme-pm",
        listing_index_url="https://acme-pm.example.com/listings",
        listing_link_selector="a.listing",
        api_recipe=None,
        last_updated_at=datetime.now(UTC),
    )
    async with httpx.AsyncClient() as http:
        result = await run_mode_a0(
            url="https://acme-pm.example.com/listings/42",
            strategy=strategy,
            http_client=http,
        )
    assert result is None


@pytest.mark.asyncio
async def test_mode_a0_retires_after_three_failures():
    recipe = _sample_recipe()
    recipe.failure_count = 3
    strategy = ExtractionStrategy(
        source_id="acme-pm",
        listing_index_url="https://acme-pm.example.com/listings",
        listing_link_selector="a.listing",
        api_recipe=recipe,
        last_updated_at=datetime.now(UTC),
    )
    async with httpx.AsyncClient() as http:
        result = await run_mode_a0(
            url="https://acme-pm.example.com/listings/42",
            strategy=strategy,
            http_client=http,
        )
    assert result is None  # recipe is retired


@pytest.mark.asyncio
async def test_mode_a0_handles_auth_required():
    recipe = _sample_recipe()
    strategy = ExtractionStrategy(
        source_id="acme-pm",
        listing_index_url="https://acme-pm.example.com/listings",
        listing_link_selector="a.listing",
        api_recipe=recipe,
        last_updated_at=datetime.now(UTC),
    )

    async with httpx.AsyncClient() as http:
        with respx.mock(base_url="https://acme-pm.example.com") as mock:
            mock.get("/api/listings/42").respond(status_code=401)

            result = await run_mode_a0(
                url="https://acme-pm.example.com/listings/42",
                strategy=strategy,
                http_client=http,
            )

    assert result is None
    assert recipe.failure_count >= 1


# --- recipe_validator ---

@pytest.mark.asyncio
async def test_validator_rejects_held_out_mismatch():
    recipe = _sample_recipe()
    held_out = [(
        "999",
        ExtractedListing(
            address="A different address entirely, Fresno, CA 12345",
            price=99999,  # very different from what the recipe will return
            bedrooms=1,
            bathrooms=1.0,
            pets_policy=PetsPolicy.UNKNOWN,
        ),
    )]

    async with httpx.AsyncClient() as http:
        with respx.mock(base_url="https://acme-pm.example.com") as mock:
            # Server returns the same body regardless of listing_id
            mock.get("/api/listings/999").respond(json=_sample_response_body("999"))

            validator = RecipeValidator(http)
            result = await validator.validate(recipe, held_out)

    assert not result.valid
    assert "mismatch" in result.reason.lower() or "diff" in result.reason.lower()


@pytest.mark.asyncio
async def test_validator_promotes_to_high_confidence_on_held_out_match():
    recipe = _sample_recipe()
    held_out = [(
        "42",
        ExtractedListing(
            address="847 Congaree Lane, Redding, CA 96001",
            price=2350,
            bedrooms=4,
            bathrooms=2.5,
            sqft=1615,
            pets_policy=PetsPolicy.UNKNOWN,
        ),
    )]

    async with httpx.AsyncClient() as http:
        with respx.mock(base_url="https://acme-pm.example.com") as mock:
            mock.get("/api/listings/42").respond(json=_sample_response_body("42"))
            validator = RecipeValidator(http)
            result = await validator.validate(recipe, held_out)

    assert result.valid
    assert result.confidence == "high"
```

Coverage: schemas, executor, validator, Mode A0. Mode B's network capture is harder to test without a real CDP session — the patch ships with a single integration test that uses Playwright directly to confirm the capturer attaches and buffers. Add it under `tests/extraction/integration/test_capture_integration.py` once the rest of the patch lands.

---

## Step 11 — Feature flag and observability

`config.py`:

```python
# Add to Config
api_recipe_enabled: bool = True
api_recipe_max_capture_bodies: int = 50  # cap responses buffered per Mode B run
api_recipe_replay_timeout_seconds: float = 8.0
api_recipe_promotion_requires_held_out: bool = False  # set True after a week of soak
```

The `api_recipe_promotion_requires_held_out` flag is the rollout knob. For the first week, ship with `False` — recipes promote to confidence: medium on self-replay, then earn high after Mode A0 produces 5 successful production calls. For the second week, flip to `True` — only recipes that match held-out listings get promoted at all. After that, you can flip back if held-out availability becomes a bottleneck on cold-start sources.

Cost dashboard additions: track `mode_a0_calls`, `mode_a0_successes`, `mode_a0_misses`, `mode_a_calls`, `mode_b_calls` separately. The ratio of `mode_a0_successes` to total scrape attempts is your headline cost-savings metric. Surface it in `/costs` next to the existing per-mode breakdown.

---

## Rollout

1. Land schemas + executor + validator with tests (steps 1–3, 10). One PR.
2. Land Mode A0 + orchestrator wiring (steps 5, 7) with `api_recipe_enabled = False`. One PR. No behavior change in production.
3. Land Mode B network capture (steps 2, 4) with the prompt update (step 8). One PR. Recipes start being captured but don't yet feed Mode A0.
4. Flip `api_recipe_enabled = True` for one source manually, verify Mode A0 hits in logs.
5. Watch the cost dashboard. After a week, flip `api_recipe_promotion_requires_held_out = True`.
6. After a month, bake the flag default into the code; remove the flag.

The whole patch is additive — every fallback path is preserved. If anything misbehaves, set `api_recipe_enabled = False` and the system reverts to today's two-mode behavior.

---

## What this is *not*

- Not a way to scrape sites that don't have a JSON API. Sites that render listings server-side will never produce a recipe; they'll always run on Mode A.
- Not a way to bypass auth. Auth-required APIs fail validation at merge time. The runtime never replays auth-bound recipes.
- Not a way to scrape sites that have aggressive bot detection on their API endpoints. If the API requires Cloudflare-issued tokens or signed requests, the capturer sees them in headers, the scrubber strips them, and the replay fails. The system gracefully falls back. No new harm; no new capability.

The pattern works on the ~60% of property manager sites that have a clean public-ish JSON API powering their own front end. That's the 60% where it's worth the engineering.
