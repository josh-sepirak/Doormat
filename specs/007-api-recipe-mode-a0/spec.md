# Feature Specification: API recipe + Mode A0 fast path

**Feature Branch**: `007-api-recipe-mode-a0`  
**Created**: 2026-04-29  
**Status**: Draft  
**Input**: Add an HTTP-recipe tier so listing extraction can use captured JSON XHR responses (Mode A0 ~$0) before HTML Mode A and agentic Mode B. Full reference: `docs/patches/01-api-recipe-patch.md`.

## Problem

Mode A (HTML + LLM) and Mode B (browser + LLM) are correct but expensive at scale. Many property manager sites load listing detail from **same-origin JSON** APIs. If we capture and validate those recipes, repeat extractions avoid both LLM HTML parsing and Browser-Use for that source.

## User Scenarios & Testing

### User Story 1 — Lower cost, same results (Priority: P1)

As a self-hoster running Doormat continuously, I want extraction to use **cheap HTTP replay** when a source exposes a stable JSON API, so my monthly OpenRouter spend drops without changing match quality.

**Why this priority**: Direct cost and reliability for the highest-volume operation (per-listing extract).

**Independent Test**: With `api_recipe_enabled` on and a promoted recipe on a test source, scrape N listings and assert cost metrics show Mode A0 hits and no regression in stored listing fields vs baseline Mode A.

**Acceptance Scenarios**:

1. **Given** a validated `ApiRecipe` on a strategy, **When** a listing URL is extracted, **Then** Mode A0 runs first and returns a structured listing without LLM when the recipe succeeds.
2. **Given** Mode A0 fails (HTTP 4xx, parse error, field mismatch), **When** extraction continues, **Then** the pipeline falls through to existing Mode A then Mode B unchanged.
3. **Given** `api_recipe_enabled=False`, **When** any listing is extracted, **Then** behavior matches pre-feature (no Mode A0).

---

### User Story 2 — Safe promotion (Priority: P1)

As an operator, I want recipes **validated** (held-out or self-replay per policy) before merge, so a bad capture does not poison production strategies.

**Why this priority**: Incorrect recipes could silently corrupt listing data.

**Independent Test**: Unit tests for `RecipeValidator` and merge gate; rejected recipes logged or stored for audit.

**Acceptance Scenarios**:

1. **Given** a proposed recipe that fails replay against held-out samples, **When** `StrategyCache.merge` runs, **Then** selectors still merge but recipe is not promoted (or is rejected per spec).
2. **Given** session-bound APIs (401/403 on replay), **When** validation runs, **Then** recipe is not promoted.

---

### User Story 3 — Observability (Priority: P2)

As an operator, I want metrics or cost breakdowns to show **Mode A0 / A / B** volumes, so I can verify savings.

**Why this priority**: Proves ROI and supports rollout flags.

**Independent Test**: Logs or `/costs` (or metrics) expose counters added in patch step 11.

---

## Functional Requirements

1. **Schema**: `ApiRecipe`, optional `api_recipe` on `StrategyUpdate`; persistence compatible with existing `ExtractionStrategy` / `strategy_json` (see plan).
2. **Capture**: Best-effort JSON response buffering during Mode B (CDP or Playwright fallback per `network_capture.py` design).
3. **Synthesis**: After Mode B, infer URL template, response root, and field paths; only GET by default for POST safety.
4. **Mode A0**: Pure `httpx` execution; align types with `ExtractedListing` (`rent` not `price` in this codebase).
5. **Merge gate**: Validate recipe before committing; feature flags in `config.py`.
6. **Migration**: Alembic under `alembic/versions/` (not `migrations/`).

## Non-Goals

- Scraping sites with no JSON API (unchanged).
- Bypassing auth or Cloudflare-only APIs (graceful fallback only).

## References

- `docs/patches/01-api-recipe-patch.md` (steps 1–11)
- `src/backend/doormat/extraction/orchestrator.py` (wiring point)
- `src/backend/doormat/extraction/strategy.py` (merge gate)

## Out of Scope

- Changing discovery or search-run UX (backend extraction only unless metrics surface in UI later).
