# Feature Specification: Interactive Agent Runs

**Feature Branch**: `005-interactive-agent-runs`  
**Created**: 2026-04-26  
**Status**: Draft  
**Input**: User wants discovery, scraping, filtering, and listing agents to be more interactive and communicative so the frontend can show what is happening, why filters are failing, whether anything is being found, how filter changes could help, and which listings are near misses.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Follow A Background Run From Anywhere (Priority: P1)

As a renter running Doormat, I want a search run to continue in the background after I leave the dashboard, so I can check Costs, Preferences, or Listings without losing visibility or stopping progress.

**Why this priority**: The current experience feels stuck because the user must remain on the originating page and the frontend only knows local polling state.

**Independent Test**: Start a run, navigate to Costs, Preferences, and Listings, then confirm a global run status remains visible and links back to the run report.

**Acceptance Scenarios**:

1. **Given** no active run, **When** the user starts a search, **Then** the backend creates a durable run and the frontend shows a global active-run strip.
2. **Given** a run is active, **When** the user leaves the dashboard, **Then** the run continues and the global status strip still shows current stage, counters, elapsed time, and cost so far.
3. **Given** the user reloads the browser, **When** the app starts, **Then** it reconnects to the active run from the backend rather than relying on local component state.

---

### User Story 2 - Understand What The Agent Is Doing (Priority: P1)

As a user watching a run, I want a live report that explains each stage and counts progress upward, so I can tell the agent is still moving and where it is currently focused.

**Why this priority**: Trust depends on visible progress. A spinner or summary count is not enough for agentic discovery and scraping.

**Independent Test**: Run a search with mocked discovery and scraping steps and verify the run report shows stage changes, current task messages, counters, warnings, and final state.

**Acceptance Scenarios**:

1. **Given** discovery is running, **When** candidates are found, deduped, validated, or rejected, **Then** the run report shows user-readable events and updated counts.
2. **Given** scraping is running, **When** a manager is checked or listings are seen, **Then** the report shows the current manager, listings seen, extracted count, and failures where relevant.
3. **Given** a stage has technical diagnostics, **When** the user expands technical details, **Then** the UI reveals model, cost, latency, URL, confidence, and error metadata without exposing secrets.

---

### User Story 3 - Stop A Run To Control Cost (Priority: P1)

As a cost-conscious self-hosted user, I want to stop an active run, so I can avoid spending more money while keeping everything already found.

**Why this priority**: Cost discipline is a core product promise and the existing "stop polling" behavior does not stop backend work.

**Independent Test**: Start a run, click Stop, verify the backend marks cancellation requested, completes the current unit, stops before the next unit, and persists partial results.

**Acceptance Scenarios**:

1. **Given** a run is active, **When** the user clicks Stop run, **Then** the run enters `cancel_requested` and the UI says it is stopping after the current unit.
2. **Given** cancellation is requested, **When** the current manager, listing, or scoring batch finishes, **Then** the run exits as `cancelled`.
3. **Given** a run was cancelled, **When** the user opens its report, **Then** partial listings, near misses, events, costs, and diagnostics remain visible.

---

### User Story 4 - See Matches, Near Misses, And Filtered-Out Listings (Priority: P2)

As a user reviewing results, I want listings grouped into Great matches, Worth a look, Near misses, and Filtered out, so I can decide whether my filters are too strict and inspect borderline options.

**Why this priority**: The user explicitly wants near misses and filter failure reasons, but the canonical listing table should not be overloaded with run-specific evaluation state.

**Independent Test**: Classify a fixed set of listings against a preference and verify each result has a category, structured filter reasons, and queryable category filters.

**Acceptance Scenarios**:

1. **Given** a listing passes hard filters with a high score, **When** it is evaluated, **Then** it appears as a Great match.
2. **Given** a listing passes hard filters with a medium score, **When** it is evaluated, **Then** it appears as Worth a look.
3. **Given** a listing misses one hard filter by a small deterministic tolerance, **When** it is evaluated, **Then** it appears as a Near miss with the reason and suggested relaxation.
4. **Given** a listing clearly fails hard filters, **When** it is evaluated, **Then** it appears as Filtered out, hidden from primary results but available for review.

---

### User Story 5 - Get Low-Cost Filter Suggestions (Priority: P2)

As a user, I want the app to explain how changing filters could help, so I can make informed changes without paying the LLM to reason over every rejected listing.

**Why this priority**: Filter advice is central to the feature, and it must preserve Doormat's under-$1/month cost goal.

**Independent Test**: Run deterministic classification on listings and confirm suggestions are computed from structured reasons without an LLM call.

**Acceptance Scenarios**:

1. **Given** several listings are over max rent by a small amount, **When** suggestions are generated, **Then** the system says how many listings would be added by raising the budget to a computed threshold.
2. **Given** several listings have unknown pet policies, **When** suggestions are generated, **Then** the system suggests reviewing unknown pet policies rather than assuming they fail.
3. **Given** a run is still active, **When** suggestions change, **Then** they are marked as early signals until the run completes.

---

### User Story 6 - Change Filters During A Run (Priority: P3)

As a user, I want filter edits to reclassify already found listings without restarting discovery or scraping, so I can see immediate feedback while the current source work continues.

**Why this priority**: This improves interactivity while avoiding duplicate discovery and scraping cost.

**Independent Test**: Change max rent during a run and verify existing run results move between categories under a new run revision while discovery and scraping continue.

**Acceptance Scenarios**:

1. **Given** a run is active, **When** the user changes max rent, bedrooms, bathrooms, pet requirement, amenities, score threshold, or scored preferences, **Then** existing listings are reclassified under a new run revision.
2. **Given** the user changes city, source scope, API key, or model, **When** a run is active, **Then** the UI explains the change will apply to the next run.
3. **Given** a run has multiple revisions, **When** the report shows current results, **Then** it defaults to the latest revision while preserving earlier explanations for traceability.

### Edge Cases

- A run is active when the frontend reloads or opens in a second tab.
- The user clicks Stop while an LLM, browser, or HTTP fetch is in progress.
- Discovery finds candidates but none validate as property managers.
- Scraping finds managers but no listings.
- Extraction sees a listing but cannot identify enough canonical data to persist it.
- A listing has unknown pet policy, missing bedrooms, missing bathrooms, or ambiguous address.
- Cost tracking data arrives after the related stage event.
- A filter edit changes current-run fields while a stage is mid-loop.
- The user has no OpenRouter key or the selected model does not support structured output.
- Developer diagnostics contain large HTML, LLM response text, or secret-like values.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST create a durable parent `SearchRun` for user-initiated discovery/scrape/filter/score workflows.
- **FR-002**: System MUST wrap the existing `DiscoveryRun` flow in Phase 1 rather than replacing it immediately.
- **FR-003**: System MUST persist typed run events with a human-readable message and structured payload.
- **FR-004**: System MUST expose an active-run polling API that any frontend page can call after navigation or reload.
- **FR-005**: Users MUST be able to stop an active run through a backend cancellation endpoint.
- **FR-006**: System MUST implement cooperative cancellation by checking the run cancel flag before starting each candidate, manager, listing, or scoring batch.
- **FR-007**: System MUST keep partial results, costs, and events after cancellation.
- **FR-008**: Frontend MUST show a global active-run status strip across Dashboard, Listings, Preferences, and Costs.
- **FR-009**: Frontend MUST provide a dedicated run report page for live progress, counters, recent events, suggestions, and technical details.
- **FR-010**: Run updates in v1 MUST use polling with durable event history. SSE can be added later without changing the persistence contract.
- **FR-011**: System MUST support user-visible event types for discovery, scraping, extraction, filtering, scoring, costs, warnings, errors, and cancellation.
- **FR-012**: System MUST capture developer diagnostics for prompt version, model/provider, tokens, cost, latency, URL/domain, HTTP status, extraction confidence, missing fields, classifier reason, retry attempt, and sanitized errors.
- **FR-013**: Developer diagnostics MUST never persist API keys, bearer tokens, full secrets, or unbounded raw HTML/LLM output.
- **FR-014**: System MUST classify run listings into `great_match`, `worth_a_look`, `near_miss`, or `filtered_out`.
- **FR-015**: System MUST store per-run listing evaluation in a separate `RunListingResult` entity rather than only on `Listing`.
- **FR-016**: System MUST persist rejected-but-valid listings as canonical listings when enough data exists to revisit them.
- **FR-017**: System MUST keep low-quality extraction failures as diagnostics/events instead of normal listing rows.
- **FR-018**: System MUST store structured filter failure reasons with expected value, actual value, severity, and computed suggestion where applicable.
- **FR-019**: Hard filter explanations and near-miss classification MUST be deterministic and not require an LLM call.
- **FR-020**: System MUST use fixed near-miss tolerances for v1, including rent within 10 percent or $200, bedrooms short by 1, bathrooms short by 0.5, and unknown pet policy as near miss when pets are required.
- **FR-021**: System MUST generate filter suggestions from aggregated deterministic miss reasons.
- **FR-022**: Suggestions during active runs MUST be labeled as early signals until the run completes.
- **FR-023**: Preference extraction SHOULD split natural-language preferences into hard filters, scored preferences, and dealbreakers with user confirmation before they drive explanations.
- **FR-024**: LLM scoring MUST be limited to listings that pass deterministic gates or are plausible near misses.
- **FR-025**: Soft scoring SHOULD batch listings in small groups to control overhead while preserving response quality.
- **FR-026**: The normal UI MUST show lightweight technical detail, with full diagnostics available through a dedicated debug API or view.

### User-Visible Event Types

- `run_started`
- `preferences_loaded`
- `filters_interpreted`
- `stage_started`
- `stage_progress`
- `stage_completed`
- `search_query_started`
- `search_query_completed`
- `candidate_found`
- `candidate_deduped`
- `candidate_check_started`
- `candidate_rejected`
- `manager_validated`
- `manager_skipped`
- `listing_page_found`
- `listing_page_fetch_started`
- `listing_page_fetch_completed`
- `listing_page_fetch_failed`
- `scrape_started`
- `listing_seen`
- `listing_duplicate_skipped`
- `extraction_started`
- `extraction_mode_a_started`
- `extraction_mode_a_failed`
- `extraction_mode_b_started`
- `strategy_updated`
- `listing_extracted`
- `listing_rejected_low_confidence`
- `hard_filters_applied`
- `listing_classified_match`
- `listing_classified_near_miss`
- `listing_classified_rejected`
- `scoring_batch_started`
- `listing_scored`
- `filter_summary_updated`
- `suggestion_updated`
- `cost_updated`
- `run_waiting_to_stop`
- `cancel_requested`
- `cancelled`
- `warning`
- `error`
- `run_completed`

### Key Entities *(include if feature involves data)*

- **SearchRun**: Parent user-visible run that tracks city, preference, status, current stage, active revision, counters, cost so far, timestamps, and cancellation state.
- **SearchRunEvent**: Durable typed event attached to a run. Contains event type, stage, message, payload, visibility, sequence, and timestamp.
- **RunListingResult**: Per-run and per-revision evaluation of a canonical listing, including category, score, filter reasons, matched preferences, missed preferences, and explanation.
- **FilterReason**: Structured reason a listing missed or nearly missed a filter. Includes filter code, label, expected value, actual value, severity, and computed suggestion.
- **RunSuggestion**: Computed suggestion derived from aggregated filter reasons, such as raising max rent or reviewing unknown pet policies.
- **DeveloperDiagnostic**: Structured technical detail associated with a run event or operation, stored safely for debugging and prompt improvement.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: User can start a run, navigate to at least three different app pages, reload, and still see the active run status within 5 seconds.
- **SC-002**: Clicking Stop prevents any new manager, listing, or scoring batch from starting after the current unit finishes.
- **SC-003**: The run report shows at least five live-updating counters: sources checked, managers validated, listings seen, matches, near misses, and filtered out.
- **SC-004**: At least 95 percent of non-main listing classifications include one or more structured filter reasons or an extraction confidence reason.
- **SC-005**: Deterministic filter explanations and suggestions add zero LLM calls compared to the current scoring flow.
- **SC-006**: Developer diagnostics include model, cost, latency, operation type, and sanitized error context for every LLM-backed discovery, extraction, or scoring operation.
- **SC-007**: The global run strip and run report meet WCAG AA contrast and keyboard accessibility expectations.
- **SC-008**: Phase 1 can be shipped while existing `DiscoveryRun` endpoints and tests continue to pass.

## Assumptions

- Doormat remains single-user and self-hosted.
- Polling every 2 to 5 seconds is sufficient for v1.
- Existing discovery logging can be mirrored into `SearchRunEvent` during the wrap-first phase.
- Near-miss tolerances are fixed in v1 and not exposed as settings.
- Neighborhood preferences are scored/current-run filters in v1 unless a future feature adds neighborhood-targeted source discovery.
- City changes, source-scope changes, API key changes, model changes, and manager-cache resets apply to the next run, not the currently active discovery/scrape scope.
- `DESIGN.md` is currently absent; UI implementation should follow `PRODUCT.md`, Tailwind styles already in the app, and Impeccable product-register guidance.
