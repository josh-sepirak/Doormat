# Plan: Trusted sources & Craigslist region picker

## Architecture

- **Static data**: `doormat/data/craigslist_regions.json` loaded via `importlib.resources`; `craigslist_regions.py` exposes `nearest_regions(lat, lon, k)`.
- **Persistence**: `trusted_sources` table; `property_manager` kind creates sibling `PropertyManager` (`validated=True`) for existing PM scrape path.
- **API**: `trusted_sources` router (`/api/trusted-sources`), `craigslist_regions` router (`/api/craigslist/regions`, `/api/craigslist/regions/parse`).
- **Geocoding**: Extend `nominatim.py` with forward geocode for arbitrary query (city + state) reusing User-Agent and optional cache.
- **Pipeline**: Query trusted `craigslist_region` rows where `city` matches run city (case-insensitive); call `fetch_craigslist_listings(..., subdomain=...)` per region; else fallback + warning event.

## Security

- Validate URLs (https only, allowed hosts for CL parse).
- HEAD/GET probe with bounded timeout; no SSRF to internal networks beyond normal outbound HTTP policy.

## Testing

- Unit: haversine / nearest regions with small fixture subset.
- API: mocked Nominatim; trusted CRUD with test DB.
- Pipeline: async test with mocked `fetch_craigslist_listings` or in-memory session.
