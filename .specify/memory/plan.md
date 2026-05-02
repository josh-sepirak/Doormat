# Doormat Technical Implementation Plan

**Version**: 2.0  
**Created**: 2026-04-25  
**Last reconciled**: 2026-05-02  
**Status**: Living plan — checklists below reflect **what is on `main` today** vs **explicit backlog**. Authoritative feature tracking lives in `specs/*/tasks.md`.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js App Router)                            │
│  • Next.js 16 App Router + Tailwind + Headless UI                           │
│  • Leaflet + react-leaflet (listing maps)                                    │
│  • SSE consumption for listing streams where implemented                     │
│  • Typed API helpers (`@hey-api/openapi-ts` in dev; hand-written clients)    │
│  • Runs: localhost:3000                                                      │
└──────────────────────────────────────────────────────────────────────────────┘
                                      ↕
┌──────────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Backend (Python)                             │
│  • FastAPI + Pydantic v2                                                     │
│  • SQLAlchemy 2.0 (Mapped columns) + Alembic                                  │
│  • SQLite + WAL (local) | Postgres via `DATABASE_URL`                       │
│  • structlog + `/metrics` Prometheus                                          │
│  • Cost tracking + `/api/costs/*`                                            │
│  • Runs: localhost:8000                                                      │
│                                                                              │
│  Agent & extraction:                                                         │
│  ├─ Browser-Use (discovery; Mode B recovery)                                │
│  ├─ Mode A / A0 / B extraction + strategy cache                            │
│  ├─ OpenRouter via openai SDK; optional Apify                               │
│  └─ Search runs pipeline + trusted sources (Craigslist regions, PM URLs)     │
│                                                                              │
│  FastMCP:                                                                    │
│  └─ `doormat/mcp_server.py` (stdio tools — wire/deploy per self-host)       │
└──────────────────────────────────────────────────────────────────────────────┘
                                      ↕
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Data Layer (SQLite; sqlite-vec planned)              │
│  • preferences, property_managers, listings, costs, extraction_strategies    │
│  • search_runs, search_run_events, run_listing_results, …                   │
│  • trusted_sources, geocode cache, …                                          │
│  • WAL mode                                                                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

Legend: `[x]` shipped on `main` · `[ ]` not shipped or not formally verified · Wording may differ slightly from v1.0 plan; capability is what matters.

### Phase 1: Foundation & Infrastructure

**Goal**: Backend scaffolding, database, observability, CI.

| ID | Task | Status |
|----|------|--------|
| 1.1 | FastAPI app (`doormat.main`), lifespan, CORS, routers | [x] |
| 1.2 | SQLAlchemy 2.0 ORM (`Mapped[...]`), async session | [x] |
| 1.3 | Alembic migrations + evolving schema (preferences, listings, runs, …) | [x] |
| 1.4 | Pydantic I/O schemas (`schemas.py`, routers) | [x] |
| 1.5 | structlog + cost hooks / middleware | [x] |
| 1.6 | `/metrics` Prometheus | [x] |
| 1.7 | Docker Compose + SQLite volume | [x] |
| 1.8 | Dockerfile (uv-based image) | [x] |
| 1.9 | GitHub Actions CI (Python **3.13**, Ruff, pytest, frontend steps as configured) | [x] |
| 1.10 | `pyproject.toml` + `uv.lock` | [x] |
| 1.11 | OpenRouter-capable LLM client + settings | [x] |
| 1.12 | Retries / resilience (tenacity where used) | [x] |

**Deliverables**: `docker compose up`, health + core APIs, CI green on `main`.

---

### Phase 2: Discovery Agent

**Goal**: Property manager discovery with Browser-Use and persistence.

| ID | Task | Status |
|----|------|--------|
| 2.1 | Browser-Use available path for discovery / Mode B | [x] |
| 2.2 | Discovery agent + LLM loop (`discovery/agent.py`, prompts) | [x] |
| 2.3 | Candidate validation / classification | [x] |
| 2.4 | Discovery cache + `PropertyManager` records | [x] |
| 2.5 | Error handling, retries, logging | [x] |
| 2.6 | Per-call / per-component cost tracking | [x] |
| 2.7 | Structured discovery traces | [x] |
| 2.8 | Tests (`tests/` discovery-related coverage) | [x] |

**Deliverables**: `/api/discovery/*` usable end-to-end with real keys.

---

### Phase 3: Scraper Generation & Extraction

**Goal**: Strategies, Mode A / A0 / B, listings in DB.

| ID | Task | Status |
|----|------|--------|
| 3.1 | Strategy cache + LLM-driven strategy updates | [x] |
| 3.2 | Mode A deterministic extraction | [x] |
| 3.3 | Mode B agentic recovery | [x] |
| 3.4 | Refinement / merge path for strategies | [x] |
| 3.5 | `Listing` model + extraction metadata | [x] |
| 3.6 | Batch / pipeline extraction in search runs | [x] |
| 3.7 | robots.txt + rate discipline for all HTTP (formal audit) | [ ] |
| 3.8 | Cost attribution for extraction | [x] |
| 3.9 | Partial failures, escalation, logging | [x] |
| 3.10 | Broad matrix of “5+ PM site types” in one integration test | [ ] |

**Deliverables**: Listings extracted and persisted through the live pipeline.

---

### Phase 4: Listing Scoring + Frontend

**Goal**: Scored listings, dashboard UX, streams.

| ID | Task | Status |
|----|------|--------|
| 4.1 | **sqlite-vec** embedding pre-filter before LLM scoring | [ ] |
| 4.2 | LLM + heuristic scoring (`scoring/`) | [x] |
| 4.3 | Listings API (pagination, filters, save, score, stream) | [x] |
| 4.4 | Next.js App Router app shell (`src/frontend`) | [x] |
| 4.5 | OpenAPI → TypeScript workflow (`openapi.json`, `@hey-api/openapi-ts`) | [x] |
| 4.6 | Preferences UI + API | [x] |
| 4.7 | Listings UI + **Leaflet** map (not MapLibre stack) | [x] |
| 4.8 | SSE listing stream (`text/event-stream`) | [x] |
| 4.9 | **nuqs** / TanStack Query as primary URL + server cache layer | [ ] |
| 4.10 | Saved listings | [x] |
| 4.11 | Costs surfaced (API + `/costs` page) | [x] |
| 4.12 | Responsive + dark/light + ongoing a11y (see run report header notes) | [x] |

**Deliverables**: Usable dashboard for discovery, runs, listings, costs, preferences, sources.

---

### Phase 5: Cost Optimization & Dashboarding

**Goal**: Visibility into spend; tighten efficiency over time.

| ID | Task | Status |
|----|------|--------|
| 5.1 | Cost aggregation + persistence | [x] |
| 5.2 | Costs API (`/api/costs/*`) | [x] |
| 5.3 | Costs UI | [x] |
| 5.4 | Tiered / routed model selection (`LLMClient`, prefs) | [x] |
| 5.5 | Prompt / response caching verification & metrics | [ ] |
| 5.6 | Budget limit enforcement + user-visible alerts | [ ] |
| 5.7 | Profiling hot paths (backend + frontend) | [ ] |
| 5.8 | Formal load test (1000 listings / multi-city SLO) | [ ] |
| 5.9 | Cost engineering guide beyond `CLAUDE.md` snippets | [ ] |

**Deliverables**: Operators can see and reason about cost; SLO hardening is backlog.

---

### Phase 6: Polish, Security & Launch

**Goal**: Hardening, MCP adoption, packaging.

| ID | Task | Status |
|----|------|--------|
| 6.1 | Third-party security audit + dependency policy | [ ] |
| 6.2 | Documented API key rotation playbook | [ ] |
| 6.3 | Pydantic validation at API boundaries | [x] |
| 6.4 | FastMCP server module present | [x] |
| 6.5 | MCP exercised by external agent in CI or documented manual matrix | [ ] |
| 6.6 | README + `CLAUDE.md` + spec kit docs | [x] |
| 6.7 | OpenAPI `/docs` + inline router docs (mkdocstrings site optional) | [ ] |
| 6.8 | `CLAUDE.md` maintained for agent workflows | [x] |
| 6.9 | Contributor / Claude skills (e.g. contribute-rental-source) | [x] |
| 6.10 | Performance profiling report | [ ] |
| 6.11 | release-please or equivalent automated changelog | [ ] |
| 6.12 | Public launch checklist (demo asset, comms) | [ ] |

**Deliverables**: Self-hostable product; launch-grade polish items tracked above.

---

## Database Schema (Alembic Migrations)

> **Note:** The SQL sketch below is illustrative; **source of truth** is `src/backend/doormat/models/orm.py` and `alembic/versions/*`.

```sql
-- Preferences: User search criteria
CREATE TABLE preferences (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,              -- "modern 2-bed under $2000"
    city TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Property Managers: Discovery cache
CREATE TABLE property_managers (
    id TEXT PRIMARY KEY,
    city TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT,
    listing_page_url TEXT,
    validated BOOLEAN DEFAULT FALSE,
    discovery_timestamp TIMESTAMP,
    INDEX (city)
);

-- Extraction Strategies: LLM-generated scrapers
CREATE TABLE extraction_strategies (
    id TEXT PRIMARY KEY,
    property_manager_id TEXT FOREIGN KEY,
    strategy_json TEXT NOT NULL,            -- LLM output: parsing logic
    tier1_model TEXT,                       -- cheap model (e.g., Claude Mini)
    tier2_model TEXT,                       -- validation model (e.g., Claude 3.5)
    validation_rate FLOAT DEFAULT 0.95,     -- % passing Tier 2
    last_refined TIMESTAMP,
    FOREIGN KEY (property_manager_id) REFERENCES property_managers(id)
);

-- Listings: Extracted + scored rentals
CREATE TABLE listings (
    id TEXT PRIMARY KEY,
    property_manager_id TEXT,
    address TEXT,
    bedrooms INT,
    price FLOAT,
    url TEXT,
    raw_data JSONB,
    extraction_timestamp TIMESTAMP,
    extraction_model TEXT,
    tier1_cost FLOAT,
    tier2_cost FLOAT,
    validation_passed BOOLEAN,
    FOREIGN KEY (property_manager_id) REFERENCES property_managers(id)
);

-- Embeddings: soft-preference pre-filter
CREATE TABLE embedding_cache (
    id TEXT PRIMARY KEY,
    listing_id TEXT,
    preference_id TEXT,
    embedding BLOB,                         -- sqlite-vec vector
    similarity FLOAT,
    pre_filter_passed BOOLEAN,              -- passed soft-filter
    FOREIGN KEY (listing_id) REFERENCES listings(id),
    FOREIGN KEY (preference_id) REFERENCES preferences(id)
);

-- Costs: LLM calls + API usage
CREATE TABLE costs (
    id TEXT PRIMARY KEY,
    component TEXT,                         -- discovery|extraction|scoring
    model TEXT,                             -- claude-mini, gpt-4, etc.
    tokens_in INT,
    tokens_out INT,
    cost_usd FLOAT,
    cache_hit BOOLEAN,
    timestamp TIMESTAMP,
    city TEXT,
    INDEX (component, timestamp)
);

-- Extraction Feedback: Validation results for refinement
CREATE TABLE extraction_feedback (
    id TEXT PRIMARY KEY,
    strategy_id TEXT,
    listing_id TEXT,
    validation_result TEXT,                 -- pass|fail|partial
    error_message TEXT,
    refined_strategy JSONB,
    timestamp TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES extraction_strategies(id),
    FOREIGN KEY (listing_id) REFERENCES listings(id)
);
```

---

## API Contracts (FastAPI Endpoints)

> **Note:** Paths evolve; verify in `doormat.main` and router modules.

### Preferences
- `POST /api/preferences` → Create new search profile
- `GET /api/preferences` → List all profiles
- `PUT /api/preferences/{id}` → Update
- `DELETE /api/preferences/{id}` → Delete

### Discovery
- `POST /api/discovery/cities/{city}` → Trigger discovery for city
- `GET /api/discovery/cities/{city}/managers` → List discovered managers
- `GET /api/discovery/cities/{city}/cost` → Cost breakdown

### Listings
- `GET /api/listings?city=SF&preference_id=abc` → Paginated, scored listings
- `GET /api/listings/{id}` → Single listing detail
- `PUT /api/listings/{id}/saved` → Save/unsave

### Scoring
- `POST /api/scoring/rescore?preference_id=abc` → Rescore all cached listings
- `GET /api/listings/scores?city=SF` → Scores for city

### Costs
- `GET /api/costs` → All-time spending
- `GET /api/costs/by-component` → Breakdown (discovery|extraction|scoring)
- `GET /api/costs/by-city?city=SF` → Per-city breakdown
- `GET /api/costs/trend?days=30` → Last 30 days

### SSE (Server-Sent Events)
- `GET /api/stream/listings?preference_id=abc` → Real-time listings stream

### Metrics
- `GET /metrics` → Prometheus format

---

## Tech Stack Decisions (Locked + drift notes)

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Backend | FastAPI | OpenAPI quality + instructor integration |
| Database | SQLAlchemy 2.0 + Alembic | Typed, async, migration-safe |
| Storage | SQLite + WAL | Local, fast, swap-in Postgres |
| Vectors | sqlite-vec | Planned; **not yet wired** (see Phase 4.1) |
| Logging | structlog JSON | Structured, cost-trackable, prod-ready |
| HTTP Client | httpx async | Sync+async parity, HTTP/2 |
| Retries | tenacity | Async-native, standard in industry |
| Agent Framework | Browser-Use + bare LLM | Avoid LangChain overhead |
| LLM Client | openai SDK → OpenRouter | 200+ models, free tier |
| Structured Output | instructor | Pydantic-typed, auto-retry |
| Frontend | Next.js App Router (v16 line) | Current app pin in `package.json` |
| Frontend Styling | Tailwind + Headless UI | Lightweight stack in repo |
| State (Client) | React hooks + hand clients | **TanStack Query + nuqs** optional upgrade |
| Maps | Leaflet + react-leaflet | Ships today |
| Real-time | SSE + FastAPI `StreamingResponse` | Listing stream |
| Type Safety | `@hey-api/openapi-ts` + TS strict | Regenerate when OpenAPI changes |
| Deployment | Docker Compose | Local dev + easy VPS deploy |
| CI/CD | GitHub Actions | Python 3.13 job today; expand matrix as needed |

---

## Quality Gates

### Before merge (continuous)

| Gate | Status |
|------|--------|
| Ruff lint + format on touched Python | [x] in CI / local |
| mypy on `src/` (strict where configured) | [x] frequent; **repo-wide zero-error bar** | [ ] |
| Pytest green (`uv run pytest`) | [x] |
| Test coverage ≥ 80% **every** package | [ ] (aspirational) |
| Cost tracking emits structured logs in dev | [x] |
| Regenerate OpenAPI + TS client when API changes | [ ] (manual today) |

### Before release (product)

| Gate | Status |
|------|--------|
| Security review (deps + OWASP-oriented pass) | [ ] |
| Long-horizon integration: discovery → extraction → scoring | [x] pieces tested; **single scripted E2E** | [ ] |
| Load / cost SLO validation | [ ] |
| README + spec kit + contributor docs | [x] |
| MCP smoke with external Claude | [ ] |

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Extraction failures (site changes) | Feedback loop refines strategy; manual override available |
| Cost overruns | Budget settings + model routing; costs UI |
| Rate limiting (429 errors) | Respect robots.txt, rate limits per manager, retry with backoff |
| Security (API key exposure) | Pydantic validation, .env for secrets, audit trail |
| Type mismatches (API drift) | FE typecheck + OpenAPI regen workflow |
| Performance (slow dashboard) | SSE streams, pagination, map lazy-load |

---

## Approval & Handoff

**Plan Owner**: Doormat Project Lead  
**Approved**: 2026-04-25  
**Reconciled**: 2026-05-02  
**Next steps**: Use `specs/*/tasks.md` for feature work; use this document for **roadmap-level** done vs backlog only.
