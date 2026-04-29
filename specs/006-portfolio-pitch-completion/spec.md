# Feature Specification: Portfolio Pitch Completion

**Feature Branch**: `006-portfolio-pitch-completion`
**Created**: 2026-04-26
**Status**: Blocked — waiting on parallel agent's "Listings table, maps, and editable LLM prompts" plan to merge
**Input**: User wants a gap analysis between Doormat's current state and the original BUILD-GUIDE / PRODUCT plan, framed for a portfolio submitted to AI engineering hiring managers. Plan should identify what is missing, what is excess, and which gaps are worth closing before submission.

## Context *(meta-feature, not a product feature)*

This specification is a **portfolio readiness plan**, not a product feature. It exists because:

1. The interview pitch in BUILD-GUIDE.md §15 makes specific technical claims a recruiter can verify by reading the repo.
2. Several pitch claims are not yet implemented in code (embedding pre-filter, prompt caching, eval harness, FastMCP integration).
3. The project has shipped substantial work *beyond* the original plan (Phase 5: interactive agent runs with durable events, mid-run filter editing, suggestion engine, cooperative cancellation) that the README does not yet credit.
4. The candidate has finite time before submission and needs a prioritized backlog rather than a comprehensive one.

The "users" in this spec are the candidate (engineer building Doormat) and a future hiring manager (engineer reading Doormat). Each user story below corresponds to one missing-but-claimed capability that, when built, makes the existing pitch defensible.

## Coordination With Parallel Work *(important — read first)*

A separate AI agent is concurrently implementing **`Listings table, maps, and editable LLM prompts`** (saved at `~/.cursor/plans/Listings and Prompts UX-bd28e386.plan.md`). To avoid merge conflicts and duplicated infrastructure, this spec is scoped to **complement, not overlap** that work. The split:

| Owned by parallel agent (DO NOT TOUCH from this spec) | Owned by this spec |
|---|---|
| `src/frontend/src/app/listings/page.tsx` (table view, view toggle, photo column, filters) | Run report page (`/runs/[runId]`) is unchanged |
| `src/frontend/src/app/preferences/page.tsx` (Prompts accordion section) | Cost dashboard (`/costs`) gets new `cache_hit_rate` and `embedding` lines (US2/US1) |
| `src/backend/doormat/api/routers/listings.py` (serialization fix for `source`, filter wiring for `min_bathrooms`/`max_bathrooms`/`pets_policy`) | New router `src/backend/doormat/api/routers/mcp.py` is *not* needed — MCP server is its own console-script process (US3) |
| `src/backend/doormat/api/routers/preferences.py` (`GET/PATCH /preferences/{id}/prompts`) | No new preferences endpoints from this spec |
| New module `src/backend/doormat/llm/prompt_registry.py` (default prompts + `get_effective_prompt`) | This spec **consumes** that registry; it does not introduce its own per-module `PROMPT_VERSION` constants |
| `Preference.prompt_overrides` column (Text/JSON, nullable) | New `Preference.embedding` and `Listing.embedding` vector columns (US1) — separate migration |
| `Listing.latitude` / `Listing.longitude` columns + geocode cache | No location columns from this spec |
| `next.config.ts` image patterns / Leaflet+OSM tiles | No frontend mapping work |

**Hard rules for this spec's implementer:**

1. Wait for the parallel agent's `prompt_registry` PR to land before starting US4. If they have not landed it by US4 start time, ship US4 anyway but as a stub that imports `from doormat.llm.prompt_registry import PromptKey` lazily — the test will skip rather than fail.
2. The Alembic migration for embedding columns (US1) must be a **separate revision** from any migration the parallel agent ships. Both revisions can coexist on the same branch tree; resolve linearly during merge.
3. The parallel agent's plan does not cover **prompt versioning metadata** (a `version: str` field on each registered prompt). US4 below adds that field to the registry, but only as an additive change — no behavioral coupling.
4. If the parallel agent ships first, US4 collapses from "build registry + add versioning + add evals" to just "add versioning + add evals." That is fine and reduces this spec's scope.

---

## Current State Inventory

### Implemented (matches plan)
- **Discovery agent** (`src/backend/doormat/discovery/`) — Browser-Use orchestration, candidate validation, strategy generation
- **Two-mode listing extraction** (`src/backend/doormat/extraction/`) — Mode A deterministic + Mode B agentic + feedback loop
- **Soft-preference scoring** (`src/backend/doormat/scoring/scorer.py`) — LLM scoring with explanations
- **Source adapters** — `craigslist.py`, `apify.py` (Zillow, Facebook Marketplace)
- **Tiered model routing + cost tracking** — `cost_tracking.py` differentiates Tier 1/Tier 2 spend
- **Cost dashboard** — `/costs` page with summary, by-component, by-model, timeseries
- **OpenRouter integration** — `openai` SDK with model picker
- **End-to-end type safety** — FastAPI → OpenAPI → `@hey-api/openapi-ts` typed client
- **Dark mode + responsive UI** (`src/frontend/src/app/`)
- **Playwright E2E suite** — 38 tests across 5 spec files (`src/frontend/e2e/`)
- **Alembic migrations + SQLite + WAL**
- **structlog observability + Prometheus `/metrics`**

### Implemented beyond plan (Phase 5 — not in BUILD-GUIDE)
- **Durable SearchRun model** with 40+ user-visible event types
- **RunListingResult** per-revision classification (`great_match`, `worth_a_look`, `near_miss`, `filtered_out`)
- **Cooperative run cancellation** with mid-stage flag checks
- **Mid-run filter editing** — reclassify without re-scraping
- **Deterministic filter-suggestion engine** — aggregates miss reasons without LLM calls
- **Active-run status strip** — global UI persistence across page navigation
- **Run report page** (`/runs/[runId]`) — live progress + technical diagnostics

### Claimed in pitch but not implemented (the gap)
- **Embedding pre-filter** — `sqlite-vec` is not installed; no embedding generation; no vector search before LLM scoring
- **Prompt caching** — no `cache_control: ephemeral` headers on any LLM call
- **FastMCP server** — no `mcp/` module, no `fastmcp` dependency, no console-script entry
- **Eval harness with versioned prompts** — no `evals/` directory, no prompt-version metadata, no regression assertions

### Planned but appropriately deferred (out of scope for portfolio)
See "Out of Scope" section below.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recruiter Verifies The Embedding Pre-Filter Claim (Priority: P1)

As a hiring manager reading the BUILD-GUIDE pitch ("embedding pre-filter — all visible in the live cost dashboard"), I want to find concrete evidence that embeddings are computed and used to gate LLM scoring, so I can verify the candidate's cost-engineering claim is real.

**Why this priority**: The pitch makes this claim directly. Without it the README is technically false. It is also the most defensible *AI engineering* signal in the cost-discipline narrative — anyone can call an LLM, fewer candidates know to pre-filter with embeddings.

**Independent Test**: A reviewer can grep the repo for `sqlite-vec`, find an `embeddings/` module, run the test suite, and observe a test that asserts the LLM scorer is *not* called for listings whose embedding cosine similarity to the preference embedding is below threshold.

**Acceptance Scenarios**:

1. **Given** a new listing is persisted, **When** the run pipeline reaches the scoring stage, **Then** the system computes (or reuses) an embedding for that listing using a cheap model.
2. **Given** a listing's embedding cosine similarity to the preference embedding is below the configured threshold, **When** the scoring stage runs, **Then** the listing is classified as `filtered_out` with a structured reason (`semantic_mismatch`) and the LLM scorer is not invoked.
3. **Given** prefiltering ran for a batch of N listings, **When** the run report is viewed, **Then** the technical diagnostics show how many listings were dropped at the embedding gate vs sent to the LLM, and the cost dashboard shows the embedding cost line item separately.
4. **Given** a recruiter clones the repo and runs `pytest tests/test_embedding_prefilter.py`, **Then** an integration test passes that exercises the full gate flow with deterministic fixtures.

---

### User Story 2 - Recruiter Verifies The Prompt Caching Claim (Priority: P1)

As a hiring manager evaluating cost discipline, I want to confirm prompt caching is wired into actual LLM calls (not just mentioned in the README), so I can trust the under-$1/month cost claim.

**Why this priority**: The pitch lists prompt caching by name. It is also the single highest-value-per-effort change in this spec — it is a one-line header on the request, but the fact that the candidate knows to add it, knows which prompts to mark cacheable, and surfaces cache-hit rate in the dashboard is the signal.

**Independent Test**: A reviewer can search for `cache_control` in `src/backend/doormat/llm/` and find at least the system prompts on extraction, scoring, and discovery agents marked as `ephemeral`. The cost dashboard shows a "cache hit rate" metric.

**Acceptance Scenarios**:

1. **Given** an LLM call is made with a system prompt that has been seen before in the last 5 minutes, **When** OpenRouter returns the response, **Then** the response includes cache-hit metadata and `cost_tracking.py` records the discounted cost.
2. **Given** a run completes that triggered ≥3 LLM calls with the same system prompt, **When** the cost dashboard is viewed, **Then** a `cache_hit_rate` value > 0 is displayed and the corresponding cost reduction is reflected in the "savings" line.
3. **Given** a developer reviews `src/backend/doormat/llm/client.py`, **Then** they see explicit `cache_control` annotations on the messages array of every LLM call that uses a stable system prompt.

---

### User Story 3 - Recruiter Plugs Doormat's MCP Server Into Claude Desktop (Priority: P1)

As a hiring manager who uses Claude Desktop or another MCP-aware client, I want to add Doormat as an MCP server with a one-line config and immediately call `search_listings`, `get_listing`, `explain_score`, and `trigger_scrape`, so I can experience the project as a working AI tool rather than a static repo.

**Why this priority**: This is the highest-leverage hiring signal of the four. MCP is the most current AI-engineering protocol (2025-2026). A working FastMCP server with non-trivial tools is rare in candidate portfolios. It transforms Doormat from "code you read" into "tool you run." It is in BUILD-GUIDE §3 but never built.

**Independent Test**: A reviewer adds the documented `mcp` config block to their Claude Desktop config, restarts Claude Desktop, and successfully calls `search_listings(city="Austin, TX")` to see real listings returned.

**Acceptance Scenarios**:

1. **Given** a fresh clone with a populated SQLite database, **When** the user runs `uv run doormat-mcp`, **Then** a FastMCP server starts on stdio and exposes the four tools.
2. **Given** Claude Desktop has Doormat configured as an MCP server, **When** the user asks Claude "find me 2-bedrooms under $2500 in Austin," **Then** Claude calls `search_listings` with structured args and returns results from the local database.
3. **Given** the user calls `explain_score` for a specific listing ID via MCP, **Then** the response includes the score, score_explanation, and matched/missed preferences from the canonical Listing record.
4. **Given** the user calls `trigger_scrape` for a city via MCP, **Then** the server creates a `SearchRun`, returns the run ID, and the run is observable in the existing `/runs/[runId]` page.
5. **Given** the README is reviewed, **Then** there is a copy-paste-ready Claude Desktop config block, a screenshot or asciicast of the integration working, and a note that MCP also works with Cursor and other MCP clients.

---

### User Story 4 - Recruiter Sees Versioned Prompts Backed By Evals (Priority: P2)

As a hiring manager, I want to see that prompts are versioned, that an eval harness measures their quality, and that regressions fail CI, so I can verify the candidate practices production-grade prompt engineering rather than ad-hoc prompting.

**Why this priority**: BUILD-GUIDE §15 pitch claims "production-grade prompt engineering with versioned evals." The Doormat constitution §IV makes the same claim ("Prompts are versioned, evaluated, and cached in source control"). This is the second-highest AI-engineering signal after MCP, but lower than P1 because evals primarily protect against future regression — the existing prompts work today.

**Dependency note**: The parallel agent is delivering the `prompt_registry` module and `Preference.prompt_overrides` column. This story **adds versioning metadata to that registry** and builds the eval harness on top — it does *not* re-implement registry storage. If the registry is not landed by start time, the eval harness can stub a `prompt_version` constant module that the registry adopts later.

**Independent Test**: A reviewer opens `evals/` in the repo, runs `uv run pytest evals/`, and observes per-prompt pass/fail counts against a small fixture set with documented thresholds. They can then `grep prompt_version src/backend/doormat/llm/prompt_registry.py` and find a `version` field next to each registered prompt.

**Acceptance Scenarios**:

1. **Given** the parallel agent's `prompt_registry` module exists, **When** a developer reads `DEFAULT_PROMPTS`, **Then** each entry carries a `version: str` (e.g. `"v1"`) alongside the template text — added by this story as an additive enhancement.
2. **Given** any LLM call site resolves a prompt via `get_effective_prompt(...)`, **When** the call records cost/event metadata, **Then** the resolved prompt's `version` is captured in the cost-tracking row and the `SearchRunEvent` diagnostics — never the override text itself, which may contain user PII.
3. **Given** an `evals/` directory at the repo root, **When** `uv run pytest evals/` is run, **Then** at minimum 4 eval suites execute (one per pitch-relevant subsystem: extraction price/address/beds, classifier legitimacy, scoring satisfaction, discovery yield) using fixture HTML/JSON snapshots, all using *default* prompts pulled from the registry by version.
4. **Given** an eval run completes, **When** the report is viewed, **Then** each suite shows a pass-rate vs. its documented threshold (extraction ≥0.95 on price/address/beds, classifier ≥0.90, scoring ≥0.80) and CI fails if any threshold is breached.
5. **Given** a prompt version is bumped from `v1` to `v2` in the registry, **When** the eval harness is rerun, **Then** results for both versions are stored alongside each other in `evals/results/<key>/<version>.json` so improvements are quantifiable.

---

### Edge Cases

- An LLM provider does not return cache-hit metadata in the same shape across models (Anthropic Claude vs OpenAI vs DeepSeek via OpenRouter).
- The user has zero listings in the DB when MCP `search_listings` is called.
- The embedding model is unavailable (network failure) — pre-filter must degrade gracefully (skip the gate, not fail the run).
- An eval fixture references a property manager whose website has changed — the eval should be resilient to fixture drift, not a live test.
- The MCP server is started without a populated DB — tools must return empty arrays with a helpful message, not crash.
- A `cache_control` annotation is added to a prompt that is *not* stable across calls (e.g. interpolated user input) — this would silently waste cache budget; the helper that adds the annotation must validate the prompt has no per-call substitutions.
- Embedding cosine similarity uses a fixed threshold; threshold is wrong for some preferences (very specific or very vague). The system should fall back to LLM scoring on ambiguous matches rather than over-filter.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Embedding Pre-Filter (US1)

- **FR-001**: System MUST add `sqlite-vec` to `pyproject.toml` dependencies and load the extension in the SQLAlchemy engine init.
- **FR-002**: System MUST compute an embedding for each `Preference` row when its description or hard filters change, and store it in a vector column.
- **FR-003**: System MUST compute an embedding for each `Listing` row when its scoring-relevant fields are first populated, and store it in a vector column.
- **FR-004**: System MUST run a vector similarity query before invoking the LLM scorer; listings below the configured cosine threshold MUST be classified `filtered_out` with reason `semantic_mismatch` and skip the LLM call.
- **FR-005**: System MUST use a cheap embedding model (e.g. `text-embedding-3-small` or an OpenRouter equivalent) and record its cost separately under cost component `embedding`.
- **FR-006**: Embedding pre-filter MUST degrade gracefully if the embedding API is unavailable: log a warning, emit a `warning` run event, and proceed to LLM scoring without filtering.
- **FR-007**: The cost dashboard MUST surface a separate `embedding` cost line and a "listings filtered at embedding gate" counter per run.

#### Prompt Caching (US2)

- **FR-008**: System MUST annotate stable system prompts with provider-appropriate cache-control headers on every LLM call (extraction Mode A & B, scoring, discovery classifier).
- **FR-009**: A helper in `src/backend/doormat/llm/client.py` MUST validate that any message marked cacheable contains no per-call interpolated values; an attempt to cache an unstable prompt MUST raise at construction time, not silently waste cache budget.
- **FR-010**: System MUST capture cache-hit metadata from the LLM response (when present) and store it on the cost-tracking row.
- **FR-011**: The cost dashboard MUST display `cache_hit_rate` (0-1) and `cache_savings_usd` aggregates over a selectable time window.
- **FR-012**: When a provider does not return cache metadata, the system MUST record `cache_hit_known: false` and exclude the call from cache-rate calculations.

#### FastMCP Server (US3)

- **FR-013**: System MUST add `fastmcp` to `pyproject.toml` and register a console-script entry `doormat-mcp` that starts the server on stdio.
- **FR-014**: The MCP server MUST expose four tools: `search_listings`, `get_listing`, `explain_score`, `trigger_scrape`. Tool input/output schemas MUST be Pydantic models reusing existing schemas where possible.
- **FR-015**: `search_listings` MUST accept structured filter args (`city`, `min_bedrooms`, `max_price`, `pets_allowed`, `category`, `limit`) and return a list of canonical `Listing` rows.
- **FR-016**: `get_listing` MUST accept a `listing_id` and return the canonical Listing plus its latest `RunListingResult` if any.
- **FR-017**: `explain_score` MUST accept a `listing_id` and return the score, explanation, matched preferences, missed preferences, and the prompt version used to generate the score.
- **FR-018**: `trigger_scrape` MUST accept a `city` and `preference_id`, create a new `SearchRun`, return the run ID and a URL to the existing `/runs/[runId]` page, and the run MUST be observable in the existing run-report UI.
- **FR-019**: README MUST include a copy-paste-ready Claude Desktop MCP config block and at least one screenshot or asciicast of the integration working end-to-end.
- **FR-020**: The MCP server MUST share the FastAPI app's database session factory and never duplicate DB connection logic.

#### Eval Harness + Prompt Versioning (US4)

- **FR-021**: System MUST extend the parallel agent's `prompt_registry` module by adding a `version: str` field to each registered default prompt. No new per-module `PROMPT_VERSION` constants — the registry is the single source of truth.
- **FR-021a**: Every LLM call site that goes through `get_effective_prompt(...)` MUST capture the resolved prompt's `version` in the cost-tracking row and `SearchRunEvent` diagnostics. The override *text* MUST NOT be persisted in diagnostics; only the version key and an `is_custom: bool` flag.
- **FR-022**: System MUST add an `evals/` directory at the repo root containing at minimum: `evals/extraction/`, `evals/classifier/`, `evals/scoring/`, `evals/discovery/`.
- **FR-023**: Each eval suite MUST contain (a) deterministic fixture data (HTML snapshots, JSON Listing fixtures, sample preferences), (b) a pytest entry that exercises the live module against the fixtures using *default* prompts (`get_effective_prompt(key, preference=None)`), and (c) a documented pass-rate threshold.
- **FR-024**: Eval suites MUST run via `uv run pytest evals/` and MUST be excluded from the default `pytest tests/` run (separate command, separate budget).
- **FR-025**: CI MUST run the eval suite on PRs that touch any `*.py` file in `extraction/`, `scoring/`, `discovery/`, `runs/`, or `llm/prompt_registry.py`.
- **FR-026**: A regression that drops any eval below its threshold MUST fail CI.
- **FR-027**: Per-prompt-version eval results MUST be stored in `evals/results/<key>/<version>.json` so improvements between versions are version-controlled.

### Success Criteria

These are the binary checks a reviewer can perform to verify the spec is delivered:

- **SC-001**: `grep -rn "sqlite_vec\|sqlite-vec" pyproject.toml src/` returns matches.
- **SC-002**: `pytest tests/test_embedding_prefilter.py -v` passes and asserts a listing is dropped before the LLM scorer.
- **SC-003**: `grep -rn "cache_control" src/backend/doormat/llm/` returns matches on at least 4 distinct LLM call sites.
- **SC-004**: Cost dashboard displays a `cache_hit_rate` value > 0 after a run that involved repeated system prompts.
- **SC-005**: `uv run doormat-mcp --help` succeeds and lists the four MCP tools.
- **SC-006**: README contains an MCP config block and a screenshot/asciicast showing Claude Desktop calling a Doormat tool.
- **SC-007**: `uv run pytest evals/` produces a per-suite report with thresholds.
- **SC-008**: At least one prompt has been bumped from `v1` to `v2` with both versions' results in `evals/results/`.
- **SC-009**: README "What's interesting in this codebase" section leads with Phase 5 (interactive runs) and the four pitch-completion items below it.

---

## Out of Scope *(deferred for portfolio submission)*

These items appear in BUILD-GUIDE.md but are explicitly **not part of this spec**. Each row records the deferral rationale so a future reviewer (or the candidate) can revisit.

| Feature | Source | Defer rationale |
|---|---|---|
| APScheduler cron jobs (twice-daily scrape, daily digest, photo backfill, strategy health check) | §3, §6 | Operational plumbing; no AI-engineering signal. The user can trigger a run from the UI; cron adds no portfolio value. |
| Resend email digest + SMTP fallback | §11 | Same as above; an email gateway is a workflow tool, not a hiring signal. |
| Photo backfill / download to local volume | §3 | Storage detail; listings already display photos via remote URL. |
| Skills bundle (`skills/doormat-mvp/`) for Zo Computer | §1, §9 | Niche audience; will be confusing to a recruiter unfamiliar with Zo. |
| MapLibre + react-map-gl frontend mapping | §2, §10 | UX polish; not an AI-engineering claim. |
| Onboarding chat (LLM-driven preference extraction with `instructor`) | §7 | The form-based preference editor already works for a single user. LLM-driven onboarding adds cost without unblocking the pitch. Could be a P3 follow-up. |
| MkDocs Material site with mkdocstrings | §13 | README + CLAUDE.md is sufficient documentation surface for portfolio review. |
| Hero GIF / vhs README recording | §14 | Marketing artifact, not engineering. *Optional half-day polish item* — recommended to include if any time remains, but does not block submission. |
| Sidebar conversational refinement with tool use | §7 | Frontend chat UI exists but lacks backend tool-use. Sidebar refinement is genuinely interesting AI-engineering, but it is a P3 *additional* feature, not a pitch-completion item. Could be User Story 5 in a future spec if desired. |

---

## Key Entities *(used by the implementation plans)*

- **PreferenceEmbedding** *(new)*: vector column on `Preference`. Recomputed when description or hard filters change. Used as the query vector in the pre-filter.
- **ListingEmbedding** *(new)*: vector column on `Listing`. Computed once per listing on first scoring pass; reused across runs.
- **PromptVersionMetadata** *(new, on existing CostTrackingRow / SearchRunEvent)*: a `prompt_version` string stored on every LLM-call cost row and structured run-event diagnostic, so prompt evolution is traceable.
- **CacheHitMetadata** *(new, on existing CostTrackingRow)*: `cache_hit_known: bool`, `cache_hit: bool | null`, `cache_savings_usd: float`. Surfaced in cost dashboard aggregates.
- **MCPToolSchema** *(new, in `src/backend/doormat/mcp/schemas.py`)*: Pydantic models for the four tools' inputs/outputs. Reuse `ListingResponse`, `SearchRunResponse`, etc., where existing.
- **EvalFixture** *(new, in `evals/`)*: JSON or HTML files representing canonical inputs. Plus per-suite Python harness modules.

---

## Recommended Sequencing *(non-binding — informs `tasks.md` later)*

> **Sequencing decision (2026-04-26):** Do **not** start any user story in this spec until the parallel agent's "Listings table, maps, and editable LLM prompts" plan has fully merged. After that lands:
>
> 1. **Re-survey the codebase** — the parallel work changes Listing serialization, the `Preference` model, and adds a `prompt_registry`. Acceptance criteria below depend on the *final* shape of those modules. Run `git log` against `main`, re-read `src/backend/doormat/llm/prompt_registry.py` and `src/backend/doormat/models/orm.py`, and confirm each FR's file paths are still correct before generating `tasks.md`.
> 2. **Reconfirm scope** — if the parallel work shipped anything that overlaps with this spec (e.g. they added embedding columns "for free" while doing geocode columns), strike the redundant FRs and update `SC-*` accordingly.
> 3. **Then proceed with the sequence below.**

Once unblocked:

1. **US2 / Prompt Caching** *(½ day)* — smallest scope, completes a pitch claim, immediate cost-dashboard signal. No dependency on parallel work; could in theory ship before US4 even if registry is delayed.
2. **US1 / Embedding Pre-Filter** *(1.5 days)* — add `sqlite-vec`, embedding generation, vector column, pre-filter gate, cost line item. Coordinate the Alembic migration with whatever migration the parallel agent shipped (likely `Listing.latitude/longitude` and `Preference.prompt_overrides`).
3. **US3 / FastMCP Server** *(1 day)* — biggest hiring win. Build last among P1s so listings/runs UX bugs surface during MCP testing. Independent of parallel work.
4. **US4 / Eval Harness** *(1.5 days)* — depends on the merged `prompt_registry`. Add the `version` field to each registered default, wire `get_effective_prompt` consumers to record the version, then build the eval harness on top.
5. **README rewrite** *(½ day)* — lead with Phase 5 interactive runs + pitch-completion items above; add MCP config block and screenshots.

Total post-unblock: ~5 focused days. Each user story can ship as its own PR / `tasks.md` cycle. P1 stories are independently shippable; US4 is best deferred until both P1s and the parallel work land.

---

## Notes For Future Specs

- US3 (FastMCP) is large enough that, when implemented, it should generate its own `tasks.md` via `/speckit.tasks 006-portfolio-pitch-completion --user-story=US3`. Same for US4.
- A *separate* future spec (`007-...`) should cover the deferred items above if the candidate ever returns to flesh out the operational layer (scheduler, email, photo backfill).
- Phase 5's "sidebar conversational refinement" referenced in BUILD-GUIDE §7 but not implemented could become spec 008 if needed.
