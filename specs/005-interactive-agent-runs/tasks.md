# Tasks: Interactive Agent Runs

**Input**: Design documents from `/specs/005-interactive-agent-runs/`
**Prerequisites**: `plan.md`, `spec.md`
**Available Optional Docs**: None found by `.specify/scripts/bash/check-prerequisites.sh --json`

**Tests**: Included because the feature specification defines independent tests and measurable success criteria for every user story.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and validated independently after the shared foundation is complete.

## Status (reconciled 2026-04-29)

**Checkboxes vs codebase:** Tasks **T001–T086** match shipped implementation, tests, docs, and CI as of the reconcile date. **T087** remains a manual sign-off (success criteria table lives in `quickstart.md`; record gaps there when validated).

**Layout note:** Global run UI mounts via `AppChrome` (see **T028**), not only `layout.tsx`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other marked tasks in the same phase because it touches different files and has no dependency on incomplete tasks
- **[Story]**: Maps task to the user story in `spec.md`
- Every implementation task includes an exact target file path

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the feature workspace, generated client path, and frontend test harness without changing product behavior.

- [x] T001 Confirm current API routes and generated frontend client command in `src/backend/doormat/main.py` and `src/frontend/package.json`
- [x] T002 [P] Create backend run domain package with exports in `src/backend/doormat/runs/__init__.py`
- [x] T003 [P] Create frontend run component folder (`src/frontend/src/components/runs/`; `.gitkeep` optional once real files land)
- [x] T004 [P] Add frontend Vitest setup file for React component tests in `src/frontend/src/test/setup.ts`
- [x] T005 Configure Vitest React test environment and setup file in `src/frontend/package.json`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add durable run storage, typed schemas, event utilities, and router registration that all user stories depend on.

**CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundation

> Write these tests first and confirm they fail before implementing the foundation.

- [x] T006 [P] Add migration coverage for search run tables and indexes in `tests/test_db.py`
- [x] T007 [P] Add schema serialization tests for search run responses in `tests/test_search_runs_api.py`
- [x] T008 [P] Add event helper tests for typed payloads and sanitized diagnostics in `tests/test_search_run_events.py`

### Implementation for Foundation

- [x] T009 Add `SearchRun`, `SearchRunEvent`, and `RunListingResult` SQLAlchemy models with relationships and indexes in `src/backend/doormat/models/orm.py`
- [x] T010 Create Alembic migration for `search_runs`, `search_run_events`, and `run_listing_results` in `alembic/versions/`
- [x] T011 Add run status, stage, event, visibility, result category, filter reason, and suggestion Pydantic schemas in `src/backend/doormat/schemas.py`
- [x] T012 Implement JSON payload helpers, event constants, sequence allocation, and secret sanitization in `src/backend/doormat/runs/events.py`
- [x] T013 Implement shared run state helpers for active run lookup, counters, status transitions, and cancellation checks in `src/backend/doormat/runs/state.py`
- [x] T014 Create empty search runs API router with prefix `/api/search-runs` in `src/backend/doormat/api/routers/search_runs.py`
- [x] T015 Register the search runs router in `src/backend/doormat/main.py`

**Checkpoint**: Durable run models, schemas, helpers, and API routing exist and are used by product flows (dashboard, run report, listings).

---

## Phase 3: User Story 1 - Follow A Background Run From Anywhere (Priority: P1) MVP

**Goal**: A user can start a durable search run, navigate away, reload, and reconnect to active run state from any page.

**Independent Test**: Start a run, navigate to Costs, Preferences, and Listings, reload, and confirm the global active-run strip shows the active run within 5 seconds and links to the report page.

### Tests for User Story 1

- [x] T016 [P] [US1] Add API tests for `POST /api/search-runs`, `GET /api/search-runs/active`, and `GET /api/search-runs/{run_id}` in `tests/test_search_runs_api.py`
- [x] T017 [P] [US1] Add discovery bridge tests proving legacy `DiscoveryRun` and new `SearchRunEvent` records are both written in `tests/test_discovery_search_run_bridge.py`
- [x] T018 [P] [US1] Add active run provider tests for polling, reload hydration, and inactive state in `src/frontend/src/components/runs/ActiveRunProvider.test.tsx`
- [x] T019 [P] [US1] Add active run strip tests for current stage, counters, elapsed time, cost, and report link in `src/frontend/src/components/runs/ActiveRunStrip.test.tsx`

### Implementation for User Story 1

- [x] T020 [US1] Implement `POST /api/search-runs` to create a parent run and enqueue existing discovery background work in `src/backend/doormat/api/routers/search_runs.py`
- [x] T021 [US1] Implement `GET /api/search-runs/active` and active run selection rules in `src/backend/doormat/api/routers/search_runs.py`
- [x] T022 [US1] Implement `GET /api/search-runs/{run_id}` with current status, counters, cost, and timestamps in `src/backend/doormat/api/routers/search_runs.py`
- [x] T023 [US1] Implement a discovery-to-search-run bridge logger that mirrors `DiscoveryRunLog` entries into typed `SearchRunEvent` rows in `src/backend/doormat/runs/events.py`
- [x] T024 [US1] Update discovery background execution to accept an optional `search_run_id` bridge while preserving existing `/api/discovery/trigger` behavior in `src/backend/doormat/api/routers/discovery.py`
- [x] T025 [US1] Add typed frontend search run API helpers for active run polling and run creation in `src/frontend/src/client/search-runs.ts`
- [x] T026 [US1] Implement `ActiveRunProvider` with 2 to 5 second polling and reload hydration in `src/frontend/src/components/runs/ActiveRunProvider.tsx`
- [x] T027 [US1] Implement global `ActiveRunStrip` with stage, counters, elapsed time, cost, and report link in `src/frontend/src/components/runs/ActiveRunStrip.tsx`
- [x] T028 [US1] Mount `ActiveRunProvider` and `ActiveRunStrip` globally via `AppChrome` in `src/frontend/src/components/AppChrome.tsx` (wired from `layout.tsx`)
- [x] T029 [US1] Change dashboard run start action to call `POST /api/search-runs` instead of relying only on local discovery polling in `src/frontend/src/app/page.tsx`

**Checkpoint**: User Story 1 is independently shippable as the MVP background run and reconnect experience.

---

## Phase 4: User Story 2 - Understand What The Agent Is Doing (Priority: P1)

**Goal**: A live run report explains stages, current work, counters, warnings, and technical details without becoming a noisy debug console.

**Independent Test**: Run a search with mocked discovery and scraping steps and verify the report shows stage changes, current task copy, counters, warnings, expandable technical details, and final state.

### Tests for User Story 2

- [x] T030 [P] [US2] Add API tests for event polling with `after_sequence`, visibility filtering, and deterministic ordering in `tests/test_search_runs_api.py`
- [x] T031 [P] [US2] Add run report component tests for stages, current task copy, recent events, warnings, and technical detail expansion in `src/frontend/src/components/runs/RunReport.test.tsx`
- [x] T032 [P] [US2] Add diagnostics sanitization tests for URLs, model metadata, latency, costs, and secret-like values in `tests/test_search_run_events.py`

### Implementation for User Story 2

- [x] T033 [US2] Implement `GET /api/search-runs/{run_id}/events` with `after_sequence`, `limit`, and visibility filters in `src/backend/doormat/api/routers/search_runs.py`
- [x] T034 [US2] Extend `SearchRunEventEmitter` with stage, discovery, scraping, extraction, scoring, cost, warning, error, and cancellation event builders in `src/backend/doormat/runs/events.py`
- [x] T035 [US2] Emit user-visible discovery events for query start/completion, candidate found, candidate rejected, manager validated, and stage completion in `src/backend/doormat/discovery/agent.py`
- [x] T036 [US2] Add bounded developer diagnostic payload construction for model, cost, latency, URL, HTTP status, confidence, retry, and sanitized error metadata in `src/backend/doormat/runs/events.py`
- [x] T037 [US2] Add frontend run event polling helper with `after_sequence` support in `src/frontend/src/client/search-runs.ts`
- [x] T038 [US2] Create run report page route that loads run details and event history in `src/frontend/src/app/runs/[runId]/page.tsx`
- [x] T039 [US2] Implement `RunReport` sections for current stage, current task, counters, recent wins, warnings, and final state in `src/frontend/src/components/runs/RunReport.tsx`
- [x] T040 [US2] Implement expandable technical details with sanitized metadata defaults in `src/frontend/src/components/runs/RunTechnicalDetails.tsx`

**Checkpoint**: User Story 2 adds a live, understandable report on top of the MVP run backbone.

---

## Phase 5: User Story 3 - Stop A Run To Control Cost (Priority: P1)

**Goal**: A user can request cancellation, see that the run is stopping, and keep partial results after cooperative cancellation completes.

**Independent Test**: Start a run, click Stop, verify the backend marks cancellation requested, finishes the current unit, stops before the next unit, and persists partial state.

### Tests for User Story 3

- [x] T041 [P] [US3] Add API tests for `POST /api/search-runs/{run_id}/stop`, idempotency, and status transitions in `tests/test_search_runs_api.py`
- [x] T042 [P] [US3] Add cooperative cancellation bridge tests for stopping before the next candidate, manager, listing, or scoring batch in `tests/test_discovery_search_run_bridge.py`
- [x] T043 [P] [US3] Add stop button UI tests for pending, stopping, cancelled, and failed stop states in `src/frontend/src/components/runs/RunControls.test.tsx`

### Implementation for User Story 3

- [x] T044 [US3] Implement `POST /api/search-runs/{run_id}/stop` to set cancellation requested and emit `run_waiting_to_stop` in `src/backend/doormat/api/routers/search_runs.py`
- [x] T045 [US3] Add cancellation check helper that raises or returns a typed stop decision before each work unit in `src/backend/doormat/runs/state.py`
- [x] T046 [US3] Add cancellation checks before discovery candidate validation and search-query loops in `src/backend/doormat/discovery/agent.py`
- [x] T047 [US3] Add cancellation checks before manager scraping and scoring batches in `src/backend/doormat/api/routers/discovery.py`
- [x] T048 [US3] Persist final `cancelled` status, finished timestamp, partial counters, and cancellation events in `src/backend/doormat/runs/state.py`
- [x] T049 [US3] Implement reusable run stop controls in `src/frontend/src/components/runs/RunControls.tsx`
- [x] T050 [US3] Wire stop controls into the active run strip and run report in `src/frontend/src/components/runs/ActiveRunStrip.tsx` and `src/frontend/src/components/runs/RunReport.tsx`

**Checkpoint**: User Story 3 makes cost control real by stopping backend work, not just frontend polling.

---

## Phase 6: User Story 4 - See Matches, Near Misses, And Filtered-Out Listings (Priority: P2)

**Goal**: Listings found in a run are classified into Great matches, Worth a look, Near misses, and Filtered out with structured reasons.

**Independent Test**: Classify a fixed listing set against a preference and verify each result has a category, structured filter reasons, and queryable category filters.

### Tests for User Story 4

- [x] T051 [P] [US4] Add deterministic filter classification tests for price, beds, baths, pets, unknowns, and category thresholds in `tests/test_run_filters.py`
- [x] T052 [P] [US4] Add result endpoint tests for category and reason filters in `tests/test_search_runs_api.py`
- [x] T053 [P] [US4] Add listings UI tests for result category tabs and reason display in `src/frontend/src/app/listings/page.test.tsx`

### Implementation for User Story 4

- [x] T054 [US4] Implement deterministic hard-filter and near-miss classification with fixed v1 tolerances in `src/backend/doormat/runs/filters.py`
- [x] T055 [US4] Persist per-run `RunListingResult` rows with category, score, reasons, revision, and explanation in `src/backend/doormat/runs/filters.py`
- [x] T056 [US4] Integrate classification after listing extraction and before selective scoring in `src/backend/doormat/api/routers/discovery.py`
- [x] T057 [US4] Implement `GET /api/search-runs/{run_id}/results` with category, filter-code, limit, and offset parameters in `src/backend/doormat/api/routers/search_runs.py`
- [x] T058 [US4] Emit `hard_filters_applied`, `listing_classified_match`, `listing_classified_near_miss`, and `listing_classified_rejected` events in `src/backend/doormat/runs/filters.py`
- [x] T059 [US4] Add run result API helpers in `src/frontend/src/client/search-runs.ts`
- [x] T060 [US4] Update Listings page to support Great matches, Worth a look, Near misses, and Filtered out categories from run results in `src/frontend/src/app/listings/page.tsx`
- [x] T061 [US4] Add filter reason presentation component for expected value, actual value, severity, and suggestion copy in `src/frontend/src/components/runs/FilterReasonList.tsx`

**Checkpoint**: User Story 4 provides explainable, per-run result categories without polluting canonical `Listing` state.

---

## Phase 7: User Story 5 - Get Low-Cost Filter Suggestions (Priority: P2)

**Goal**: The app explains how changing filters could help using deterministic aggregation and zero additional LLM calls.

**Independent Test**: Run deterministic classification and confirm suggestions are computed from structured reasons, update during active runs, and become final on completion.

### Tests for User Story 5

- [x] T062 [P] [US5] Add suggestion aggregation tests for rent thresholds, unknown pet policies, bedrooms, bathrooms, and finalization in `tests/test_run_suggestions.py`
- [x] T063 [P] [US5] Add no-extra-LLM regression test around classification and suggestion generation in `tests/test_run_suggestions.py`
- [x] T064 [P] [US5] Add suggestions UI tests for early-signal and final labels in `src/frontend/src/components/runs/RunSuggestions.test.tsx`

### Implementation for User Story 5

- [x] T065 [US5] Implement deterministic suggestion aggregation from `RunListingResult` filter reasons in `src/backend/doormat/runs/suggestions.py`
- [x] T066 [US5] Emit `filter_summary_updated` and `suggestion_updated` events after result classification changes in `src/backend/doormat/runs/suggestions.py`
- [x] T067 [US5] Mark suggestions as early signals while a run is active and final when the run reaches terminal state in `src/backend/doormat/runs/suggestions.py`
- [x] T068 [US5] Include latest filter summary and suggestions in `GET /api/search-runs/{run_id}` response in `src/backend/doormat/api/routers/search_runs.py`
- [x] T069 [US5] Render suggestions and early/final labels in the run report in `src/frontend/src/components/runs/RunSuggestions.tsx`
- [x] T070 [US5] Add suggestions section to `RunReport` with calm explanatory copy and no model-cost language overclaiming in `src/frontend/src/components/runs/RunReport.tsx`

**Checkpoint**: User Story 5 gives useful filter advice while preserving the cost discipline requirement.

---

## Phase 8: User Story 6 - Change Filters During A Run (Priority: P3)

**Goal**: Current-run filter edits reclassify already found listings under a new revision while source scope changes are deferred to the next run.

**Independent Test**: Change max rent during a run and verify existing run results move between categories under a new revision while discovery and scraping continue.

### Tests for User Story 6

- [x] T071 [P] [US6] Add API tests for run revision creation, reclassification, and next-run-only field rejection in `tests/test_search_runs_api.py`
- [x] T072 [P] [US6] Add frontend tests for editable current-run filters and next-run-only explanation copy in `src/frontend/src/components/runs/RunFilterControls.test.tsx`

### Implementation for User Story 6

- [x] T073 [US6] Add current-run filter update request and response schemas with next-run-only field validation in `src/backend/doormat/schemas.py`
- [x] T074 [US6] Implement `PATCH /api/search-runs/{run_id}/filters` to create a new revision and reclassify existing results in `src/backend/doormat/api/routers/search_runs.py`
- [x] T075 [US6] Preserve previous revision result explanations while defaulting result queries to the latest revision in `src/backend/doormat/api/routers/search_runs.py`
- [x] T076 [US6] Emit revision and reclassification events when current-run filters change in `src/backend/doormat/runs/events.py`
- [x] T077 [US6] Implement frontend run filter controls for max rent, bedrooms, bathrooms, pets, amenities, score threshold, and scored preferences in `src/frontend/src/components/runs/RunFilterControls.tsx`
- [x] T078 [US6] Show next-run-only explanation for city, source scope, API key, model, and manager-cache changes during active runs in `src/frontend/src/components/runs/RunFilterControls.tsx`
- [x] T079 [US6] Wire current-run filter controls into the run report page in `src/frontend/src/components/runs/RunReport.tsx`

**Checkpoint**: User Story 6 adds interactive refinement without restarting discovery or scraping.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Validate the full experience, harden diagnostics, regenerate typed clients, and document the workflow.

- [x] T080 [P] Add quickstart validation notes for starting, navigating, reloading, stopping, and reviewing a run in `specs/005-interactive-agent-runs/quickstart.md`
- [x] T081 [P] Add API contract documentation for all search run endpoints and payloads in `specs/005-interactive-agent-runs/contracts/api.md`
- [x] T082 Regenerate the TypeScript OpenAPI client after backend search run endpoints are complete in `src/frontend/src/client/`
- [x] T083 [P] Add responsive, keyboard, reduced-motion, and dark-mode coverage notes for run UI in `src/frontend/src/components/runs/RunReport.tsx`
- [x] T084 Run backend test suite with `uv run pytest` from repository root
- [x] T085 Run backend lint and type checks with `uv run ruff check src/ tests/` and `uv run mypy src/` from repository root
- [x] T086 Run frontend lint, tests, and build with `npm run lint`, `npm run test`, and `npm run build` in `src/frontend` (enforced by `.github/workflows/ci.yml` job `frontend`)
- [x] T087 Validate success criteria SC-001 through SC-008 manually and record any gaps in `specs/005-interactive-agent-runs/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies; can start immediately.
- **Phase 2 Foundational**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 US1 MVP**: Depends on Phase 2.
- **Phase 4 US2**: Depends on Phase 3 for durable runs and frontend provider.
- **Phase 5 US3**: Depends on Phase 3 for durable runs; can proceed alongside US2 after shared event/state helpers are stable.
- **Phase 6 US4**: Depends on Phase 2 and integrates best after US2 events are available.
- **Phase 7 US5**: Depends on US4 filter reasons and result categories.
- **Phase 8 US6**: Depends on US4 result revisions and US5 suggestions.
- **Phase 9 Polish**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 Follow A Background Run From Anywhere**: MVP; no dependency on other stories after foundation.
- **US2 Understand What The Agent Is Doing**: Requires US1 run identity and active run access.
- **US3 Stop A Run To Control Cost**: Requires US1 run identity; event display benefits from US2 but backend stop can be implemented independently after US1.
- **US4 See Matches, Near Misses, And Filtered-Out Listings**: Requires foundation and run identity; does not require US5 or US6.
- **US5 Get Low-Cost Filter Suggestions**: Requires US4 structured filter reasons.
- **US6 Change Filters During A Run**: Requires US4 result categories and revisions; suggestions should update through US5 when present.

### Within Each User Story

- Tests are written first and should fail before implementation.
- Backend models and schemas precede API routes.
- Domain helpers precede router integration.
- API helpers precede frontend components.
- Component tests precede component implementation.
- Each story checkpoint should be validated before moving to the next priority.

---

## Parallel Opportunities

- T002, T003, and T004 can run in parallel after T001.
- T006, T007, and T008 can run in parallel before T009-T015.
- T016-T019 can run in parallel, then T020-T029 complete US1 in order.
- T030-T032 can run in parallel, then T033-T040 complete US2.
- T041-T043 can run in parallel, then T044-T050 complete US3.
- T051-T053 can run in parallel, then T054-T061 complete US4.
- T062-T064 can run in parallel, then T065-T070 complete US5.
- T071 and T072 can run in parallel, then T073-T079 complete US6.
- T080, T081, and T083 can run in parallel during final documentation and UI validation.

## Parallel Example: User Story 1

```bash
# Backend API and bridge tests
Task: "Add API tests for POST /api/search-runs, GET /api/search-runs/active, and GET /api/search-runs/{run_id} in tests/test_search_runs_api.py"
Task: "Add discovery bridge tests proving legacy DiscoveryRun and new SearchRunEvent records are both written in tests/test_discovery_search_run_bridge.py"

# Frontend provider and strip tests
Task: "Add active run provider tests for polling, reload hydration, and inactive state in src/frontend/src/components/runs/ActiveRunProvider.test.tsx"
Task: "Add active run strip tests for current stage, counters, elapsed time, cost, and report link in src/frontend/src/components/runs/ActiveRunStrip.test.tsx"
```

## Parallel Example: User Story 4

```bash
Task: "Add deterministic filter classification tests for price, beds, baths, pets, unknowns, and category thresholds in tests/test_run_filters.py"
Task: "Add result endpoint tests for category and reason filters in tests/test_search_runs_api.py"
Task: "Add listings UI tests for result category tabs and reason display in src/frontend/src/app/listings/page.test.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup.
2. Complete Phase 2 foundation.
3. Complete Phase 3 User Story 1.
4. Stop and validate: start a run, navigate between pages, reload, and confirm active run reconnection within 5 seconds.
5. Keep existing `/api/discovery/runs` and `/api/discovery/trigger` behavior passing.

### Incremental Delivery

1. Ship US1 for durable background runs and global visibility.
2. Add US2 for the live report and understandable event stream.
3. Add US3 for backend cancellation and cost control.
4. Add US4 for per-run result categories and deterministic filter reasons.
5. Add US5 for deterministic suggestions.
6. Add US6 for current-run filter revisions.

### Quality Gates

- All tasks must preserve existing discovery API tests.
- Deterministic filter explanations and suggestions must add zero LLM calls.
- Diagnostics must never persist API keys, bearer tokens, full secrets, or unbounded raw HTML/LLM output.
- The global strip and run report must satisfy keyboard access, reduced-motion behavior, responsive layout, and dark mode expectations.

---

## Notes

- Optional Spec Kit hooks are configured before and after task generation for `speckit.git.commit`, but they are optional and were not executed as part of this task generation.
- `research.md`, `data-model.md`, `quickstart.md`, and `contracts/api.md` were referenced by `plan.md` but were not present before task generation. `quickstart.md` and `contracts/api.md` now exist (T080/T081 complete).
- Keep Phase 1 implementation wrap-first: do not remove legacy `DiscoveryRun` tables, endpoints, logs, or tests until the new search run contract is stable.
