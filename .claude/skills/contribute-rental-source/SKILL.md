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

This skill walks the contributor through adding a new rental property manager site to doormat as a hand-curated source. The end deliverable is a PR containing:

1. An `ExtractionStrategy` JSON file under `strategies/<source-id>.json`
2. A scrubbed HTML test fixture under `tests/fixtures/html/<source-id>/sample.html`
3. (Optional) An `ApiRecipe` if the site has a usable JSON API
4. A docs entry under `docs/sources.md`
5. An entry-point registration in `pyproject.toml` (via `StrategyAdapter`)

## When to use this skill

Use it when:

- The contributor says "add a property manager", "add a source", "contribute a rental site"
- The contributor says "I want doormat to support [URL]"
- The contributor pastes a PM site URL and asks "can doormat scrape this?"
- The contributor mentions a city they care about and wants doormat to work well there from day one

Do NOT use it when:

- The user is just running doormat normally — runtime discovery is Mode B's job, not this skill's
- The site requires login to view listings — doormat does not handle authenticated scrapes
- The site is a national aggregator (Zillow, Realtor.com, Apartments.com) — those are routed through Apify

## Prerequisites

This skill depends on **browser-harness** being installed and connected to the contributor's running Chrome. If it isn't, prompt the contributor to install it first:

```bash
git clone https://github.com/browser-use/browser-harness ~/tools/browser-harness
cd ~/tools/browser-harness
uv sync
# Follow install.md to connect to Chrome
```

The harness gives you `goto`, `click`, `screenshot`, `js`, `http_get`, and the rest of the helpers. You'll use them extensively here.

The contributor must also have doormat cloned and `uv sync --dev` complete.

## Workflow overview

Run these phases in order. Each phase has explicit verification. Don't skip ahead — a strategy that passes Phase 7 but failed Phase 3 is a strategy that will work today and break next month.

### Phase 1 — Pre-flight

Before opening the page in Chrome, verify it's a legitimate target.

1. Run `python skills/contribute-rental-source/scripts/preflight.py <URL>`. This checks:
   - `robots.txt` — does it disallow listings paths?
   - HTTP status — does the site respond?
   - Login wall — is there a sign-in requirement on the index page?
   - Captcha presence — does the page bounce to a Cloudflare or reCAPTCHA challenge?

2. If preflight returns any blocker, **stop and tell the contributor**. Don't try to work around `robots.txt`. Captcha-protected sites are runtime-only (they go through Apify, not through this skill).

If preflight passes, proceed.

### Phase 2 — Harness connection

1. Verify the contributor's Chrome is connected to browser-harness.
2. Navigate to the source URL via the harness and take a screenshot to confirm you're on the right page.
3. If the screenshot doesn't match what the contributor expected, stop and ask.

### Phase 3 — Map the listing structure

Identify how listings are linked from the index using JavaScript introspection and DOM analysis.

1. Harvest listing links with CSS selectors and identify the canonical URL pattern.
2. Identify the listing-link CSS selector (e.g., `.listing-card a`, `a[href*="/listings/"]`).
3. Test pagination if applicable (Next page, `?page=2`, infinite scroll).

### Phase 4 — Sample five listings

Pick 5 listings spread across the index. For each listing:

1. Capture the full HTML of the listing's main content area.
2. Record the human-readable values (address, rent, beds, baths, sqft, pets, amenities, photos).
3. **CRITICAL: capture network traffic.** If the page loads its own data via JSON, note:
   - The endpoint URL pattern
   - The HTTP method (GET/POST)
   - Any X-* headers required (NOT Cookie / Authorization)
   - A sample response

This information becomes an `ApiRecipe` in the strategy (huge perf win).

### Phase 5 — Generate the strategy

Run the conversion script:

```bash
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

```bash
  --api-method GET \
  --api-url-template "https://acme-pm.example.com/api/listings/{listing_id}" \
  --api-headers '{"Accept": "application/json"}' \
  --api-response-root "$.data.listing" \
  --api-field-paths '{"address":"address","price":"rent","bedrooms":"beds","bathrooms":"baths"}'
```

### Phase 6 — Capture and scrub a fixture

```bash
python skills/contribute-rental-source/scripts/scrub_fixture.py \
  --input /tmp/listing-1.html \
  --output tests/fixtures/html/acme-pm/sample.html
```

**Inspect the output manually before committing.** Synthetic data is non-negotiable; PII in committed fixtures is a security and legal issue.

### Phase 7 — Validate

```bash
python skills/contribute-rental-source/scripts/validate_strategy.py \
  --strategy strategies/acme-pm.json \
  --fixture tests/fixtures/html/acme-pm/sample.html
```

This runs the doormat extraction pipeline (Mode A) against the strategy on the scrubbed fixture and asserts:
- Required fields (address, price, bedrooms, bathrooms) extract
- `pets_policy` resolves to a valid enum value
- Confidence is "high"

If the API recipe is present, it also validates the recipe against a known listing on the live site.

If validation fails, fix the strategy and re-run. **Don't proceed to PR.**

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

### Phase 9 — Document

Add an entry to `docs/sources.md`:

```markdown
#### Acme Property Management (Asheville, NC)

- **Source ID:** `acme-pm`
- **Index:** https://acme-pm.example.com/listings
- **Method:** Direct scraping (Mode A) + ApiRecipe (Mode A0)
- **Coverage:** Asheville metro area
- **Robots.txt:** Respected (`/listings` is allowed)
- **Maintainer:** @your-github-handle
- **Notes:** Single-family homes only, ~80 active listings
```

### Phase 10 — Open the PR

```bash
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

## Guidelines

- **Always run phases in order.** Skipping preflight or validation leads to broken strategies.
- **Five samples is the minimum.** Strategies validated against 1-2 samples are fragile.
- **Synthetic fixture data is non-negotiable.** Manually inspect scrubbed output before committing.
- **One source per PR.** A PR with three sources is hard to review.
- **Don't commit a strategy you can't replay.** Phase 7's validate step is the line.

## Bundled resources

- `references/strategy-schema.md` — the `ExtractionStrategy` schema with field-by-field guidance
- `references/extraction-fixture-format.md` — what a good test fixture looks like
- `references/pr-template.md` — checklist for the contributor
- `scripts/preflight.py` — robots/captcha/login-wall checks
- `scripts/from_harness.py` — converts harness exploration to strategy
- `scripts/scrub_fixture.py` — PII scrubber for committed fixtures
- `scripts/validate_strategy.py` — runs Mode A extraction against the strategy
