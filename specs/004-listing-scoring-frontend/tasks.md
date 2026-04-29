# Tasks: Listing scoring, API endpoints, and frontend UI

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Legend: `[ ]` pending · `[x]` done

---

## Phase 1 — Backend scoring & API foundations

- [ ] **1.1** Create `scoring/schemas.py`: `ScoringResult`, `ScoringRequest`, `ScorerConfig` Pydantic models.
- [ ] **1.2** Implement `scoring/scorer.py`: `ListingScorer` class with LLM + heuristic fallback, prompt templates in `prompt_registry`, cost tracking.
- [ ] **1.3** Create `scoring/heuristics.py`: budget, bedroom, city, pet-friendly matching logic for fallback.
- [ ] **1.4** Add unit tests for scorer (LLM success, LLM failure → heuristic, output validation) in `tests/unit/test_scorer.py`.
- [ ] **1.5** Extend `models/orm.py`: add `saved` (bool), `score` (float 0–1), `scoring_reason` (text) to `Listing` ORM model.
- [ ] **1.6** Alembic migration: add columns to `listings` table (allow null initially).

---

## Phase 2 — Preference model & preferences API

- [ ] **2.1** Extend `Preference` ORM model: `api_provider`, `openrouter_api_key`, `apify_api_token` fields.
- [ ] **2.2** Alembic migration: add API fields to `preferences` table; encrypt keys at-rest if applicable (document assumption).
- [ ] **2.3** Create `schemas/preferences.py`: `PreferenceResponse`, `PreferenceCreate`, `PreferenceUpdate` with masked key fields for response.
- [ ] **2.4** Implement `api/routes/preferences.py`:
  - `GET /api/preferences` — retrieve stored preference (omit keys in response except metadata).
  - `POST /api/preferences` — create/update preference.
  - `PATCH /api/preferences` — partial update (API keys only).
- [ ] **2.5** Add integration tests for preferences CRUD in `tests/integration/test_preferences_api.py`.

---

## Phase 3 — Listings API (paginated + save + SSE stream)

- [ ] **3.1** Implement `api/routes/listings.py`:
  - `GET /api/listings` — paginated list with query filters (`min_price`, `max_price`, `bedrooms`, `saved`, `limit`, `offset`).
  - `GET /api/listings/{id}` — single listing detail (must be defined before stream route to avoid shadowing).
  - `POST /api/listings/{id}/save` — toggle saved flag.
  - `POST /api/listings/score` — batch score all listings against stored preference.
  - `GET /api/listings/stream` — SSE stream (emit events on new/updated listings).
- [ ] **3.2** Create `api/sse.py`: `ListingStreamManager` for managing SSE connections and event emission.
- [ ] **3.3** Implement pagination helper in `api/utils.py` (offset/limit, next_page token).
- [ ] **3.4** Add filter validation and ORM query building for listings filters.
- [ ] **3.5** Integration tests for all endpoints (list, detail, save, score, stream) in `tests/integration/test_listings_api.py`.

---

## Phase 4 — Batch scoring & cost tracking integration

- [ ] **4.1** Implement `POST /api/listings/score` handler:
  - Load stored preference (or reject if missing).
  - Call `ListingScorer.score_batch()` for all listings (or paginated if >1000).
  - Persist scores/reasons to DB via ORM.
  - Return summary (total scored, count > 0.7, cost_usd).
- [ ] **4.2** Wire cost tracking: each scorer call emits cost event (via `cost_tracking.py`).
- [ ] **4.3** Add integration test: score 100 listings and verify costs recorded.

---

## Phase 5 — Frontend: Listings page

- [ ] **5.1** Create `frontend/app/(dashboard)/listings/page.tsx`: main listings grid layout.
- [ ] **5.2** Build `frontend/components/ListingCard.tsx`: display address, bedrooms, price, score badge, save button.
- [ ] **5.3** Implement filter bar component: budget range, bedrooms, saved toggle (client-side state mgmt via React state + @hey-api client).
- [ ] **5.4** Wire client to `GET /api/listings` with filters and pagination (infinite scroll or "Load More").
- [ ] **5.5** Implement save/unsave toggle via `POST /api/listings/{id}/save`.
- [ ] **5.6** Responsive design: verify mobile layout (cards stack, filters collapse into dropdown).
- [ ] **5.7** Add dark mode support via Tailwind `dark:` utilities.
- [ ] **5.8** Component tests for ListingCard, filter bar in `frontend/__tests__/`.

---

## Phase 6 — Frontend: Preferences page

- [ ] **6.1** Create `frontend/app/(dashboard)/preferences/page.tsx`: preference form layout.
- [ ] **6.2** Build form component: budget (number), bedrooms (number), walkable (checkbox), pet-friendly (checkbox), neighborhood (text/select).
- [ ] **6.3** Add API key input fields (masked input with show/hide toggle).
- [ ] **6.4** Implement form submission: `POST /api/preferences` or `PATCH` for API keys.
- [ ] **6.5** Add toast notifications for success/error states.
- [ ] **6.6** Pre-fill form with existing preference on load via `GET /api/preferences`.
- [ ] **6.7** Responsive design: form should work on mobile (single-column layout).
- [ ] **6.8** Component tests in `frontend/__tests__/`.

---

## Phase 7 — UI polish & integration

- [ ] **7.1** Create or update Header component: navigation links, dark mode toggle, cost dashboard link.
- [ ] **7.2** Create or update Footer component: links, version/build info.
- [ ] **7.3** Verify routing: `/listings` and `/preferences` resolve correctly from layout.
- [ ] **7.4** End-to-end test: full user flow (enter preferences → view listings → save items → see updated scores).
- [ ] **7.5** Dark mode verification: both themes render correctly and persist via localStorage.
- [ ] **7.6** Accessibility audit: WCAG 2.1 AA (keyboard nav, color contrast, semantic HTML).

---

## Phase 8 — Error handling, edge cases & final testing

- [ ] **8.1** Test LLM scorer failure paths: invalid key, timeout, malformed response → verify fallback activates.
- [ ] **8.2** Test API key not leaked in logs: enable debug logging, score listings, grep logs for keys (must be absent).
- [ ] **8.3** Test empty listings list: verify UI shows empty state message.
- [ ] **8.4** Test preference missing before scoring: API returns 400 with guidance to set preferences.
- [ ] **8.5** Test SSE reconnection: close stream, verify UI reconnects automatically.
- [ ] **8.6** Test rate limiting on `/api/listings/score`: send >100 listings, verify 429 response.
- [ ] **8.7** Run full pytest suite: `uv run pytest` all 79 tests pass.
- [ ] **8.8** Lint + type check: `uv run ruff check` and `uv run mypy src/` pass without errors.

---

## Phase 9 — Documentation & deployment

- [ ] **9.1** Add endpoint documentation in `CLAUDE.md` or API docs (auto-generated from OpenAPI).
- [ ] **9.2** Update README with Phase 4 summary (scoring, listing browsing, preferences UI).
- [ ] **9.3** Document cost tracking output in COST-GUIDE.md snippet.
- [ ] **9.4** Tag phase with commit: `git tag phase-4-complete` (optional, defer to deployment).

---

## Dependency order

Phase order: **1 → 2 → 3 → 4** (backend ready), then **5 ∥ 6** (frontend parallel), then **7 → 8 → 9**.

**Minimum viable slice to prove value**: **1.1–1.6 + 2.1–2.5 + 3.1–3.5 + 4.1–4.3** (backend complete, manual API testing), then **5 + 6** (UI can browse & set prefs), then **8 + 9** (testing & docs).

## Notes

- All Alembic migrations should use `render_as_batch=True` for SQLite compatibility (convention in this repo).
- SSE stream route must be defined **before** `/{id}` in router to avoid shadowing (critical for FastAPI routing).
- Cost tracking should emit events for every scorer call (even heuristic fallback counts as 0 LLM cost).
- Dark mode toggle state should persist in browser localStorage (avoid flash of wrong theme).
- API key fields should be encrypted at-rest if possible; document if not implemented (e.g., "Keys stored plaintext in SQLite; use HTTPS or VPN for network access").
