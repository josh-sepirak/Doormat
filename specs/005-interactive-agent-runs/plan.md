# Implementation Plan: Interactive Agent Runs

**Branch**: `005-interactive-agent-runs` | **Date**: 2026-04-26 | **Spec**: `specs/005-interactive-agent-runs/spec.md`  
**Input**: Feature specification from `specs/005-interactive-agent-runs/spec.md`

## Summary

Create a hybrid background run system that gives Doormat one durable parent run for discovery, scraping, filtering, scoring, near misses, and diagnostics. Phase 1 wraps the existing `DiscoveryRun` flow instead of replacing it. The frontend gains a global active-run strip, a dedicated run report page, and polling-based reconnection so users can leave the dashboard while the run continues.

## Technical Context

**Language/Version**: Python 3.13 backend, TypeScript/React with Next.js 15 frontend  
**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, structlog, httpx, Next.js App Router, Tailwind  
**Storage**: SQLite with SQLAlchemy and Alembic migrations  
**Testing**: pytest for backend, frontend component/API behavior tests where existing setup supports them  
**Target Platform**: Local self-hosted web application  
**Project Type**: Web application with FastAPI backend and Next.js frontend  
**Performance Goals**: Polling reconnect within 5 seconds; page navigation must not interrupt backend runs; deterministic filter classification should be cheap enough for all persisted listings in a run  
**Constraints**: Preserve cost discipline, avoid unnecessary LLM calls, keep existing discovery tests working, do not expose secrets in diagnostics  
**Scale/Scope**: Single-user local deployment, one active run is the expected v1 case

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Cost Discipline**: Pass. Deterministic filter reasons, near-miss classification, and suggestions add no model calls. LLM scoring remains selective.
- **Self-Contained & Single-User**: Pass. Durable run state lives in local DB and assumes single-user operation.
- **Autonomous Agent Excellence**: Pass. Agent steps remain structured and validated, with improved visibility.
- **Production-Grade Prompt Engineering**: Pass. Diagnostics capture prompt/model/version data for prompt improvement without storing secrets.
- **End-to-End Type Safety**: Pass. New API schemas will be Pydantic models and frontend consumers should use typed interfaces or generated client.
- **Observability First**: Pass. This feature directly upgrades user-visible and developer-visible observability.
- **Simplicity Over Frameworks**: Pass. Polling-first and wrap-first avoids introducing a queue or realtime framework in v1.

## Project Structure

### Documentation (this feature)

```text
specs/005-interactive-agent-runs/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── api.md
```

### Source Code (repository root)

```text
src/backend/doormat/
├── api/routers/
│   ├── discovery.py              # Wrap existing DiscoveryRun flow during Phase 1
│   └── search_runs.py            # New run lifecycle API
├── models/
│   └── orm.py                    # SearchRun, SearchRunEvent, RunListingResult
├── schemas.py                    # Pydantic request/response schemas
├── runs/
│   ├── events.py                 # Typed event emitter and payload helpers
│   ├── filters.py                # Deterministic hard-filter and near-miss logic
│   └── suggestions.py            # Aggregated suggestion generation
└── scoring/
    └── scorer.py                 # Selective scoring integration

src/frontend/src/
├── app/
│   ├── layout.tsx                # Global provider/strip mount
│   └── runs/[runId]/page.tsx     # Dedicated run report page
├── components/
│   ├── ActiveRunProvider.tsx
│   ├── ActiveRunStrip.tsx
│   └── RunReport.tsx
└── client/
    └── search-runs.ts            # API helpers until generated client covers them

tests/
├── test_search_runs_api.py
├── test_run_filters.py
└── test_discovery_search_run_bridge.py
```

**Structure Decision**: Add a `runs` backend module for the new domain logic while keeping current discovery, extraction, and scoring modules intact. This preserves the wrap-first approach and keeps the run API separate from legacy discovery endpoints.

## Phase 0 Research

Research conclusions are captured in `research.md`.

Key decisions:

- Use polling-first with durable event history for v1.
- Model one parent `SearchRun` with typed child events and per-run listing results.
- Wrap current `DiscoveryRun` first, then migrate internals later.
- Generate hard-filter reasons, near misses, and suggestions deterministically.
- Use cooperative cancellation rather than forcibly killing in-flight calls.
- Use a dedicated run report page plus global status strip for UX.

## Phase 1 Design

### Data Model

See `data-model.md`.

Implementation adds:

- `SearchRun`
- `SearchRunEvent`
- `RunListingResult`

Later phases may add `DeveloperDiagnostic` or `RunSuggestion` as separate tables if event payloads become too large or hard to query. V1 can store suggestions and diagnostics as typed JSON payloads on events, provided payloads are bounded and sanitized.

### API Contracts

See `contracts/api.md`.

New endpoints:

- `POST /api/search-runs`
- `GET /api/search-runs/active`
- `GET /api/search-runs/{run_id}`
- `GET /api/search-runs/{run_id}/events`
- `POST /api/search-runs/{run_id}/stop`
- `GET /api/search-runs/{run_id}/results`

### UI Contract

The frontend uses a shared active-run provider that polls `GET /api/search-runs/active`. When a run is active, it renders a compact strip in the app layout. The run report page polls run details and events by run ID.

Visual direction:

- Warm, capable, quiet.
- Live research-report feel, not a debug console by default.
- Restrained color, slate surfaces, blue accent, no neon or heavy dashboard chrome.
- Live counters animate upward only as state changes, with motion kept purposeful and brief.

## Phase 2 Task Plan

### Phase 1: Run Backbone And Minimal UI

**Goal**: Solve the page-navigation and cancellation pain while preserving current discovery behavior.

- Add Alembic migration for `search_runs`, `search_run_events`, and initial indexes.
- Add SQLAlchemy models and Pydantic schemas.
- Add `SearchRunEventEmitter` helper with typed event constants.
- Add `POST /api/search-runs` to create a parent run and start the existing discovery flow in the background.
- Add a bridge logger that writes both existing `DiscoveryRunLog` entries and new `SearchRunEvent` entries.
- Add `GET /api/search-runs/active`, `GET /api/search-runs/{run_id}`, and event polling.
- Add `POST /api/search-runs/{run_id}/stop` and cooperative cancellation checks between discovery units.
- Add frontend `ActiveRunProvider`.
- Add global `ActiveRunStrip`.
- Add minimal `/runs/[runId]` page with current stage, counters, events, cost so far, and stop action.
- Add tests for run creation, active run retrieval, stop state, and discovery bridge events.

### Phase 2: Background Scrape And Extraction Events

**Goal**: Turn scraping from a synchronous summary into a background stage with visible progress.

- Add scrape stage events for manager fetch, listing page fetch, listing seen, extraction start, Mode A result, Mode B fallback, strategy update, and low-confidence rejection.
- Check cancellation before each manager and listing.
- Persist rejected-but-valid listings as canonical `Listing` rows.
- Keep low-quality extraction junk as events/diagnostics only.
- Update run counters for listings seen, extracted, low-confidence rejected, and cost.

### Phase 3: Filter Results And Near Misses

**Goal**: Represent per-run outcomes without polluting canonical listing data.

- Add `run_listing_results` table and model.
- Implement deterministic hard-filter evaluation.
- Implement fixed near-miss tolerances.
- Add result categories: `great_match`, `worth_a_look`, `near_miss`, `filtered_out`.
- Store structured filter reasons per result.
- Add result query endpoint with category and reason filters.
- Update Listings UI to filter by result category.

### Phase 4: Suggestions

**Goal**: Explain how filter changes could help without model calls.

- Aggregate filter reasons per run revision.
- Emit `filter_summary_updated` and `suggestion_updated` events.
- Show suggestions during active runs as early signals.
- Mark suggestions final when run completes.

### Phase 5: Polished Run Report

**Goal**: Make the run report feel like a calm live research report.

- Add sectioned progress for sources, managers, scraping, filters, scoring, and suggestions.
- Add animated count-up counters.
- Add current-task copy, recent wins, and warnings.
- Add expandable technical details.
- Add a dedicated debug API or debug section for full diagnostics.
- Validate responsive behavior, keyboard access, reduced-motion behavior, and dark mode.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Parent run plus legacy discovery run during Phase 1 | Needed for wrap-first migration | Replacing `DiscoveryRun` immediately risks breaking existing tests and behavior |
| Per-run listing result table | Needed for revisions, near misses, and filter history | Storing categories only on `Listing` loses run-specific context and breaks reclassification |

## Risks And Mitigations

| Risk | Mitigation |
|------|------------|
| Run system duplicates discovery logging | Use a bridge logger in Phase 1 and deprecate legacy logs only after the new contract is stable |
| Event payloads grow too large | Bound payload sizes, summarize raw content, and move full diagnostics to a separate table if needed |
| UI becomes noisy | Use calm default report sections and keep technical detail expandable |
| Cancellation feels slow | Show `run_waiting_to_stop` immediately, then stop cooperatively after the current unit |
| LLM cost increases | Keep filter reasons and suggestions deterministic; score only gated listings and plausible near misses |
| Diagnostics leak secrets | Central sanitizer before persistence, tests with secret-like values |

## Implementation Notes

- Phase 1 must not remove existing `/api/discovery/runs` behavior.
- Existing dashboard discovery can migrate to `POST /api/search-runs` after the search run API is tested.
- Search run statuses should include `queued`, `running`, `cancel_requested`, `cancelled`, `success`, and `error`.
- User-facing labels should be `Great matches`, `Worth a look`, `Near misses`, and `Filtered out`; internal enum values can remain snake_case.
- City, source scope, model, API key, and manager-cache changes are next-run-only while a run is active.
- Max rent, min bedrooms/bathrooms, pet requirement, amenities, scored preferences, and thresholds can reclassify the current run under a new revision.

## Post-Design Constitution Check

- **Cost Discipline**: Still pass. The plan explicitly avoids new LLM calls for explanations and suggestions.
- **Observability First**: Still pass. User-visible events and developer diagnostics are first-class.
- **Simplicity Over Frameworks**: Still pass. No queue or SSE dependency in v1.
- **Type Safety**: Still pass if schemas are added before frontend consumption.
- **Prompt Versioning**: Still pass if diagnostics include prompt/version where LLM-backed steps occur.
