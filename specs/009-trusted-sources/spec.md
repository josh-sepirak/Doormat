# Feature Specification: Trusted sources & Craigslist region picker

**Feature Branch**: `009-trusted-sources`  
**Created**: 2026-05-01  
**Status**: Implemented  
**Input**: Per-install trusted listing sources (Craigslist regions + property manager URLs) with geocoded CL region suggestions to avoid wrong-city subdomains.

## Problem

1. Craigslist routing uses a small hardcoded map and naive fallback (`lancaster` → Lancaster, PA), so cities like Lancaster, CA hit the wrong regional site.
2. Users cannot pin specific Craigslist regions or local PM listing pages; discovery-only flow is insufficient for “sites I trust.”

## User Scenarios & Testing

### User Story 1 — Pick the correct Craigslist region (P1)

As a searcher, I want to confirm which Craigslist regional site covers my city after I enter city + state, so listings come from the right metro.

**Independent Test**: `GET /api/craigslist/regions?city=Lancaster&state=CA` returns Inland Empire among top suggestions with distance.

**Acceptance**:

1. **Given** city + state, **When** regions API runs, **Then** response includes `geocoded` coordinates and `suggestions` with subdomain, label, url, distance_mi.
2. **Given** a pasted `https://inlandempire.craigslist.org` URL, **When** parse endpoint runs, **Then** valid subdomain and label are returned.

---

### User Story 2 — Trusted sources library (P1)

As a self-hoster, I want a global list of trusted Craigslist regions and PM sites that every run uses, without re-entering per preference.

**Independent Test**: Add trusted CL region for city X; run scrape; listings use that subdomain.

**Acceptance**:

1. **Given** a saved `craigslist_region` trusted source for a city, **When** scraping runs with Craigslist enabled, **Then** fetch uses that region (or all matching regions), not only naive subdomain.
2. **Given** no trusted region for the city, **When** scraping runs, **Then** legacy auto-map runs and a warning event is emitted.

---

### User Story 3 — Trusted property managers (P1)

As a user, I want to paste a PM listings URL so it is scraped like discovered managers.

**Independent Test**: POST trusted `property_manager` creates `TrustedSource` + validated `PropertyManager` for the city; PM direct scrape includes it.

---

## Functional Requirements

1. Bundled `craigslist_regions.json` with subdomains and representative lat/lon for distance ranking.
2. `TrustedSource` ORM + Alembic migration (`kind`, `label`, `url`, optional `city`, `metadata_json`).
3. REST: `GET/POST/DELETE` trusted-sources; `POST .../test`; CL regions `GET` + `POST /parse`.
4. Pipeline: `_scrape_craigslist` prefers trusted CL regions for matching city; dedupe by listing URL across regions.
5. Frontend: `/sources` page, modals, preferences nudge when Craigslist on without trusted region for city.

## Non-Goals

- Cross-install / community sharing of trusted sources.
- Bulk CSV import.
- In-place edit of trusted rows (delete + recreate in v1).

## Success Criteria

- SC-001: Lancaster, CA flow surfaces Inland Empire in top 3 suggestions after geocode.
- SC-002: User-added trusted PM URL appears in next scrape run for that city.
- SC-003: Preferences with only legacy `sources_enabled` behave as before when no trusted CL rows exist.

## References

- [src/backend/doormat/sources/craigslist.py](../../src/backend/doormat/sources/craigslist.py)
- [src/backend/doormat/runs/pipeline.py](../../src/backend/doormat/runs/pipeline.py)
