# Adding a rental source

This guide walks you through contributing a new rental property manager source to doormat as a hand-curated, version-controlled strategy.

## Why contribute a source?

doormat automatically discovers property managers at runtime via Mode B. However, pre-curated strategies have big advantages:

- **Instant results** — New users in your city get matches on day one, not after 2–5 minutes and $0.50–$2 in LLM costs
- **Tested & reliable** — Your strategy is validated against real fixtures before merging
- **Version-controlled** — Changes are tracked, reviewed, and easy to revert if a PM redesigns their site

## Prerequisites

Before starting, you'll need:

1. **doormat repo** — Cloned and set up with `uv sync --dev`
2. **browser-harness** — Installed and connected to your Chrome browser
   ```bash
   git clone https://github.com/browser-use/browser-harness ~/tools/browser-harness
   cd ~/tools/browser-harness
   uv sync
   # Follow install.md to connect to Chrome
   ```
3. **A PM site in mind** — A public, non-authenticated property manager website you want to support

## Workflow overview

The contribution workflow has 10 phases, all handled by the `contribute-rental-source` skill. You provide samples and configs; the skill generates the strategy, validates it, and opens a PR.

**Estimated time:** 30–60 minutes depending on site structure complexity.

### Phase 1 — Pre-flight checks

Verify the site is eligible:

```bash
cd doormat
python .claude/skills/contribute-rental-source/scripts/preflight.py https://acme-pm.example.com/listings
```

This checks:
- ✓ `robots.txt` allows scraping (respects robots.txt rules)
- ✓ HTTP 200 response (site is accessible)
- ✓ No login wall (public listings page)
- ✓ No Captcha (not bot-challenged)

**If preflight fails**, stop. The site isn't eligible (check with maintainers if you think otherwise).

### Phase 2 — Browser-harness connection

Open your Chrome browser and verify browser-harness can control it. The skill will use it to explore the listing structure and capture sample HTML.

### Phase 3 — Map the listing structure

Using browser-harness, identify:
- Where listings are linked from the index (`a.listing-card`, etc.)
- The canonical URL pattern (`/listings/123`, `/property/abc`, etc.)
- How pagination works (Next button, `?page=2`, infinite scroll)

The skill will help you capture this information.

### Phase 4 — Sample five listings

Pick 5 representative listings across the index (not all from page 1). For each:
1. Capture the listing's HTML
2. Note the human-readable values (address, rent, beds, baths, pets, amenities)
3. Check if there's a usable JSON API (check Network tab for XHR/fetch calls)

The script will guide you through this.

### Phase 5 — Generate the strategy

Run the conversion script:

```bash
python .claude/skills/contribute-rental-source/scripts/from_harness.py \
  --source-id acme-pm \
  --display-name "Acme Property Management (Asheville, NC)" \
  --index-url "https://acme-pm.example.com/listings" \
  --listing-url-pattern "/listings/{listing_id}" \
  --listing-link-selector "a.listing-card" \
  --sample-html /tmp/listing-1.html /tmp/listing-2.html /tmp/listing-3.html /tmp/listing-4.html /tmp/listing-5.html \
  --output strategies/acme-pm.json
```

If you found a JSON API, also add:

```bash
  --api-method GET \
  --api-url-template "https://acme-pm.example.com/api/listings/{listing_id}" \
  --api-headers '{"Accept": "application/json"}' \
  --api-response-root "$.data.listing" \
  --api-field-paths '{"address":"address","price":"rent","bedrooms":"beds","bathrooms":"baths"}'
```

### Phase 6 — Scrub the fixture

Clean PII from the sample HTML before committing:

```bash
python .claude/skills/contribute-rental-source/scripts/scrub_fixture.py \
  --input /tmp/listing-1.html \
  --output tests/fixtures/html/acme-pm/sample.html
```

**⚠️ IMPORTANT**: Manually review the scrubbed output before committing. Replace any:
- Real street addresses → synthetic addresses
- Real phone numbers → test numbers
- Real emails → generic placeholders
- Real names → generic placeholders

Committed PII is a legal and security issue.

### Phase 7 — Validate

Test your strategy against the scrubbed fixture:

```bash
python .claude/skills/contribute-rental-source/scripts/validate_strategy.py \
  --strategy strategies/acme-pm.json \
  --fixture tests/fixtures/html/acme-pm/sample.html
```

If validation passes (all required fields extracted with high confidence), proceed to Phase 8. If not, adjust your strategy selectors and retry.

### Phase 8 — Register the source

Add an entry point to `pyproject.toml`:

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
- **Method:** Direct scraping (Mode A)
- **Coverage:** Asheville metro area
- **Robots.txt:** Respected
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
gh pr create --fill --template .claude/skills/contribute-rental-source/references/pr-template.md
```

Fill out the PR template checklist completely before submitting.

## Guidelines

### Always run phases in order

Skipping preflight or validation can lead to broken strategies. Phases are ordered for a reason.

### Five samples is the minimum

If the site has fewer than 5 listings at contribution time, wait. Strategies validated against 1–2 samples are fragile.

### Synthetic fixture data is non-negotiable

Manual review after scrubbing is mandatory. Real PII in committed fixtures is unacceptable.

### One source per PR

Multi-source PRs are hard to review. One source, one PR.

### When the API has session-bound auth

If the JSON API requires `Cookie` or `Authorization` headers, don't include it. The recipe can't be portable across sessions. Selectors-only is fine.

## Reference

- **Skill documentation**: `.claude/skills/contribute-rental-source/SKILL.md`
- **Strategy schema**: `.claude/skills/contribute-rental-source/references/strategy-schema.md`
- **Fixture guidelines**: `.claude/skills/contribute-rental-source/references/extraction-fixture-format.md`
- **PR template**: `.claude/skills/contribute-rental-source/references/pr-template.md`

## Questions?

If you hit issues:

1. **Preflight failing?** The site may block bots or have auth walls. Try a different site.
2. **Selectors not matching?** Check that your sample HTML is representative. Try additional samples if available.
3. **Validation failing?** Review your selectors against the fixture HTML. Use browser DevTools to verify CSS/XPath patterns.
4. **Need help?** Open an issue in the repo — maintainers are here to help.

## Thank you! 🙏

Your contribution helps users in your region get instant rental results on day one. doormat is stronger because of contributors like you.
