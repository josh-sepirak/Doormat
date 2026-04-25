---
name: listing-extraction
version: 2.0.0
schema: doormat.schemas.ListingExtractionResult
recommended_model_mode_a: claude-haiku-4-5
recommended_model_mode_b: claude-sonnet-4-7
fallback_models: [openai/gpt-5-mini, openai/gpt-5, deepseek/deepseek-v3, google/gemini-2.5-flash]
prompt_cache: true
expected_input_tokens_mode_a: 1500
expected_output_tokens_mode_a: 250
expected_input_tokens_mode_b: 4000
expected_output_tokens_mode_b: 600
estimated_cost_usd_mode_a: 0.0008
estimated_cost_usd_mode_b: 0.025
tools_required_mode_b: [browser_navigate, browser_get_dom, browser_extract_text, browser_click, browser_scroll, browser_screenshot]
---

# Listing extraction — agentic-first

Extracts a structured `Listing` from a single rental listing page. This
is the highest-volume LLM call in doormat. Two modes:

- **Mode A (deterministic-first)** is the hot path. ~99% of calls. Takes
  pre-fetched HTML (already filtered to the listing fragment by the
  source's cached extraction strategy) and emits a typed Listing.
  Runs on Haiku 4.5. ~$0.0008/listing.
- **Mode B (agentic recovery)** kicks in when Mode A returns
  `confidence: low` or fails schema validation, OR when the runtime
  detects that a source's cached extraction strategy has drifted
  (parse failure rate > 20% over the last 50 listings). Mode B drives
  Browser-Use to navigate the listing page like a human, extracts what
  Mode A missed, AND emits a `strategy_update` patch that updates the
  source's cached extraction strategy so subsequent calls in Mode A
  succeed. Runs on Sonnet 4.7. ~$0.025/listing.

The two-mode design is the dominant cost optimization in doormat. A naive
all-agentic approach would cost ~$8/day for typical use; this approach
costs ~$0.30/day because Mode B fires for ~1% of listings. The
strategy-update feedback loop means Mode B's cost is amortized across
all future Mode A calls for that source.

## When to use which mode

The runtime selects the mode automatically. The agent itself does not
choose. The selection logic, in pseudocode:

```python
async def extract_listing(html, url, source_id) -> Listing:
    strategy = await strategy_cache.get(source_id)

    if strategy and strategy.health > 0.8:
        # Mode A: trust the cached strategy
        result = await run_mode_a(html, strategy)
        if result.confidence != "low":
            return result.listing

    # Mode A failed or strategy health is poor — escalate to Mode B
    result = await run_mode_b(url, source_id, prior_failure=result)
    if result.strategy_update:
        await strategy_cache.merge(source_id, result.strategy_update)
    return result.listing
```

The reason the same prompt file handles both modes is that the schema
is the same. The system prompt branches on whether tools are available;
the user template branches on whether HTML or a URL is provided.

---

## System

You extract structured rental listing data from rental websites.

You operate in one of two modes determined by your runtime:

**Mode A** — you receive pre-fetched HTML for a single listing. Extract
the structured fields directly from the HTML. Do not call tools; the
deterministic mode does not provide them. If you cannot extract a field
with confidence, mark it as unknown and set the overall `confidence`
to `low`. The runtime will retry in Mode B.

**Mode B** — you receive a URL and the prior Mode A failure context.
You have browser tools available. Navigate the page, extract what you
need, and crucially, observe *what made Mode A fail* so you can emit a
`strategy_update` that prevents the same failure on the next listing
from this source. Common Mode A failures and their Mode B fixes:

| Mode A failure | Mode B response |
|---|---|
| Address selector returned generic site footer | Find the real address element; emit selector update |
| Rent extracted from marketing banner instead of price label | Identify the labeled rent field; update selector |
| Bedrooms missing because they're in a JS-loaded panel | Click the "Details" tab if present; update strategy |
| Photos missing because they're lazy-loaded | Scroll the gallery; update strategy with photo container selector |
| Pet policy missing because it's behind "Show all amenities" | Click expansion control; update strategy |

When you emit a `strategy_update`, only include selectors and steps
you have *verified work* on the page in front of you. A strategy
patch that's wrong is worse than no patch — it would cause cascading
Mode A failures across every subsequent listing from the source.

**Common rules across both modes:**

The HTML or page is the source of truth. If a field cannot be
determined with confidence, mark it as unknown rather than guessing.
A missing `sqft` is normal and acceptable. A guessed `sqft` is a bug.

When sources disagree — for example, a price in the page title
disagrees with a price near the "Apply Now" button — prefer the
labeled, structured value (`<dt>RENT</dt><dd>$2,350</dd>`,
`data-test="price"`, `<meta property="rental:price">`) over
unlabeled prose. Marketing banners ("$1000 OFF FIRST MONTH!") are
the lowest-confidence signal and never the canonical rent.

The `pets_policy` field has four valid values:

- `allowed_with_small_dog` — listing explicitly mentions small dogs OK,
  pets allowed, dogs welcome, or pets considered (with no overriding
  no-dog signal)
- `cats_only` — explicit cats-only or no-dogs-but-cats language
- `none_allowed` — explicit "no pets"
- `unknown` — the listing does not address pet policy

Negative signals always override positive ones. "Pets considered"
plus "no large dogs" → `allowed_with_small_dog`. "Small dogs allowed"
plus "no dogs" (the real copy-paste-template pattern) →
`none_allowed`. When in doubt, prefer the more restrictive
interpretation; the user can verify with the landlord.

The `reasoning` field in your output is a scratchpad. Use it when
fields are ambiguous. Skip it when the listing is unambiguous —
empty reasoning is preferred to padded reasoning.

In Mode B, your `reasoning` should also briefly describe what you
tried and what worked. This is the most valuable single artifact for
debugging extraction quality. Keep it under 150 words.

---

## User template — Mode A

Mode: A (deterministic)

Source: `{{source}}`
Source URL: `{{url}}`
Cached extraction strategy version: `{{strategy_version}}`

<html>
{{html}}
</html>

Extract the listing.

---

## User template — Mode B

Mode: B (agentic recovery)

Source: `{{source}}`
Source URL: `{{url}}`

Prior Mode A failure context:

```json
{{prior_failure_json}}
```

The Mode A extraction returned `confidence: low` or failed validation.
Navigate the listing page using your browser tools. Extract the
listing. Then emit a `strategy_update` patch describing the selectors
or interaction steps that would have allowed Mode A to succeed.

Available tools:

- `browser_navigate(url)` — load a URL into the active page.
- `browser_get_dom(selector?)` — return cleaned DOM as text.
  When called with no selector, returns the full page text under
  ~8k tokens (further trimming if needed). With a selector, returns
  just that subtree.
- `browser_extract_text(selector)` — fast targeted extraction.
- `browser_click(selector)` — click an element. Use for "Show more
  amenities", "Details" tabs, photo gallery navigation, cookie
  banners. Never click external links or "Apply Now" buttons.
- `browser_scroll(direction, amount?)` — scroll up/down. Useful for
  lazy-loaded photos and infinite-scroll details panels.
- `browser_screenshot(region?)` — only use when DOM extraction is
  ambiguous and visual layout matters (e.g., the listing has the
  rent rendered as text inside an image — rare). Each screenshot
  costs ~1500 input tokens and ~0.8s of latency. Budget: 2 per
  call. If you need more, the listing is probably a problem
  source and should be skipped.

Constraints:

- You have a budget of 8 tool calls per extraction. Use them.
- Do not navigate away from the listing's domain.
- Do not interact with login forms, payment forms, or "Apply"
  buttons.
- Do not click ads. If an ad blocks content, scroll past it.
- If the page requires login or returns a 4xx/5xx, return a Listing
  with `confidence: low` and an empty `strategy_update`. The runtime
  will deactivate the source.

---

## Output schema

Defined in `src/doormat/schemas/listing.py`:

```python
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl


class PetsPolicy(str, Enum):
    ALLOWED_WITH_SMALL_DOG = "allowed_with_small_dog"
    CATS_ONLY = "cats_only"
    NONE_ALLOWED = "none_allowed"
    UNKNOWN = "unknown"


class Listing(BaseModel):
    address: str = Field(
        description="Full street address, including city, state, ZIP when available. "
                    "If unrecoverable, set to 'Unknown — see source URL'."
    )
    rent: int = Field(
        ge=200, le=50_000,
        description="Monthly rent in USD. Integer dollars only. "
                    "Prefer labeled price fields over marketing copy."
    )
    bedrooms: int = Field(ge=0, le=20)
    bathrooms: float = Field(ge=0, le=20)
    sqft: int | None = Field(
        default=None, ge=100, le=20_000,
        description="Square feet. Null if not stated. Never estimate."
    )
    pets_policy: PetsPolicy = Field(
        description="See system prompt for the four valid values and their precedence rules."
    )
    amenities: list[str] = Field(
        default_factory=list, max_length=20,
        description="Lowercase short tags. Examples: 'pool', 'rv parking', "
                    "'fenced yard', 'in-unit laundry', 'garage', 'central ac'. "
                    "Skip generic adjectives like 'modern', 'spacious', 'beautiful'."
    )
    photos: list[HttpUrl] = Field(
        default_factory=list, max_length=20,
        description="Photo URLs from the listing's image gallery. "
                    "Skip thumbnails of agent profiles or PM logos."
    )
    description: str = Field(
        max_length=2000,
        description="The listing's narrative description, cleaned of HTML and "
                    "trimmed to 2000 chars. Preserve paragraph breaks where present."
    )


class StrategyUpdate(BaseModel):
    """A patch to a source's cached extraction strategy.

    Only emitted in Mode B. Contains selectors or interaction steps that
    are verified to work on the current page. The runtime merges this
    into the source's strategy after validating it on a held-out sample.
    """
    field_selectors: dict[str, str] = Field(
        default_factory=dict,
        description="CSS or XPath selectors per field name. "
                    "Example: {'rent': 'dd.price', 'bedrooms': '.beds-baths .beds'}"
    )
    pre_extraction_actions: list[str] = Field(
        default_factory=list,
        description="Click/scroll actions needed before extraction. "
                    "Example: ['click .show-all-amenities', 'scroll down 800']"
    )
    notes: str | None = Field(
        default=None, max_length=500,
        description="Free-form notes about the source's quirks, for the next "
                    "engineer (or the agent) reviewing this strategy."
    )


class ListingExtractionResult(BaseModel):
    """The unified output schema for both Mode A and Mode B."""

    reasoning: str | None = Field(
        default=None, max_length=600,
        description="Scratchpad for ambiguous fields. In Mode B, also briefly "
                    "describe what you tried with the browser tools and what worked. "
                    "Skip when listing is unambiguous."
    )
    listing: Listing
    confidence: Literal["high", "medium", "low"] = Field(
        description="Your confidence that the listing matches what a human would "
                    "extract. low triggers Mode B retry (in Mode A) or human review "
                    "(in Mode B). Be honest."
    )
    strategy_update: StrategyUpdate | None = Field(
        default=None,
        description="Only emit in Mode B. Set to None in Mode A. "
                    "If Mode B did not learn anything new, also set to None."
    )
    mode: Literal["A", "B"] = Field(
        description="The mode you ran in. Used by the runtime for cost tracking."
    )
```

---

## Examples

### Example 1 — Mode A, clean AppFolio listing

<input>
mode: A
source: hignell
strategy_version: 3
html: <h2>$1000 MOVE IN SPECIAL OFF FIRST MONTHS RENT.</h2>
      <dl>
        <dt>RENT</dt><dd>$2,350</dd>
        <dt>Square Feet</dt><dd>1,615</dd>
        <dt>Bed / Bath</dt><dd>4 bd / 2.5 ba</dd>
      </dl>
      <div>847 Congaree Lane, Redding, CA 96001</div>
      <p>This 4 bedroom, 2.5 bath home is located in a newly built peaceful
      Redding neighborhood. Solar panels, newly landscaped backyard.</p>
      <div>Amenities: gated community, yard, security system, garbage disposal,
      solar panel, garage, playground</div>
      <div>Pet Policy: Cats allowed, Small dogs allowed</div>
</input>

<o>
{
  "listing": {
    "address": "847 Congaree Lane, Redding, CA 96001",
    "rent": 2350,
    "bedrooms": 4,
    "bathrooms": 2.5,
    "sqft": 1615,
    "pets_policy": "allowed_with_small_dog",
    "amenities": ["gated community", "yard", "security system", "solar", "garage", "playground"],
    "photos": [],
    "description": "This 4 bedroom, 2.5 bath home is located in a newly built peaceful Redding neighborhood. Solar panels, newly landscaped backyard."
  },
  "confidence": "high",
  "strategy_update": null,
  "mode": "A"
}
</o>

The marketing banner "$1000 MOVE IN SPECIAL" is correctly ignored;
the labeled `<dd>$2,350</dd>` is the rent. The reasoning field is
omitted because nothing is ambiguous.

### Example 2 — Mode A failure, then Mode B recovery

<input>
mode: A
source: small-pm
strategy_version: 1
html: <article class="listing">
        <h3>Charming bungalow</h3>
        <p>$1,800/mo. <a href="#details">Click for details</a></p>
      </article>
</input>

Mode A response:

<o>
{
  "reasoning": "The HTML fragment passed in does not contain bedrooms, bathrooms, or address — only a title, rent, and a 'click for details' link. The strategy is incomplete; it must not be expanding the details panel before extraction.",
  "listing": {
    "address": "Unknown — see source URL",
    "rent": 1800,
    "bedrooms": 0,
    "bathrooms": 0,
    "sqft": null,
    "pets_policy": "unknown",
    "amenities": [],
    "photos": [],
    "description": "Charming bungalow"
  },
  "confidence": "low",
  "strategy_update": null,
  "mode": "A"
}
</o>

Runtime sees `confidence: low`, escalates to Mode B with the URL.

<input>
mode: B
source: small-pm
url: https://small-pm.example.com/listings/42
prior_failure_json: { "confidence": "low", "missing_fields": ["address", "bedrooms", "bathrooms"] }
</input>

Mode B response (after tool calls):

```
[tool call] browser_navigate("https://small-pm.example.com/listings/42")
[tool call] browser_get_dom() -> "...Charming bungalow $1,800/mo. Click for details..."
[tool call] browser_click("a[href='#details']")
[tool call] browser_get_dom() -> "...3 bd / 2 ba ... 1,100 sqft ... 12 Maple St, Asheville, NC 28801 ... Pets allowed with deposit ..."
```

<o>
{
  "reasoning": "Mode A failed because the listing's details panel is hidden behind a 'Click for details' anchor. Clicked it, the panel expanded, all fields became extractable. Strategy update: pre_extraction_actions should include the click on a[href='#details'].",
  "listing": {
    "address": "12 Maple St, Asheville, NC 28801",
    "rent": 1800,
    "bedrooms": 3,
    "bathrooms": 2.0,
    "sqft": 1100,
    "pets_policy": "allowed_with_small_dog",
    "amenities": [],
    "photos": [],
    "description": "Charming bungalow"
  },
  "confidence": "high",
  "strategy_update": {
    "field_selectors": {
      "address": ".details-panel .address",
      "bedrooms": ".details-panel .bd-count"
    },
    "pre_extraction_actions": [
      "click a[href='#details']"
    ],
    "notes": "small-pm.example.com hides bed/bath/address behind a click-to-expand details panel. Without expanding, Mode A only sees title and rent."
  },
  "mode": "B"
}
</o>

The strategy update is the most valuable artifact here. The next 100
listings from this source will succeed in Mode A because the runtime
will execute the click action before extraction.

### Example 3 — Mode B, page requires interaction beyond what's allowed

<input>
mode: B
source: gated-portal
url: https://gated.example.com/listings/77
prior_failure_json: { "confidence": "low", "missing_fields": ["everything"] }
</input>

```
[tool call] browser_navigate("https://gated.example.com/listings/77")
[tool call] browser_get_dom() -> "...Sign in to view listings..."
```

<o>
{
  "reasoning": "Page requires sign-in to view listings. Cannot extract; cannot work around per the constraint that prohibits login form interaction. Returning low confidence with no strategy update — the source should be deactivated.",
  "listing": {
    "address": "Unknown — see source URL",
    "rent": 0,
    "bedrooms": 0,
    "bathrooms": 0,
    "sqft": null,
    "pets_policy": "unknown",
    "amenities": [],
    "photos": [],
    "description": ""
  },
  "confidence": "low",
  "strategy_update": null,
  "mode": "B"
}
</o>

The runtime will deactivate `gated-portal` after seeing two
consecutive low-confidence Mode B results with no strategy update.

---

## Eval queries

```yaml
# tests/prompts/listing-extraction.yaml

# Mode A evals — fast, cheap, run on every PR
- name: mode_a_clean_appfolio
  mode: A
  fixture: tests/fixtures/html/hignell/847-congaree.html
  expect:
    confidence: high
    listing.rent: 2350
    listing.bedrooms: 4
    listing.bathrooms: 2.5
    listing.pets_policy: allowed_with_small_dog
    strategy_update: null

- name: mode_a_marketing_banner_disambiguation
  mode: A
  fixture: tests/fixtures/html/marketing-banner-with-discount.html
  expect:
    listing.rent: 2595         # not the $1000-off discount price
    confidence: high

- name: mode_a_pet_policy_negative_overrides_positive
  mode: A
  fixture: tests/fixtures/html/contradictory-pets.html
  expect:
    listing.pets_policy: none_allowed

- name: mode_a_low_confidence_on_partial_html
  mode: A
  fixture: tests/fixtures/html/details-hidden.html
  expect:
    confidence: low
    # Runtime should escalate to Mode B

# Mode B evals — slower, more expensive, run nightly
- name: mode_b_recovery_with_strategy_update
  mode: B
  fixture_url: file://tests/fixtures/sites/click-for-details/listing-42.html
  expect:
    confidence: high
    listing.address_contains: ["Maple", "28801"]
    strategy_update.pre_extraction_actions: not_empty

- name: mode_b_login_wall_returns_no_update
  mode: B
  fixture_url: file://tests/fixtures/sites/gated/listing-77.html
  expect:
    confidence: low
    strategy_update: null     # don't lie about learning something

- name: mode_b_lazy_loaded_photos
  mode: B
  fixture_url: file://tests/fixtures/sites/lazy-photos/listing-3.html
  expect:
    listing.photos.length_at_least: 5
    strategy_update.pre_extraction_actions_includes: ["scroll"]
```

The fixture system serves Mode B fixtures as local files via Playwright,
so Mode B evals run deterministically against synthetic sites that
exercise the relevant patterns. See
`tests/fixtures/sites/README.md` for how to add a new Mode B fixture.

---

## Notes

### Cost characteristics

Per-call costs at typical token counts and current (April 2026)
pricing:

| Mode | Model | Input | Output | Cost (no cache) | Cost (cache hit) |
|---|---|---|---|---|---|
| A | Haiku 4.5 | 1500 | 250 | $0.0021 | $0.0008 |
| A | GPT-5-mini | 1500 | 250 | $0.0017 | $0.0007 |
| A | DeepSeek V3 (free tier) | 1500 | 250 | $0 | $0 |
| B | Sonnet 4.7 | 4000 | 600 | $0.027 | $0.025 |
| B | GPT-5 | 4000 | 600 | $0.022 | $0.020 |

Mode B fires for ~1% of new listings in steady state once the
strategy cache warms up. For 300 new listings/day, that's ~3 Mode B
calls (~$0.075/day) and ~297 Mode A calls (~$0.24/day with cache).
Total: ~$0.32/day. After dedup-before-LLM, only *new* listings
incur cost — typical steady-state cost is ~$0.05/day.

### Why two modes instead of one

A single agentic-everything design (always Mode B) costs ~30× more.
A single deterministic-everything design (always Mode A) cannot
recover when sources change their HTML. The two-mode design buys
deterministic-Mode-A's cost profile with agentic-Mode-B's robustness,
at the cost of slightly more system complexity. The strategy-update
feedback loop means the system gets *cheaper* over time as Mode B
teaches Mode A how to handle each source's quirks.

### Strategy validation gate

Before merging a `strategy_update` from Mode B into the source's
cached strategy, the runtime validates it against the most recent 5
listings from that source. If the patched strategy doesn't improve
extraction confidence on at least 3 of them, the patch is logged
and discarded. This prevents one weird listing from poisoning the
strategy for an entire source. See `src/doormat/strategy/validator.py`.

### Browser-Use integration

Mode B uses Browser-Use 1.x with the following configuration:

```python
from browser_use import Agent, Browser, ChatAnthropic

browser = Browser(
    headless=True,
    use_vision=False,                  # Default to DOM-only for cost
    page_extraction_llm=ChatAnthropic(model="claude-haiku-4-5"),
    max_history_items=8,               # Compact history aggressively
)
agent = Agent(
    task=mode_b_user_template,
    llm=ChatAnthropic(model="claude-sonnet-4-7"),
    browser=browser,
    max_actions_per_step=2,
    max_failures=2,
)
```

`use_vision=False` is the most important flag. Per Browser-Use's own
documentation, vision adds ~0.8s latency per step and substantial
token cost. The agent uses screenshots only when explicitly called
via `browser_screenshot`, which is rare. `page_extraction_llm` is
set to Haiku separately so that the agent's main reasoning runs on
Sonnet but the deeper page-text extraction (which is the most
common operation) runs on Haiku — another cost win.

### What this prompt deliberately does not do

- It does not score listings against user preferences. That's
  `scoring/fit-score-with-explanation.md`.
- It does not download photos. The runtime fetches photo URLs
  asynchronously after extraction.
- It does not handle multi-listing pages. The discovery agent
  identifies whether a URL is a single-listing page or a results
  page; only single-listing pages reach this prompt.
- It does not de-duplicate. Hash-based dedup runs *before* this
  prompt; we never extract the same listing twice.

### Known failure modes

1. **Listings that span multiple URLs** — some PMs put one logical
   listing across a "summary" page and a "details" page reachable
   only via JS popup. Mode B handles this when the popup is in the
   same page; cross-URL listings are flagged for human review.
2. **Listings rendered entirely in JS-injected iframes** — rare,
   but Mode B currently fails on these silently. Tracked in `#208`.
3. **Multi-unit buildings with shared listing pages** — same address,
   different units, different rents. Mode A collapses to the lowest
   rent. Mode B flags via `confidence: medium` and suggests adding
   a `multi_unit` field in v0.3.

### Versioning

- **2.0.0** — added Mode B (agentic recovery) with strategy_update.
  Schema changed: response is now `ListingExtractionResult` wrapping
  a `Listing` rather than a bare `Listing`. Migration: callers must
  unwrap `result.listing` to get the legacy shape.
- **1.2.0** — added `reasoning` field as structured CoT.
- **1.1.0** — added `confidence` field.
- **1.0.0** — initial release.
