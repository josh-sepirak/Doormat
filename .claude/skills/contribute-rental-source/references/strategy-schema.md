# Strategy Schema Reference

This document describes the `ExtractionStrategy` JSON format that doormat uses to extract rental listing data from property manager websites.

## Top-level structure

```json
{
  "field_selectors": {
    "address": "CSS or XPath selector",
    "rent": "CSS or XPath selector",
    ...
  },
  "pre_extraction_actions": [
    "click .show-more",
    "scroll down 500"
  ],
  "notes": "Optional free-form notes about the source",
  "api_recipe": {
    "method": "GET",
    "url_template": "...",
    ...
  }
}
```

## Field selectors

CSS or XPath selectors identifying where each listing field lives in the HTML. Only fields with extractable data need selectors.

**Required fields** (must include selectors):
- `address` — Full street address
- `rent` — Monthly rent in USD (parse to integer)
- `bedrooms` — Number of bedrooms (integer)
- `bathrooms` — Number of bathrooms (float)

**Optional fields** (selector if data available):
- `sqft` — Square footage (parse to integer, or null)
- `pets_policy` — Pet policy text (parse to enum: `allowed_with_small_dog`, `cats_only`, `none_allowed`, `unknown`)
- `amenities` — List of amenity tags (parse comma/space-separated to lowercase list)
- `photos` — Photo URLs (parse all image src/href attributes)
- `description` — Full listing description (HTML text, clean to 2000 chars)

### Examples

#### Simple CSS selectors

```json
{
  "address": "h1.listing-title",
  "rent": ".rent-price",
  "bedrooms": ".stat-beds",
  "bathrooms": ".stat-baths"
}
```

#### Complex XPath selectors (when CSS fails)

```json
{
  "address": "//div[@class='property-details']//h1/text()",
  "rent": "//span[contains(text(), '$')]/following-sibling::span[1]",
  "bedrooms": "//dt[contains(text(), 'Bed')]/following-sibling::dd[1]"
}
```

## Pre-extraction actions

Interactions required before extraction (clicks, scrolls, waits).

```json
"pre_extraction_actions": [
  "click .show-all-details",
  "wait 1000",
  "scroll down 800"
]
```

## API Recipe (optional)

If the property manager site has a JSON API endpoint that serves listing data, capture it here. This enables the fast Mode A0 path (HTTP only, no browser or LLM).

```json
{
  "method": "GET",
  "url_template": "https://acme-pm.example.com/api/listings/{listing_id}",
  "headers": {
    "Accept": "application/json"
  },
  "body_template": null,
  "response_root": "$.data.listing",
  "field_paths": {
    "address": "$.address",
    "rent": "$.monthlyRent",
    "bedrooms": "$.bedCount",
    "bathrooms": "$.bathCount",
    "sqft": "$.squareFeet",
    "pets_policy": "$.petsAllowed"
  },
  "extractable_fields": ["address", "rent", "bedrooms", "bathrooms", "sqft"],
  "captured_at": "2026-05-01T15:30:00Z",
  "captured_from_listing_id": "12345",
  "last_validated_at": "2026-05-01T15:30:00Z",
  "last_failure_at": null,
  "failure_count": 0,
  "confidence": "high",
  "capture_notes": "API returns full listing in $.data.listing; includes pagination metadata in $.meta"
}
```

### ApiRecipe fields

- `method` — HTTP method (`GET` or `POST`)
- `url_template` — URL pattern with placeholders:
  - `{listing_id}` — The ID from the listing's canonical URL
  - `{slug}` — The URL slug (e.g., `acme-property-123`)
- `headers` — Safe HTTP headers (no `Authorization`, `Cookie`, or `X-CSRF-*` — those are session-bound)
- `body_template` — POST body template (JSON-encoded), or `null` for GET
- `response_root` — JSONPath to the listing object in the response (e.g., `$.data.listing` or `$`)
- `field_paths` — Per-field JSONPath accessors within the response root
- `extractable_fields` — Which fields the recipe can populate (subset of `field_paths.keys()`)
- `captured_at` — ISO 8601 timestamp when the recipe was captured
- `captured_from_listing_id` — The listing ID used during capture (for replay validation)
- `last_validated_at` — When the recipe last passed replay validation
- `last_failure_at` — When the recipe last failed
- `failure_count` — Number of consecutive failures; recipes retire after 3 failures
- `confidence` — `high` (replay-validated), `medium` (matched but unvalidated), or `low` (opportunistically captured)
- `capture_notes` — Free-form notes about quirks or edge cases

## Notes field

Optional free-form notes for the next contributor or runtime agent reviewing this strategy:

```json
"notes": "Site uses infinite scroll; must scroll to page bottom before all listings load. Pagination via JavaScript, not URL parameters."
```

## PetsPolicy enum values

When parsing `pets_policy` from HTML text, map to one of:

- `allowed_with_small_dog` — Pets allowed with restrictions (typically small dogs only)
- `cats_only` — Cats allowed, dogs not
- `none_allowed` — No pets allowed
- `unknown` — Cannot determine from listing text

Precedence rules (from `doormat.schemas`):
1. If text contains "no pets", `NONE_ALLOWED`
2. If text contains "dogs" without "no dogs", prefer `ALLOWED_WITH_SMALL_DOG`
3. If text contains "cats only", `CATS_ONLY`
4. Otherwise, `UNKNOWN`

## Validation

All fields are validated at contribution time:

- `field_selectors` — Must be non-empty and select valid CSS/XPath
- `address`, `rent`, `bedrooms`, `bathrooms` selectors — Required
- `rent` parse — Must be 0–50,000 USD
- `bedrooms` parse — Must be 0–20
- `bathrooms` parse — Must be 0.0–20.0 (allows half-baths)
- `sqft` parse — If present, must be 100–20,000
- `amenities` — Max 20 tags, lowercase only
- `photos` — Max 20 URLs, valid HTTP/HTTPS only
- `description` — Max 2000 characters

## Example: Complete strategy

```json
{
  "field_selectors": {
    "address": "h1.property-address",
    "rent": "span.monthly-rent",
    "bedrooms": "span.beds",
    "bathrooms": "span.baths",
    "sqft": "span.square-feet",
    "pets_policy": "p.pet-policy",
    "amenities": "ul.amenities",
    "photos": "img.gallery-image",
    "description": "div.listing-description"
  },
  "pre_extraction_actions": [
    "click button.expand-full-description",
    "wait 500"
  ],
  "notes": "Site uses dynamic content loading. Amenities in comma-separated list under 'Amenities' heading. Photos load lazily; scroll gallery to end.",
  "api_recipe": {
    "method": "GET",
    "url_template": "https://acme-pm.example.com/api/listings/{listing_id}",
    "headers": {
      "Accept": "application/json"
    },
    "body_template": null,
    "response_root": "$.listing",
    "field_paths": {
      "address": "$.address",
      "rent": "$.monthlyRent",
      "bedrooms": "$.bedrooms",
      "bathrooms": "$.bathrooms",
      "sqft": "$.squareFeet",
      "pets_policy": "$.petPolicy"
    },
    "extractable_fields": ["address", "rent", "bedrooms", "bathrooms", "sqft"],
    "captured_at": "2026-05-01T10:15:00Z",
    "captured_from_listing_id": "ACM-12345",
    "last_validated_at": "2026-05-01T10:15:00Z",
    "last_failure_at": null,
    "failure_count": 0,
    "confidence": "high",
    "capture_notes": "API response always includes all fields for the requested listing_id. Status code 404 if listing not found or delisted."
  }
}
```
