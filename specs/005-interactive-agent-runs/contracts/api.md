# Search runs API contract

Base path: `/api/search-runs` (JSON). Auth: `POST` and `PATCH` use the same optional bearer dependency as discovery when `AUTH_BEARER_TOKEN` is set.

## `POST /api/search-runs`

**Body:** `{ "city": string (2–100 chars), "preference_id"?: string | null }`

**Response:** `SearchRunResponse` — includes `id`, `discovery_run_id`, `city`, `status`, `current_stage`, counters (`sources_checked`, `managers_validated`, `listings_seen`, category counts), `cost_usd_so_far`, `active_revision`, `started_at`, `finished_at`, `filter_summary`, `suggestions`, `suggestions_early_signal`, `cancel_requested`.

**Effect:** Creates `DiscoveryRun` + `SearchRun`, appends `run_started`, schedules background discovery with `search_run_id` bridge.

---

## `GET /api/search-runs/active`

**Response:** `{ "active": boolean, "run": SearchRunResponse | null }` — newest non-terminal run by `started_at`, statuses `queued` \| `running` \| `cancel_requested`.

---

## `GET /api/search-runs/{run_id}`

**Response:** `SearchRunResponse` for any run id (including terminal).

---

## `GET /api/search-runs/{run_id}/events`

**Query:** `after_sequence` (default `-1` = from start), `limit` (1–500), `visibility` optional filter `user` \| `developer`.

**Response:** `SearchRunEventOut[]` ordered by `sequence` ascending.

---

## `POST /api/search-runs/{run_id}/stop`

**Response:** `SearchRunResponse`. Idempotent for terminal runs and for repeat cancel requests.

**Effect:** Sets cancel flags, emits `run_waiting_to_stop` and `cancel_requested` events; discovery/scrape loops honor cooperative cancel.

---

## `GET /api/search-runs/{run_id}/results`

**Query:** `category` optional (`great_match`, `worth_a_look`, `near_miss`, `filtered_out`), `revision` optional (defaults to run’s `active_revision`), `limit`, `offset`.

**Response:** `RunListingResultOut[]` — `listing_id`, `category`, `score`, `filter_reasons_json` (JSON array of structured reasons), `explanation`, `revision`.

---

## `PATCH /api/search-runs/{run_id}/filters`

**Body (JSON):** Partial `SearchRunFiltersPatch` — `max_price`, `min_bedrooms`, `min_bathrooms`, `pets_required`, `score_great_threshold`, `score_worth_threshold`. Extra keys ignored. `next_run_city` and `next_run_change_openrouter_key` are rejected with 422.

**Response:** Updated `SearchRunResponse` after reclassification pass.

**Effect:** Merges into `filters_json`, increments `active_revision`, emits progress + classification events.

---

## Typed client

Generated SDK lives under `src/frontend/src/client/` (`sdk.gen.ts`, `types.gen.ts`, …). Thin wrappers for polling and `after_sequence` remain in `src/frontend/src/client/search-runs.ts`.
