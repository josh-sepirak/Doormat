# PR Template: Add a rental source

**Use this template when submitting a PR that adds a new property manager source to doormat.**

Replace all `[BRACKETED]` placeholders with your details.

---

## Description

This PR adds support for **[Property Manager Name]** operating in **[City/Region]** via the contributor skill.

### Source details

- **Source ID:** `[source-id]` (lowercase, hyphen-separated)
- **Property Manager:** [Legal business name]
- **Market:** [City, State]
- **Index URL:** [URL where listings are browsed]
- **Coverage:** [e.g., "single-family homes in downtown Denver", "apartments across metro area"]

---

## What's included

- [ ] `strategies/[source-id].json` — Extraction strategy with field selectors
- [ ] `tests/fixtures/html/[source-id]/sample.html` — Scrubbed HTML fixture
- [ ] `src/backend/doormat/sources/pm/[source-id].py` — Adapter shim
- [ ] `pyproject.toml` — Entry point registration
- [ ] `docs/sources.md` — Documentation entry

Optional:
- [ ] `strategies/[source-id].json` includes `api_recipe` (JSON API support)
- [ ] `tests/fixtures/html/[source-id]/README.md` — Notes about fixture

---

## Validation

Before submission, all phases of the contribution workflow must complete:

### Phase 1 — Pre-flight ✓
- [ ] Site responded to HTTP (no 503/timeout)
- [ ] `robots.txt` allows listing scraping
- [ ] No login wall detected
- [ ] No Captcha challenge

**Proof:**
```
$ python skills/contribute-rental-source/scripts/preflight.py [INDEX_URL]
Status: PASS ✓
```

### Phase 2 — Browser connection ✓
- [ ] Browser-harness connected to Chrome
- [ ] Successfully navigated to index URL
- [ ] Screenshot matches site layout

### Phase 3 — Listing structure mapped ✓
- [ ] Listing link selector identified
- [ ] Listing URL pattern documented
- [ ] Pagination mechanism identified (if applicable)

### Phase 4 — Five listings sampled ✓
- [ ] 5 representative listings captured
- [ ] Human-readable values extracted (address, rent, beds, baths, etc.)
- [ ] Network traffic inspected for JSON APIs
- [ ] API endpoint documented (if found)

### Phase 5 — Strategy generated ✓
- [ ] `from_harness.py` completed successfully
- [ ] Strategy JSON validates against schema
- [ ] All required field selectors present (address, rent, bedrooms, bathrooms)

**Proof:**
```
$ python skills/contribute-rental-source/scripts/from_harness.py \
    --source-id [source-id] \
    --display-name "[Property Manager Name]" \
    --index-url "[URL]" \
    ...
Generated: strategies/[source-id].json ✓
```

### Phase 6 — Fixture scrubbed ✓
- [ ] `scrub_fixture.py` completed successfully
- [ ] Manual PII review completed (all real addresses, names, emails replaced)
- [ ] Fixture is valid HTML (parseable)

**PII checklist:**
- [ ] No real street addresses (except street names)
- [ ] No real phone numbers
- [ ] No real email addresses
- [ ] No real first/last names
- [ ] No real photo URLs with user IDs or CDN paths
- [ ] All CSS classes and selectors preserved

### Phase 7 — Validation passed ✓
- [ ] `validate_strategy.py` completed successfully
- [ ] All required fields extracted from fixture (address, rent, bedrooms, bathrooms)
- [ ] Confidence level: `high`
- [ ] If API recipe present: recipe replay validated against live listing

**Proof:**
```
$ python skills/contribute-rental-source/scripts/validate_strategy.py \
    --strategy strategies/[source-id].json \
    --fixture tests/fixtures/html/[source-id]/sample.html
Status: PASS ✓
Extracted: address, rent, bedrooms, bathrooms, sqft, pets_policy, amenities, photos
Confidence: high ✓
```

### Phase 8 — Source registered ✓
- [ ] Entry point added to `pyproject.toml` under `[project.entry-points."doormat.sources"]`
- [ ] Adapter shim created at `src/backend/doormat/sources/pm/[source-id].py`

### Phase 9 — Documentation complete ✓
- [ ] Entry added to `docs/sources.md` with source details
- [ ] Docs include: source ID, index URL, method, coverage, robots.txt status, maintainer, notes

### Phase 10 — Ready for review ✓
- [ ] Branch created: `sources/add-[source-id]`
- [ ] All files committed
- [ ] No merge conflicts

---

## Testing

Run the full validation suite locally:

```bash
# Single source validation
python skills/contribute-rental-source/scripts/validate_strategy.py \
  --strategy strategies/[source-id].json \
  --fixture tests/fixtures/html/[source-id]/sample.html

# Lint the strategy JSON
uv run python -c "
  import json
  with open('strategies/[source-id].json') as f:
    strategy = json.load(f)
  print('Strategy JSON valid ✓')
  print(f\"Fields: {list(strategy['field_selectors'].keys())}\")
"

# Run doormat tests to ensure no regressions
uv run pytest tests/ -xvs
```

---

## Type of change

- [ ] New feature (adding a source)
- [ ] Bug fix (fixing existing source)
- [ ] Documentation update

---

## Checklist

- [ ] I have read the contribution skill documentation
- [ ] I have tested the strategy locally (Phase 7 passes)
- [ ] I have scrubbed all PII from the fixture (Phase 6)
- [ ] I have verified my source complies with robots.txt (Phase 1)
- [ ] I have run the pre-commit checks (linting, format)
- [ ] I have updated `docs/sources.md` (Phase 9)

---

## Maintainer notes

- **Confidence level:** [high / medium / low]
- **API recipe included:** [yes / no]
- **Known limitations:** [List any quirks, e.g., "infinite scroll; must scroll to bottom"]
- **Estimated listings:** [e.g., "~150 active listings as of 2026-05-01"]
- **Contact:** [@your-github-handle]

---

## Reviewers: check these

- [ ] Fixture has no PII (spot-check a few real vs. synthetic values)
- [ ] Strategy JSON has all required field selectors
- [ ] Validation passed in contributor's local environment (proof in comment)
- [ ] Entry point correctly registered in `pyproject.toml`
- [ ] Documentation entry is complete and accurate
- [ ] No regressions in existing tests

---

**Thank you for contributing!** 🎉 Your curated strategy will help new users in [City/Region] get results instantly on their first run.
