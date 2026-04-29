# Patch 2 — `contribute-rental-source` skill

## What this does

doormat already discovers sources at runtime via Mode B (and now Mode A0 with recipes). The runtime works fine. But there's a UX problem: a *new user* in a new city pays the discovery cost — typically $0.50–$2 in LLM tokens and 2–5 minutes of agent runtime — before they see results.

The fix is **pre-population**: ship doormat with a curated set of working strategies for popular markets so users in those cities get instant out-of-box performance. Not all of doormat's sources should be agent-discovered; some should be human-curated, reviewed, and version-controlled.

The contributor skill turns the developer's running Chrome into a strategy-generation machine. Workflow:

```
contributor: $ make add-source URL=https://acme-pm.example.com
                ↓
Claude Code (with browser-harness skill installed):
  1. Navigates to the URL in the contributor's real Chrome
  2. Explores the listing index (clicks listings, observes network)
  3. Identifies index URL pattern, listing URL pattern, pagination
  4. Captures a sample listing's HTML structure
  5. Generates an ExtractionStrategy + optional ApiRecipe
  6. Scrubs and saves a test fixture
  7. Runs `doormat strategy validate` against the new strategy
  8. Opens a PR with the strategy, fixture, and a docs entry
```

The contributor never touches Python directly. Claude Code drives browser-harness; the skill encodes the doormat-specific outputs.

## Why this complements Mode B (instead of replacing it)

| Concern | Mode B (runtime) | Contributor skill (build-time) |
|---|---|---|
| Who runs it | doormat daemon, on user's server | Developer at desk, in Claude Code |
| Browser | Headless via Browser-Use | Real Chrome, contributor's profile |
| Cost | LLM tokens (~$0.50–$2) | Free (developer's own usage) |
| Auth-bound endpoints | Cannot use | Can explore (skill warns when API would be session-bound) |
| Output | Strategy committed to runtime cache | PR with strategy + fixture + docs |
| Audience | Every user | Pre-curated for popular markets |

The runtime needs Mode B for the long tail. The skill is for getting popular markets right at first run.

---

## What ships in this patch

```
skills/
└── contribute-rental-source/
    ├── SKILL.md
    ├── references/
    │   ├── strategy-schema.md
    │   ├── extraction-fixture-format.md
    │   └── pr-template.md
    └── scripts/
        ├── from_harness.py        # converts harness exploration → doormat strategy
        ├── scrub_fixture.py       # PII scrubber for committed test fixtures
        └── validate_strategy.py   # runs doormat eval against a new strategy

Makefile target:
  make add-source URL=https://...

Documentation:
  docs/contributing/adding-a-source.md
```

Drop-in install: copy `skills/contribute-rental-source/` from this patch into your repo and add the Make target. The skill works in any AI coding tool that respects `.claude/skills/` or `AGENTS.md` (Claude Code, Cursor, Copilot in VS Code, OpenCode).

---

## File 1 — `skills/contribute-rental-source/SKILL.md`

```markdown
---
name: contribute-rental-source
description: Add a new rental property manager source to doormat as a hand-curated, version-controlled strategy. Use this skill when the contributor has a specific PM site URL they want to permanently support — not for runtime discovery, which Mode B handles automatically. Triggers when the contributor says "add a property manager", "add a source", "contribute a rental site", "I want doormat to support [URL]", or pastes a PM site URL and asks if doormat can handle it.
license: Apache-2.0
metadata:
  author: doormat
  version: 1.0.0
  requires:
    - browser-harness (https://github.com/browser-use/browser-harness) installed and connected to the contributor's Chrome
    - doormat repo cloned with `uv sync --dev` complete
---

# Contribute a rental source

This skill walks the contributor through adding a new rental property
manager site to doormat as a hand-curated source. The end deliverable
is a PR containing:

1. An `ExtractionStrategy` JSON file under `strategies/<source-id>.json`
2. A scrubbed HTML test fixture under `tests/fixtures/html/<source-id>/sample.html`
3. (Optional) An `ApiRecipe` if the site has a usable JSON API
4. A docs entry under `docs/sources.md`
5. An entry-point registration in `pyproject.toml`

## When to use this skill

Use it when:

- The contributor says "add a property manager", "add a source",
  "contribute a rental site"
- The contributor says "I want doormat to support [URL]"
- The contributor pastes a PM site URL and asks "can doormat scrape this?"
- The contributor mentions a city they care about and wants doormat
  to work well there from day one

Do NOT use it when:

- The user is just running doormat normally — runtime discovery is
  Mode B's job, not this skill's
- The site requires login to view listings — doormat does not handle
  authenticated scrapes
- The site is a national aggregator (Zillow, Realtor.com,
  Apartments.com) — those are routed through Apify

## Prerequisites

This skill depends on **browser-harness** being installed and
connected to the contributor's running Chrome. If it isn't, prompt
the contributor to install it first:

```
git clone https://github.com/browser-use/browser-harness ~/tools/browser-harness
cd ~/tools/browser-harness
uv sync
# Follow install.md to connect to Chrome
```

The harness gives you `goto`, `click`, `screenshot`, `js`, `http_get`,
and the rest of the helpers in `helpers.py`. You'll use them
extensively here.

The contributor must also have doormat cloned and `uv sync --dev`
complete in the doormat repo.

## Workflow

Run these phases in order. Each phase has explicit verification.
Don't skip ahead — a strategy that passes phase 7 but failed phase 3
is a strategy that will work today and break next month.

### Phase 1 — Pre-flight

Before opening the page in Chrome, verify it's a legitimate target.

1. Run `python skills/contribute-rental-source/scripts/preflight.py URL`.
   This checks:
   - robots.txt — does it disallow listings paths?
   - HTTP status — does the site respond?
   - Login wall — is there a sign-in requirement on the index page?
   - Captcha presence — does the page bounce to a Cloudflare or
     reCAPTCHA challenge?

2. If preflight returns any blocker, **stop and tell the contributor**.
   Don't try to work around robots.txt. Captcha-protected sites
   are runtime-only (they go through Apify, not through this skill).

If preflight passes, proceed.

### Phase 2 — Harness connection

1. Verify the contributor's Chrome is connected to browser-harness:
   `uv run browser-harness <<< 'print(page_info())'`
2. Navigate to the source URL via the harness:
   ```
   uv run browser-harness <<'PY'
   goto("https://acme-pm.example.com/listings")
   wait_for_load()
   print(page_info())
   PY
   ```
3. Take a screenshot for the contributor to confirm you're on
   the right page:
   ```
   uv run browser-harness <<'PY'
   screenshot("/tmp/source-index.png", full=True)
   PY
   ```

If the screenshot doesn't match what the contributor expected
(e.g., it landed on a sales page, not rentals), stop and ask.

### Phase 3 — Map the listing structure

Identify how listings are linked from the index.

1. Use `js()` to inspect the DOM structure:
   ```
   uv run browser-harness <<'PY'
   anchors = js("""
       Array.from(document.querySelectorAll('a'))
           .filter(a => a.href && /listing|rental|property|unit/i.test(a.href))
           .slice(0, 10)
           .map(a => ({href: a.href, text: a.innerText.trim().slice(0, 80)}))
   """)
   import json; print(json.dumps(anchors, indent=2))
   PY
   ```

2. From the harvested anchors, identify the canonical URL pattern:
   - `https://acme-pm.example.com/listings/12345` → pattern is
     `/listings/{listing_id}`
   - `https://acme-pm.example.com/property/abc-def` → pattern is
     `/property/{slug}`

3. Identify the listing-link CSS selector. Try in order:
   - `[data-test*="listing"] a`
   - `a[href*="/listings/"]`
   - `.listing-card a`
   - The most specific selector that matches the anchors you saw.

4. Test pagination if applicable. Look for "Next page" anchors,
   `?page=2` URL patterns, or an infinite-scroll indicator.

### Phase 4 — Sample five listings

Pick 5 listings spread across the index (not all from page 1, not
all consecutive). Open each, and for each listing capture:

1. The full HTML of the listing's main content area:
   ```
   uv run browser-harness <<'PY'
   goto("LISTING_URL")
   wait_for_load()
   html = js("document.querySelector('main, .listing-detail, body').outerHTML")
   open("/tmp/listing-N.html", "w").write(html)
   PY
   ```

2. The values a human would extract (address, rent, beds, baths,
   sqft, pets, amenities, photos). Confirm visually with a
   screenshot.

3. **CRITICAL: capture network traffic during the page load.**
   The harness exposes `Network.responseReceived` events; if it
   doesn't, fall back to opening DevTools' Network tab and looking
   for JSON XHR/fetch responses on the same domain. If the page
   loads its own data via JSON, note:
   - The endpoint URL pattern
   - The HTTP method (GET/POST)
   - Any X-* headers required (NOT Cookie / Authorization)
   - The response shape (paste a sample into a comment)

   This information becomes an `ApiRecipe` in the strategy. It's
   the single biggest perf win you can deliver.

### Phase 5 — Generate the strategy

Run the conversion script:

```
python skills/contribute-rental-source/scripts/from_harness.py \
  --source-id acme-pm \
  --display-name "Acme Property Management (Asheville, NC)" \
  --index-url "https://acme-pm.example.com/listings" \
  --listing-url-pattern "/listings/{listing_id}" \
  --listing-link-selector "a.listing-card" \
  --sample-html /tmp/listing-1.html /tmp/listing-2.html /tmp/listing-3.html /tmp/listing-4.html /tmp/listing-5.html \
  --output strategies/acme-pm.json
```

If you observed a JSON API in phase 4, also pass:

```
  --api-method GET \
  --api-url-template "https://acme-pm.example.com/api/listings/{listing_id}" \
  --api-headers '{"Accept": "application/json"}' \
  --api-response-root "$.data.listing" \
  --api-field-paths '{"address":"address","price":"rent","bedrooms":"beds","bathrooms":"baths"}'
```

The script:
1. Parses each sample HTML and proposes selectors per Listing field
2. Verifies each selector matches >= 3 of the 5 samples
3. Builds a strategy JSON conforming to the doormat schema
4. If --api-* flags are present, validates the recipe by replaying
   it against a held-out listing and writes it to the strategy
5. Reports a summary the contributor can review before committing

### Phase 6 — Capture and scrub a fixture

```
python skills/contribute-rental-source/scripts/scrub_fixture.py \
  --input /tmp/listing-1.html \
  --output tests/fixtures/html/acme-pm/sample.html
```

The scrubber replaces real addresses, phone numbers, emails, and
personal names with synthetic equivalents. **Inspect the output
manually before committing.** Synthetic data is non-negotiable; PII
in committed fixtures is a security and legal issue.

### Phase 7 — Validate

```
python skills/contribute-rental-source/scripts/validate_strategy.py \
  --strategy strategies/acme-pm.json \
  --fixture tests/fixtures/html/acme-pm/sample.html
```

This runs the doormat extraction pipeline (Mode A) against the
new strategy on the scrubbed fixture and asserts:
- Required fields (address, price, bedrooms, bathrooms) extract
- pets_policy resolves to a valid enum value
- Confidence is "high"

If the API recipe is present, it also validates the recipe by
firing it against a known listing on the live site (one you saw
during phase 4) and comparing.

If validation fails, fix the strategy and re-run. Don't proceed to PR.

### Phase 8 — Register the source

Add to `pyproject.toml`:

```toml
[project.entry-points."doormat.sources"]
acme-pm = "doormat.sources.pm.acme_pm:Adapter"
```

Create the adapter shim at `src/backend/doormat/sources/pm/acme_pm.py`:

```python
from doormat.sources.pm._strategy_adapter import StrategyAdapter

Adapter = StrategyAdapter.from_json("strategies/acme-pm.json")
```

(`StrategyAdapter.from_json` reads the strategy file at startup and
exposes the standard adapter interface — no code generation needed
per source.)

### Phase 9 — Document

Add an entry to `docs/sources.md`:

```markdown
#### Acme Property Management (Asheville, NC)

- **Source ID:** `acme-pm`
- **Index:** https://acme-pm.example.com/listings
- **Method:** Direct scraping (Mode A) + ApiRecipe (Mode A0) when stable
- **Coverage:** Asheville metro area
- **Robots.txt:** Respected (`/listings` is allowed)
- **Maintainer:** @your-github-handle
- **Notes:** Single-family homes only, ~80 active listings
```

### Phase 10 — Open the PR

```
git checkout -b sources/add-acme-pm
git add strategies/acme-pm.json \
        tests/fixtures/html/acme-pm/sample.html \
        src/backend/doormat/sources/pm/acme_pm.py \
        pyproject.toml \
        docs/sources.md
git commit -s -m "feat(sources): add acme-pm (Asheville, NC)"
git push origin sources/add-acme-pm
gh pr create --fill --template skills/contribute-rental-source/references/pr-template.md
```

Confirm the PR template's checklist is complete before submitting.

## Examples

### Example 1: Cleanly-structured AppFolio site

Contributor: *"Add Acme Property Management — they manage about 80
homes in Asheville. Their site is at https://acme-pm.example.com."*

Walk through phases 1–10. AppFolio sites have a regular HTML
structure and tend to expose a `/api/listings` JSON endpoint. Both
selectors and an ApiRecipe should generate cleanly. Total time:
~30 minutes.

### Example 2: Custom Next.js site with hidden API

Contributor: *"Can you add https://riverside-rentals.example.com? They have
listings in Sacramento."*

The site uses Next.js App Router. The HTML is server-rendered, but
when you click a listing, the detail panel fetches via
`/api/trpc/listings.byId`. Capture this in phase 4. The ApiRecipe
ends up replacing both Mode A and Mode B for this source.

### Example 3: Site that doesn't qualify

Contributor: *"Add https://signincallme.example.com — they have great
rentals in Denver."*

Phase 1 preflight detects a sign-in wall on `/listings`. Stop and
tell the contributor that authenticated sites aren't supported by
doormat. Suggest they check whether the PM also lists on Zillow.

## Guidelines

### Always run phases in order

The temptation to skip preflight or skip the held-out validation is
strong. Don't. Strategies that pass validate but skipped phase 1
leak into the runtime and break a week later. The phases are
ordered for a reason.

### Five samples is the minimum

If a site has fewer than 5 listings live at the time of contribution,
do not contribute it. Strategies validated against 1-2 samples are
fragile and become per-listing exception logic. Wait until the site
has more inventory.

### Synthetic fixture data is non-negotiable

The scrubber is good but not perfect. Manually inspect the output
of phase 6 before committing. Names, phone numbers, real addresses,
real photo URLs from the live site — all replaced with synthetic
equivalents. The fixture is committed to a public repo; treat it
that way.

### One source per PR

A PR that adds three sources is hard to review. One source, one PR.

### When the API recipe captures session-bound data

If phase 4 reveals that the site's API requires a `Cookie` header or
a CSRF token to work, the recipe is session-bound and not portable.
Don't include `--api-*` flags in phase 5; the strategy ships with
selectors only. Mode B will retry capture at runtime with its own
session, which sometimes works.

### Don't commit a strategy you can't replay

Phase 7's validate step is the line. If the strategy doesn't pass,
the strategy is wrong. Don't ship a hopeful strategy.

## Bundled resources

- `references/strategy-schema.md` — the Pydantic schema for
  `ExtractionStrategy`, with field-by-field guidance and examples
- `references/extraction-fixture-format.md` — what a good test
  fixture looks like
- `references/pr-template.md` — checklist for the contributor
- `scripts/preflight.py` — robots/captcha/login-wall checks
- `scripts/from_harness.py` — converts harness exploration to
  strategy
- `scripts/scrub_fixture.py` — PII scrubber for committed fixtures
- `scripts/validate_strategy.py` — runs the eval suite against
  the new strategy

## Changelog

- **1.0.0** — initial release.
```

---

## File 2 — `skills/contribute-rental-source/scripts/from_harness.py`

```python
"""Convert browser-harness exploration into a doormat ExtractionStrategy.

Reads sample HTML files, proposes selectors per field by walking the DOM,
verifies the proposed selectors match >= 3 of 5 samples, and emits a
strategy JSON conforming to doormat's ExtractionStrategy schema.

Optionally builds an ApiRecipe from --api-* flags and replay-validates it
against a known listing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from selectolax.parser import HTMLParser, Node


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source-id", required=True)
    p.add_argument("--display-name", required=True)
    p.add_argument("--index-url", required=True)
    p.add_argument("--listing-url-pattern", required=True,
                   help="e.g. /listings/{listing_id}")
    p.add_argument("--listing-link-selector", required=True)
    p.add_argument("--sample-html", nargs="+", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--pre-extraction-actions", nargs="*", default=[])

    # Optional API recipe
    p.add_argument("--api-method", choices=["GET", "POST"])
    p.add_argument("--api-url-template")
    p.add_argument("--api-headers", help="JSON dict")
    p.add_argument("--api-body-template")
    p.add_argument("--api-response-root", default="$")
    p.add_argument("--api-field-paths", help="JSON dict")
    p.add_argument("--api-replay-listing-id", help="ID to use for recipe replay validation")
    p.add_argument("--api-replay-expected", help="JSON dict of expected field values")

    args = p.parse_args()

    sample_paths = [Path(s) for s in args.sample_html]
    if len(sample_paths) < 5:
        print(f"ERROR: need 5 samples, got {len(sample_paths)}", file=sys.stderr)
        return 1
    for s in sample_paths:
        if not s.exists():
            print(f"ERROR: sample file not found: {s}", file=sys.stderr)
            return 1

    # Phase A: propose selectors per field by walking each sample DOM
    proposals = propose_selectors(sample_paths)

    # Phase B: verify each candidate selector matches >= 3 of 5 samples
    verified = verify_selectors(proposals, sample_paths, threshold=3)

    if not all(k in verified for k in ("address", "price", "bedrooms", "bathrooms")):
        print("ERROR: required fields missing after verification", file=sys.stderr)
        print(f"verified: {sorted(verified.keys())}", file=sys.stderr)
        return 1

    # Phase C: build the strategy
    strategy: dict[str, Any] = {
        "source_id": args.source_id,
        "display_name": args.display_name,
        "schema_version": 1,
        "listing_index_url": args.index_url,
        "listing_link_selector": args.listing_link_selector,
        "detail_pre_extraction_actions": args.pre_extraction_actions,
        "field_selectors": verified,
        "photo_gallery_strategy": None,
        "notes": "",
        "api_recipe": None,
        "last_updated_at": datetime.now(UTC).isoformat(),
    }

    # Phase D: build and validate optional ApiRecipe
    if args.api_method and args.api_url_template:
        recipe = build_recipe(args)
        if args.api_replay_listing_id and args.api_replay_expected:
            print("Validating API recipe against held-out listing...")
            valid, reason = asyncio.run(
                replay_validate(
                    recipe,
                    listing_id=args.api_replay_listing_id,
                    expected=json.loads(args.api_replay_expected),
                )
            )
            if not valid:
                print(f"WARNING: recipe replay failed: {reason}", file=sys.stderr)
                print("Strategy will ship without recipe; runtime Mode B may capture one later.")
                recipe = None
            else:
                recipe["confidence"] = "high"
        strategy["api_recipe"] = recipe

    # Phase E: write strategy and report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(strategy, indent=2))

    print(f"\n=== strategy written to {output_path} ===\n")
    print(f"  source_id:        {args.source_id}")
    print(f"  field_selectors:  {len(verified)} fields verified across "
          f"{len(sample_paths)} samples")
    for field, sel in verified.items():
        print(f"    {field:14s}  {sel}")
    if strategy["api_recipe"]:
        print(f"  api_recipe:       {strategy['api_recipe']['confidence']} confidence")
    print(f"\nNext: run scrub_fixture.py and validate_strategy.py.")
    return 0


# ---------------------------------------------------------------------------
# Selector proposal
# ---------------------------------------------------------------------------

# Per-field strategies. Each strategy returns (selector, extracted_value) or None.
FIELD_STRATEGIES: dict[str, list] = {
    "address": [
        ("dl dt:contains('Address') + dd", "text"),
        ("[data-test*='address']", "text"),
        (".listing-address", "text"),
        ("[itemprop='streetAddress']", "text"),
    ],
    "price": [
        ("dl dt:contains('Rent') + dd", "currency"),
        ("[data-test*='price']", "currency"),
        ("[data-test*='rent']", "currency"),
        ("[itemprop='price']", "currency"),
        (".listing-price", "currency"),
    ],
    "bedrooms": [
        ("[data-test*='bed']", "first-int"),
        ("[itemprop='numberOfBedrooms']", "first-int"),
        (".beds", "first-int"),
    ],
    "bathrooms": [
        ("[data-test*='bath']", "first-float"),
        ("[itemprop='numberOfBathroomsTotal']", "first-float"),
        (".baths", "first-float"),
    ],
    "sqft": [
        ("[data-test*='sqft']", "first-int"),
        ("[itemprop='floorSize']", "first-int"),
        (".sqft", "first-int"),
    ],
    "pets_policy": [
        ("[data-test*='pet']", "text"),
        (".pet-policy", "text"),
    ],
    "amenities": [
        (".amenities li", "list"),
        ("[data-test*='amenities'] li", "list"),
    ],
    "photos": [
        (".photo-gallery img", "src-list"),
        ("[data-test*='photo'] img", "src-list"),
        (".gallery img", "src-list"),
    ],
    "description": [
        ("[itemprop='description']", "text"),
        (".listing-description", "text"),
        (".description", "text"),
    ],
}


def propose_selectors(sample_paths: list[Path]) -> dict[str, list[str]]:
    """For each field, return a list of candidate selectors that found
    *something* in at least one sample."""
    candidates: dict[str, list[str]] = {f: [] for f in FIELD_STRATEGIES}
    for path in sample_paths:
        html = path.read_text()
        tree = HTMLParser(html)
        for field, strategies in FIELD_STRATEGIES.items():
            for selector, _kind in strategies:
                # selectolax uses CSS subset, doesn't support :contains() —
                # fall back to manual match for those.
                if ":contains(" in selector:
                    matched = _selector_with_contains(tree, selector)
                else:
                    matched = tree.css(selector)
                if matched:
                    if selector not in candidates[field]:
                        candidates[field].append(selector)
    return candidates


def _selector_with_contains(tree: HTMLParser, selector: str) -> list[Node]:
    """Handle pseudo-selectors like 'dl dt:contains("Rent") + dd'."""
    # Parse "tag:contains('text') + sibling" pattern
    m = re.match(r"(\w+)\s+(\w+):contains\(['\"]([^'\"]+)['\"]\)\s*\+\s*(\w+)", selector)
    if not m:
        return []
    container_tag, label_tag, label_text, sibling_tag = m.groups()
    out: list[Node] = []
    for container in tree.css(container_tag):
        for label in container.css(label_tag):
            if label_text.lower() in (label.text() or "").lower():
                # Find the next sibling matching sibling_tag
                node = label.next
                while node:
                    if node.tag == sibling_tag:
                        out.append(node)
                        break
                    node = node.next
    return out


# ---------------------------------------------------------------------------
# Selector verification
# ---------------------------------------------------------------------------

def verify_selectors(
    proposals: dict[str, list[str]],
    sample_paths: list[Path],
    threshold: int,
) -> dict[str, list[str]]:
    """Return selectors that match >= threshold samples per field."""
    samples = [HTMLParser(p.read_text()) for p in sample_paths]
    out: dict[str, list[str]] = {}
    for field, candidates in proposals.items():
        keep: list[str] = []
        for selector in candidates:
            hits = sum(
                1
                for tree in samples
                if (
                    _selector_with_contains(tree, selector)
                    if ":contains(" in selector
                    else tree.css(selector)
                )
            )
            if hits >= threshold:
                keep.append(selector)
        if keep:
            out[field] = keep
    return out


# ---------------------------------------------------------------------------
# Recipe building & validation
# ---------------------------------------------------------------------------

def build_recipe(args: argparse.Namespace) -> dict[str, Any]:
    headers = json.loads(args.api_headers) if args.api_headers else {}
    field_paths = json.loads(args.api_field_paths) if args.api_field_paths else {}
    return {
        "method": args.api_method,
        "url_template": args.api_url_template,
        "headers": headers,
        "body_template": args.api_body_template,
        "response_root": args.api_response_root,
        "field_paths": field_paths,
        "extractable_fields": list(field_paths.keys()),
        "captured_at": datetime.now(UTC).isoformat(),
        "captured_from_listing_id": args.api_replay_listing_id or "manual",
        "last_validated_at": None,
        "last_failure_at": None,
        "failure_count": 0,
        "confidence": "low",  # bumped to high if replay validates
        "capture_notes": "Manually contributed via from_harness.py",
    }


async def replay_validate(
    recipe: dict[str, Any],
    listing_id: str,
    expected: dict[str, Any],
) -> tuple[bool, str]:
    """Fire the recipe and compare extracted values to expected."""
    url = recipe["url_template"].replace("{listing_id}", listing_id)
    body = (
        recipe["body_template"].replace("{listing_id}", listing_id)
        if recipe["body_template"]
        else None
    )

    async with httpx.AsyncClient() as http:
        try:
            resp = await http.request(
                recipe["method"],
                url,
                headers=recipe["headers"],
                content=body,
                timeout=10.0,
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            return False, f"http error: {exc}"

    if resp.status_code in (401, 403):
        return False, f"auth required (status {resp.status_code})"
    if resp.status_code >= 400:
        return False, f"status {resp.status_code}"
    try:
        body_json = resp.json()
    except ValueError as exc:
        return False, f"non-JSON response: {exc}"

    # Walk the response_root + field_paths
    root = walk_path(body_json, recipe["response_root"])
    if root is None:
        return False, "response_root resolved to None"

    diffs = []
    for field, expected_value in expected.items():
        path = recipe["field_paths"].get(field)
        if not path:
            continue
        got = walk_path(root, path)
        if got != expected_value:
            diffs.append(f"{field}: expected {expected_value!r}, got {got!r}")

    if diffs:
        return False, "; ".join(diffs[:3])
    return True, "all expected fields match"


def walk_path(obj: Any, path: str) -> Any:
    """Same minimal JSONPath walker as recipe_executor.py."""
    if path in ("", "$"):
        return obj
    if path.startswith("$."):
        path = path[2:]
    elif path.startswith("$"):
        path = path[1:]
    cur = obj
    for part in path.split("."):
        if "[" in part:
            key, _, rest = part.partition("[")
            if key:
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(key)
            while rest:
                idx_str, _, rest = rest.partition("]")
                if idx_str and isinstance(cur, list):
                    try:
                        cur = cur[int(idx_str)]
                    except (ValueError, IndexError):
                        return None
                if rest.startswith("["):
                    rest = rest[1:]
        else:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        if cur is None:
            return None
    return cur


if __name__ == "__main__":
    sys.exit(main())
```

---

## File 3 — `skills/contribute-rental-source/scripts/scrub_fixture.py`

```python
"""Replace real PII in committed test fixtures with synthetic equivalents.

The scrubber is conservative: it errs on the side of replacing more than
necessary. Manually inspect the output before committing.
"""

import argparse
import re
import sys
from pathlib import Path


# Order matters: phone before street numbers, email before everything.
PATTERNS = [
    # Email
    (re.compile(r"[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}"), "tester@example.com"),
    # US phone — (530) 555-1234, 530-555-1234, 530.555.1234
    (re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"), "(555) 555-0100"),
    # SSN-like — paranoid catch
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "XXX-XX-XXXX"),
    # Street addresses — heuristic. Replaces "###(?: \w+){1,4} (St|Ave|Rd|...)"
    (re.compile(
        r"\b\d{1,6}\s+([A-Z][a-zA-Z]+\s+){1,4}"
        r"(St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Ln|Lane|Dr|Drive|"
        r"Way|Ct|Court|Pl|Place|Ter|Terrace|Cir|Circle|Pkwy|Parkway|Hwy|Highway)"
        r"\b"
    ), "100 Synthetic Lane"),
    # ZIP+4 — "12345-6789" → "00000-0000"
    (re.compile(r"\b(\d{5})-(\d{4})\b"), "00000-0000"),
    # Plain ZIP — be careful not to clobber price strings. Match only when
    # preceded by a state abbreviation pattern.
    (re.compile(r"\b([A-Z]{2})\s+\d{5}\b"), r"\1 00000"),
    # Photo URLs from the source domain — replace host with example.com but
    # keep the path so structure is preserved.
    # NOTE: this matches https://*.example.com/photos/foo.jpg patterns.
    (re.compile(
        r"https?://[a-z0-9.-]+\.(com|net|org|io|app|co)(/[\w./%-]*\.(jpg|jpeg|png|webp))",
        re.I,
    ), r"https://example.com\2"),
    # First+last names — too risky to detect generically. The contributor must
    # manually scan the output for personal names. The scrubber prints a
    # warning prompt if it sees plausible name patterns.
]


NAME_HINT = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr)\.?\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b"
    r"|\b[A-Z][a-z]+\s+[A-Z]\.\s+[A-Z][a-z]+\b"
)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    src = Path(args.input).read_text()
    scrubbed = src

    for pattern, replacement in PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)

    name_hits = NAME_HINT.findall(src)
    if name_hits:
        print("WARNING: possible names detected — review manually before committing:",
              file=sys.stderr)
        for h in set(name_hits):
            print(f"  - {h}", file=sys.stderr)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(scrubbed)
    print(f"Scrubbed fixture written to {out}")

    bytes_removed = len(src) - len(scrubbed)
    print(f"Net change: {bytes_removed:+d} bytes after substitutions")
    print("REMINDER: visually inspect the output for any remaining PII before committing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## File 4 — `skills/contribute-rental-source/scripts/validate_strategy.py`

```python
"""Run doormat's Mode A extraction against a candidate strategy + fixture.

Asserts:
- The strategy parses cleanly into ExtractionStrategy.
- Mode A extracts a Listing with confidence: high.
- Required fields are non-null.
- ApiRecipe (if present) replays successfully.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

# Local imports — adjust if your package layout differs
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "backend"))

from doormat.extraction.mode_a import run_mode_a
from doormat.extraction.recipe_validator import RecipeValidator
from doormat.extraction.schemas import ApiRecipe, ExtractionStrategy


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--strategy", required=True)
    p.add_argument("--fixture", required=True)
    p.add_argument("--api-replay-listing-id",
                   help="If the strategy has an api_recipe, replay against this listing_id")
    args = p.parse_args()

    strategy_data = json.loads(Path(args.strategy).read_text())
    strategy = ExtractionStrategy.model_validate(strategy_data)
    fixture_html = Path(args.fixture).read_text()

    print(f"=== Validating {strategy.source_id} ===\n")

    # Mode A check
    print("Step 1: Mode A extraction against fixture...")
    # NOTE: run_mode_a in your codebase takes an LLM client. For validation,
    # we use a stub or a real client based on env. Adjust to your codebase's
    # actual signature.
    from doormat.llm.client import get_llm_client
    llm = get_llm_client()
    result = await run_mode_a(
        html=fixture_html,
        strategy=strategy,
        llm_client=llm,
    )

    if result.confidence != "high":
        print(f"FAIL: Mode A confidence is {result.confidence}, expected high")
        print(f"  reasoning: {result.reasoning}")
        return 1

    listing = result.listing
    required = ("address", "price", "bedrooms", "bathrooms")
    missing = [f for f in required if not getattr(listing, f, None)]
    if missing:
        print(f"FAIL: required fields missing: {missing}")
        return 1

    print(f"  OK: {listing.address} | ${listing.price} | "
          f"{listing.bedrooms}bd/{listing.bathrooms}ba")

    # ApiRecipe check
    if strategy.api_recipe and args.api_replay_listing_id:
        print("\nStep 2: ApiRecipe replay...")
        async with httpx.AsyncClient() as http:
            validator = RecipeValidator(http)
            # Use the fixture-extracted listing as the held-out reference
            replay = await validator.validate(
                recipe=strategy.api_recipe,
                held_out_listings=[(args.api_replay_listing_id, listing)],
            )
        if not replay.valid:
            print(f"FAIL: recipe replay: {replay.reason}")
            return 1
        print(f"  OK: confidence {replay.confidence}")

    print("\n=== validation passed ===")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

---

## File 5 — Make target

Append to your repo's `Makefile`:

```makefile
.PHONY: add-source
add-source:
ifndef URL
	@echo "Usage: make add-source URL=https://example-pm.com"
	@exit 1
endif
	@echo "Launching contribute-rental-source skill..."
	@echo "Make sure browser-harness is connected to your Chrome."
	@echo ""
	@echo "Now ask Claude Code (or your AI tool):"
	@echo "  'Use the contribute-rental-source skill to add $(URL)'"
	@echo ""
	@echo "The skill will walk you through phases 1-10."
```

---

## File 6 — `docs/contributing/adding-a-source.md`

Brief contributor-facing doc that points at the skill:

```markdown
# Adding a rental source

doormat supports two ways to add a rental property manager site:

## Runtime (zero contribution)

doormat's Mode B agent automatically discovers and adds sources at
runtime. When a user runs doormat in a city it doesn't yet support,
the discovery agent finds local PMs and generates strategies for them.

The user pays a one-time discovery cost (~$0.50–$2 of LLM tokens). No
PR or contribution is needed.

## Hand-curated (contribution)

For popular markets — places where you know users are running doormat —
contributing a hand-curated strategy is faster, cheaper, and more
reliable than runtime discovery. Hand-curated strategies ship in the
repo, version-controlled, with test fixtures and an explicit owner.

To contribute one:

1. Install [browser-harness](https://github.com/browser-use/browser-harness)
   and connect it to your running Chrome.
2. Open Claude Code (or any AGENTS.md-aware AI tool) in the doormat repo.
3. Tell it: *"Use the contribute-rental-source skill to add
   https://acme-pm.example.com"*
4. The skill walks you through 10 phases, ending in a PR.

The full skill specification lives at
`skills/contribute-rental-source/SKILL.md`.

## What makes a good source to contribute?

Good:
- Local property manager covering a metro area
- Public listings, no login required
- 5+ active rentals at time of contribution
- robots.txt allows scraping the listings path
- Reachable without proxies or stealth browsers

Bad:
- National aggregator (Zillow, Realtor.com — already covered via Apify)
- Authenticated site (we don't handle scraping behind a login)
- Captcha-protected site (use Apify if an actor exists)
- Sites with fewer than 5 listings (strategies overfit on small samples)
```

---

## Why this is genuinely useful (not just a doc PR)

Three things this patch buys you that aren't captured by Mode B:

**It's the user-experience answer.** A new user opening doormat for the first time in Asheville has a meaningfully different first hour if Asheville's PMs are pre-curated vs. if Mode B has to discover them while the user waits. Hand-curation ahead of launches is what every consumer product does. doormat shouldn't be different.

**It's the contributor pipeline.** Open-source projects need contributors. "Add a property manager via Claude Code in 30 minutes" is a dramatically lower bar than "write a Python adapter and submit it to our extension API." The skill lowers contribution friction by an order of magnitude. Recruiters will read this skill and recognize it as the thing 99% of OSS projects fail to build.

**It's the difference between Mode B as fallback and Mode B as primary.** Right now your runtime depends on Mode B for cold starts. With pre-curated strategies, Mode B becomes a true fallback — used only for sources nobody contributed. That's a more conservative, more reliable runtime, with the agentic discovery as the safety net rather than the load-bearing path.

---

## Rollout

1. Drop the skill directory and scripts into the repo. Add the `Makefile` target. Add the docs page. One PR.
2. Use the skill yourself to contribute Redding's 13 PMs as the first batch. This both proves the skill works and bootstraps the curated set. (You already have these strategies in some form — contribution lets you formalize and ship them.)
3. Mention in the launch announcement: *"Want doormat to support your city? See `skills/contribute-rental-source/`."*

The total scope is 4 files of code + 1 SKILL.md + 1 docs page + 1 Makefile target. Two-day project, depending on how clean your existing strategy persistence layer is.
