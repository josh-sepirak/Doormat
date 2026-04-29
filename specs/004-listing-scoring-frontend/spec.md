# Feature Specification: Listing scoring, API endpoints, and frontend UI

**Feature Branch**: `004-listing-scoring-frontend`  
**Created**: 2026-04-29  
**Status**: Draft  
**Input**: Deliver core scoring engine, REST API tier, and responsive Next.js UI for viewing listings and managing preferences.

## Problem

Users have extracted listings but no way to view, score, or filter them. Backend lacks structured API for programmatic access. Frontend doesn't exist. Phase 4 delivers end-to-end scoring + UI foundation.

## User Scenarios & Testing

### User Story 1 — Score and view listings (Priority: P1)

As a user, I want to enter my rental preferences (budget, bedrooms, walkability, pet-friendly), then see a ranked list of matching listings with scores and reasoning, so I can quickly identify good options.

**Why this priority**: Core value proposition — turning extracted data into ranked, actionable matches.

**Independent Test**: Given a preference profile and 100 cached listings, run `/api/listings/score` and verify top-3 results include at least one match (score > 0.7) with reasoning field populated.

**Acceptance Scenarios**:

1. **Given** a user with budget $3200, walkable, 2-bed preference, **When** listings are scored, **Then** listings matching all three criteria rank in top 5 with scores > 0.85.
2. **Given** LLM scorer fails (API key invalid/down), **When** scoring runs, **Then** heuristic fallback activates (budget/bedroom/city signals) without API key leaks in logs.
3. **Given** preferences with valid OpenRouter key, **When** `/api/listings/score` runs, **Then** cost is recorded and visible in `/metrics`.

---

### User Story 2 — Browse and save listings (Priority: P1)

As a user, I want to browse all extracted listings with filtering (price range, bedroom count, saved/bookmarked), so I can explore options and build a shortlist.

**Why this priority**: Basic CRUD and discovery UX before refinement loops.

**Independent Test**: GET `/api/listings?min_price=2000&max_price=3500&bedrooms=2` returns only matching listings; verify pagination works at 100+ results.

**Acceptance Scenarios**:

1. **Given** 500 listings in the database, **When** I request page 1 with 20 results per page, **Then** I get exactly 20 results and `next_page` token is present.
2. **Given** a listing I want to watch, **When** I POST `/api/listings/{id}/save`, **Then** the listing is marked saved and subsequent GETs include a `saved: true` flag.
3. **Given** saved=true filter, **When** I GET `/api/listings?saved=true`, **Then** only saved listings are returned.

---

### User Story 3 — Manage preferences and API keys (Priority: P1)

As a user, I want to save my rental preferences (bedrooms, budget, walkability, pets) in the UI and configure my OpenRouter API key, so I can persist settings and enable scoring.

**Why this priority**: User-facing configuration required for scoring and cost tracking.

**Independent Test**: Preferences saved via frontend POST to `/api/preferences` persist across browser reloads and appear in `GET /api/preferences`.

**Acceptance Scenarios**:

1. **Given** the Preferences page, **When** I enter budget $3200, walkable neighborhood, 2 bedrooms, and click Save, **Then** preferences persist and are returned by the API.
2. **Given** preferences with no API key, **When** scoring attempts, **Then** fallback heuristic is used and a UI warning prompts for key.
3. **Given** a valid OpenRouter API key entered, **When** preferences are saved, **Then** the key is stored securely and not echoed back to the frontend in unmasked form.

---

### User Story 4 — Real-time listing stream (Priority: P2)

As a user, I want to see listings update in real-time as the background scraper runs, using a server-sent events (SSE) stream, so I can monitor progress and see new matches without polling.

**Why this priority**: Quality-of-life for active users watching a search run.

**Independent Test**: Open `/api/listings/stream`, simulate a scrape job adding 10 listings, and verify SSE events are received within 1 second.

**Acceptance Scenarios**:

1. **Given** a browser with `/api/listings/stream` open, **When** a background scrape completes and new listings are extracted, **Then** SSE events are emitted with listing ID, address, and score (if available).
2. **Given** the SSE stream active, **When** I navigate away and return, **Then** reconnection re-establishes the stream without data loss.

---

## Functional Requirements

1. **Scoring Engine** (`ListingScorer`):
   - LLM-based scoring (0–1 scale) using OpenRouter with preference context.
   - Heuristic fallback (budget, bedroom, city, pet signals) when LLM unavailable.
   - Structured output with reasoning field for each score.
   - Injection-safe prompts framing listing data as `UNTRUSTED LISTING DATA`.

2. **Listing API** (5 endpoints):
   - `GET /api/listings` — paginated list with filters (price, bedrooms, saved).
   - `GET /api/listings/stream` — SSE stream of listing events (new, updated, scored).
   - `GET /api/listings/{id}` — single listing detail.
   - `POST /api/listings/{id}/save` — toggle saved flag.
   - `POST /api/listings/score` — batch score all listings against preference.

3. **Preferences API** (CRUD):
   - `GET /api/preferences` — retrieve stored preference.
   - `POST /api/preferences` — create/update preference with budget, bedrooms, walkability, pet-friendly, neighborhood signals.
   - `PATCH /api/preferences` — partial update (API keys only; preference body separate).
   - Schema extension: `api_provider` (enum: "openrouter"), `openrouter_api_key`, `apify_api_token` fields added to `Preference` model.

4. **Frontend UI** (Next.js 15, Tailwind):
   - `/listings` page: grid layout with score badge, price, bedrooms, address, save button.
   - `/preferences` page: form for budget/rooms/walkability + API key input fields.
   - Header: navigation, dark mode toggle, cost dashboard link.
   - Footer: links, version info.
   - Responsive design (mobile-first).

5. **Database Schema**:
   - `Preference` model extended: `api_provider`, `openrouter_api_key` (encrypted), `apify_api_token` (encrypted).
   - Two Alembic migrations: (1) add API fields to `preferences` table, (2) add `saved` and `score` columns to `listings` table.

6. **Error Handling**:
   - LLM scorer failures degrade gracefully to heuristic; API key not leaked in logs.
   - Invalid preference data returns 422 with schema errors.
   - Rate limiting on scoring endpoints (max 100 listings per minute).

## Success Criteria

- SC-1: All 79 pytest tests pass (unit + integration).
- SC-2: `GET /api/listings` returns paginated list with all filter combinations working.
- SC-3: `POST /api/listings/score` scores all listings and stores results in DB without data corruption.
- SC-4: Frontend `/listings` renders and can save/unsave items without API errors.
- SC-5: Frontend `/preferences` persists and retrieves settings correctly.
- SC-6: Cost tracking shows per-call cost for scorer (visible in logs, `/metrics`, future dashboard).
- SC-7: SSE stream is not shadowed by `GET /api/listings/{id}` route (routing order correct).
- SC-8: Heuristic fallback activates without exception when LLM key absent or invalid.

## Non-Goals

- Real-time browser-based searching (deferred to Phase 5).
- Advanced filtering UI (faceted search, saved searches).
- Exporting listings (CSV, email digest).

## References

- PR #4: https://github.com/josh-sepirak/Doormat/pull/4
- `src/backend/doormat/scoring/` (scorer implementation)
- `src/backend/doormat/api/` (endpoint implementations)
- `frontend/app/(dashboard)/listings/` (UI components)

## Out of Scope

- Changing extraction pipeline (listing data already available).
- Multi-user preference sharing.
- Preference templates or "popular" defaults.
