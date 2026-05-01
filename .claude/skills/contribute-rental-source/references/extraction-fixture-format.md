# Extraction Fixture Format

A fixture is a real or representative HTML page from the property manager's site, scrubbed of all personally identifiable information (PII) and committed to the repo for use in CI/validation tests.

## Purpose

Fixtures allow doormat to validate contributed strategies without depending on live external sites:

1. **Build-time validation** — Contributors run `validate_strategy.py` against the fixture to ensure their strategy works
2. **CI tests** — GitHub Actions validates all contributed strategies against their fixtures on every push
3. **Regression detection** — If a PM changes their HTML structure, our tests catch it immediately

## Format

A fixture is **plain HTML** — a snapshot of a single property listing page. It can be:

- Full page (`<html>` root)
- Document fragment (body or main content only)
- Minified or formatted (both acceptable)

### Structure

```html
<!DOCTYPE html>
<html>
<head>
  <title>Listing #[SYNTHETIC_ID] - Acme Property Management</title>
  <meta charset="utf-8">
</head>
<body>
  <div class="listing-wrapper">
    <h1 class="property-title">[SYNTHETIC_ADDRESS]</h1>
    <div class="price-section">
      <span class="monthly-rent">$[SYNTHETIC_PRICE]</span>
    </div>
    <div class="property-stats">
      <span class="beds">[SYNTHETIC_BEDS]</span>
      <span class="baths">[SYNTHETIC_BATHS]</span>
      <span class="sqft">[SYNTHETIC_SQFT]</span>
    </div>
    <div class="pet-policy">
      Pets: [SYNTHETIC_POLICY]
    </div>
    <div class="amenities">
      <ul>
        <li>Amenity 1</li>
        <li>Amenity 2</li>
      </ul>
    </div>
    <div class="description">
      [SYNTHETIC_DESCRIPTION_TEXT]
    </div>
    <div class="gallery">
      <img src="/photos/synthetic-photo-1.jpg" alt="photo">
      <img src="/photos/synthetic-photo-2.jpg" alt="photo">
    </div>
  </div>
</body>
</html>
```

## PII Replacement Rules

**MUST replace before committing:**

1. **Addresses**
   - Real: `123 Main St, Asheville, NC 28801`
   - Synthetic: `456 Oak Ave, Redding, CA 96001`
   - Use complete fake addresses (not just street names)

2. **Phone numbers**
   - Real: `828-555-1234`
   - Synthetic: `555-0142` or `555-0195` (standard test numbers)
   - Include area code if original had it

3. **Email addresses**
   - Real: `manager@acme-pm.example.com`, `leasing@example.com`
   - Synthetic: `contact@example.com`, `info@example.com`
   - Use generic placeholder emails only

4. **Agent/Owner names**
   - Real: `Sarah Johnson`, `Michael Chen`
   - Synthetic: `Property Manager`, `Leasing Agent`, `PM Staff`
   - Or use generic first names: `John`, `Jane`, `Alex`

5. **Photo URLs**
   - Real: `https://acme-pm.example.com/photos/user-12345/image-xyz.jpg`
   - Synthetic: `/photos/listing-image-1.jpg` or `https://example.com/photos/placeholder.jpg`
   - Strip user IDs, names, timestamps

6. **Personal descriptions or notes**
   - Real: `Contact Sarah at ext. 204 for questions`
   - Synthetic: `Contact leasing office for questions`

7. **Company names (if exact match could identify PII)**
   - Real: `Acme Property Management - 1 Park Ave, Asheville`
   - Synthetic: `Acme Property Management` (without exact address or owner names)

**DO NOT replace:**

- Generic street/place names (Oak Ave, Downtown, etc.)
- Cities, states, ZIP codes (public information)
- Generic amenity names (pool, garage, laundry)
- Listing price ranges (unless linked to specific PII)
- URL patterns and CSS classes (needed for selectors)

## Example fixture

### Before (with PII)

```html
<div class="listing-detail">
  <h1>456 Maple Drive, Apartment 2B</h1>
  <span class="price">$2,800/month</span>
  <div class="contact">
    <p>For inquiries, contact <strong>Jennifer Walsh</strong></p>
    <p>Phone: 828-555-0147</p>
    <p>Email: jennifer@appfolio-pm.example.com</p>
  </div>
  <p>This charming 2BR apartment is managed by Jennifer's team at Appfolio.</p>
  <img src="https://appfolio-cdn.example.com/photos/user-86429/2br-apt.jpg" />
</div>
```

### After (scrubbed)

```html
<div class="listing-detail">
  <h1>123 Sycamore Lane, Apartment 2B</h1>
  <span class="price">$2,800/month</span>
  <div class="contact">
    <p>For inquiries, contact <strong>Property Manager</strong></p>
    <p>Phone: 555-0142</p>
    <p>Email: contact@example.com</p>
  </div>
  <p>This charming 2BR apartment is managed by the Appfolio PM team.</p>
  <img src="/photos/listing-2br.jpg" />
</div>
```

## Validation checklist

Before committing a fixture, verify:

- [ ] No real addresses (cross-check with Google Maps if unsure)
- [ ] No real phone numbers (test numbers only)
- [ ] No real email addresses (generic placeholders)
- [ ] No real names (first names OK, but not surnames unless very generic)
- [ ] No photo URLs pointing to real CDNs with user IDs
- [ ] No quoted personal descriptions or notes with identifying info
- [ ] All CSS classes and selectors intact (needed for strategy)
- [ ] All HTML structure preserved (don't remove DOM elements)
- [ ] Document is valid HTML (can parse with selectolax, beautifulsoup, etc.)

## Storage

Fixtures are committed to:

```
tests/fixtures/html/<source-id>/
├── sample.html              (primary fixture)
├── sample-page-2.html       (optional: second listing)
└── README.md                (optional: notes about fixture)
```

Example:

```
tests/fixtures/html/acme-pm/
├── sample.html
└── README.md  # "Fixture captured 2026-04-30, represents typical Asheville 2BR rental"
```

## Testing fixtures

Run the contribution validation script to test:

```bash
python skills/contribute-rental-source/scripts/validate_strategy.py \
  --strategy strategies/acme-pm.json \
  --fixture tests/fixtures/html/acme-pm/sample.html
```

The validator:

1. Parses the fixture HTML
2. Applies the strategy's selectors
3. Extracts fields
4. Validates required fields are present and parseable
5. Reports success or failure

If validation fails, review the strategy's selectors against the fixture.
