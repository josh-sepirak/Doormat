# Doormat Technical Implementation Plan

**Version**: 1.0  
**Created**: 2026-04-25  
**Status**: Ready for Task Breakdown

> **Note (2026-05):** The phase checklists below are an early roadmap. Delivery is tracked in `specs/*/tasks.md` on `main`; do not treat unchecked rows here as the source of truth for current work.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           Frontend (Next.js 15)                              │
│  • Next.js 15 App Router + Tailwind UI + shadcn/ui                          │
│  • TanStack Query v5 (server state) + nuqs (URL state)                       │
│  • react-map-gl + MapLibre GL (map view)                                     │
│  • Real-time SSE updates + WebSocket heartbeat                               │
│  • Typed client: @hey-api/openapi-ts (auto-generated from FastAPI schema)    │
│  • Runs: localhost:3000                                                      │
└──────────────────────────────────────────────────────────────────────────────┘
                                      ↕
┌──────────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Backend (Python)                             │
│  • FastAPI 0.x + Pydantic v2 (validation at all boundaries)                 │
│  • SQLAlchemy 2.0 (typed ORM) + Alembic (migrations)                         │
│  • SQLite + WAL (local) | Postgres (swap-in)                                │
│  • structlog (JSON logging) + Prometheus metrics (/metrics)                  │
│  • Cost tracking + dashboard aggregation                                     │
│  • Runs: localhost:8000                                                      │
│                                                                              │
│  Agent Orchestration Layer:                                                  │
│  ├─ Browser-Use (discovery + scraper generation)                             │
│  ├─ LLM loops (extraction generation, scoring, feedback)                    │
│  ├─ instructor (structured output + retries)                                │
│  ├─ OpenRouter client (200+ model access)                                   │
│  └─ Apify fallback (anti-bot for protected sites)                           │
│                                                                              │
│  FastMCP Server:                                                             │
│  └─ Exposes Doormat capabilities to external Claude agents                  │
└──────────────────────────────────────────────────────────────────────────────┘
                                      ↕
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Data Layer (SQLite + sqlite-vec)                       │
│  • preferences (user searches)                                               │
│  • property_managers (discovery cache)                                       │
│  • extraction_strategies (LLM-generated scrapers)                            │
│  • listings (pulled + scored)                                                │
│  • costs (LLM calls, API usage, aggregated metrics)                          │
│  • embedding_cache (soft-preference pre-filters)                             │
│  • extraction_feedback (validation results for refinement)                   │
│  • WAL mode (concurrent reads + writes)                                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Foundation & Infrastructure (Week 1-2)
**Goal**: Backend scaffolding, database, observability, CI/CD ready

#### Tasks
- [ ] **1.1**: FastAPI project scaffold (uvicorn, ASGI, error handling)
- [ ] **1.2**: SQLAlchemy 2.0 models (typed, with Mapped[T] annotations)
- [ ] **1.3**: Alembic migrations setup + initial schema (preferences, property_managers, listings, costs)
- [ ] **1.4**: Pydantic models for API responses (schema validation)
- [ ] **1.5**: structlog setup (JSON in prod, console in dev) + cost tracking middleware
- [ ] **1.6**: `/metrics` Prometheus endpoint + cost aggregation
- [ ] **1.7**: Docker + docker-compose.yml (FastAPI + SQLite volume)
- [ ] **1.8**: Dockerfile (uv multi-stage, python:3.13-slim, cache mounts)
- [ ] **1.9**: GitHub Actions workflow (matrix 3.12/3.13, ruff lint, mypy strict, pytest)
- [ ] **1.10**: pyproject.toml + uv lock (dependencies locked)
- [ ] **1.11**: OpenRouter client setup (SDK pointed at OpenRouter)
- [ ] **1.12**: Error handling + retry logic (tenacity for transient failures)

**Deliverables**: Backend runs `docker compose up`, test endpoints work, cost logs flowing

---

### Phase 2: Discovery Agent (Week 2-3)
**Goal**: Autonomous property manager discovery via Browser-Use

#### Tasks
- [ ] **2.1**: Browser-Use orchestration setup (login, navigation, screenshot capture)
- [ ] **2.2**: Discovery LLM loop (system prompt + multi-turn agent)
- [ ] **2.3**: Candidate validation agent (verify property manager legitimacy)
- [ ] **2.4**: Cache layer (store discovered managers per city, avoid re-discovery)
- [ ] **2.5**: Error handling + feedback loop (retry invalid discoveries)
- [ ] **2.6**: Cost tracking per city (discovery $0.03 target)
- [ ] **2.7**: Logging + observability (structured discovery traces)
- [ ] **2.8**: Unit tests (discovery logic, caching, validation)

**Deliverables**: Agent discovers 20+ property managers in test city, caches results, costs tracked

---

### Phase 3: Scraper Generation & Extraction (Week 3-4)
**Goal**: LLM generates extraction strategies; two-tier extraction pipeline

#### Tasks
- [ ] **3.1**: Extraction strategy generator (LLM → working parsing code)
- [ ] **3.2**: Tier 1 extraction (cheap model + structured output via instructor)
- [ ] **3.3**: Tier 2 validation (stronger model checks Tier 1 results)
- [ ] **3.4**: Feedback loop (refinement on validation failures)
- [ ] **3.5**: Listing model + schema (property attributes: address, price, bedrooms, etc.)
- [ ] **3.6**: Batch extraction (process 100s of listings efficiently)
- [ ] **3.7**: Rate limiting + robot.txt respect (no aggressive scraping)
- [ ] **3.8**: Cost tracking (extraction $0.02 target)
- [ ] **3.9**: Error handling (partial failures, retries, manual override)
- [ ] **3.10**: Integration tests (extraction validates for 5+ property manager types)

**Deliverables**: 1000 listings extracted + validated in < 10 minutes, cost <$0.05

---

### Phase 4: Listing Scoring + Frontend (Week 4-5)
**Goal**: Score listings against preferences; beautiful Next.js dashboard

#### Tasks
- [ ] **4.1**: Embedding model setup (soft-preference pre-filter via sqlite-vec)
- [ ] **4.2**: Scoring agent (LLM ranks listings + explains why)
- [ ] **4.3**: Listing API endpoints (paginated, filterable, scoreable)
- [ ] **4.4**: Next.js setup (App Router, Tailwind UI, shadcn/ui)
- [ ] **4.5**: TypeScript client generation (OpenAPI → @hey-api/openapi-ts)
- [ ] **4.6**: Preference editor page (natural language input)
- [ ] **4.7**: Listings page (map view + card grid)
- [ ] **4.8**: Real-time SSE setup (sse-starlette backend + useEffect frontend)
- [ ] **4.9**: Filter UI (nuqs for shareable URL state)
- [ ] **4.10**: Saved listings feature (star/save, export)
- [ ] **4.11**: Cost scoring indicator (show cost per component)
- [ ] **4.12**: Responsive design + accessibility (WCAG AA)

**Deliverables**: Dashboard renders, filters work, real-time updates, 90-second demo video capability

---

### Phase 5: Cost Optimization & Dashboarding (Week 5-6)
**Goal**: Live cost dashboard, model routing, prompt caching verification

#### Tasks
- [ ] **5.1**: Cost aggregation logic (parse logs, group by component/model/city)
- [ ] **5.2**: Cost dashboard API endpoints (GET /api/costs, GET /api/costs/{city}, etc.)
- [ ] **5.3**: Dashboard frontend (charts, trends, alerts)
- [ ] **5.4**: Model routing decision logic (choose cheapest viable model)
- [ ] **5.5**: Prompt caching verification (measure hits/misses)
- [ ] **5.6**: Budget alerts (notify if spending exceeds limit)
- [ ] **5.7**: Profiling + optimization (identify hot paths)
- [ ] **5.8**: Load testing (1000 listings, 5 concurrent cities)
- [ ] **5.9**: Documentation (cost engineering guide for users + devs)

**Deliverables**: Cost dashboard live, verify <$1/month for typical use, prompt caching proven

---

### Phase 6: Polish, Security & Launch (Week 6)
**Goal**: Security audit, performance tuning, MCP integration, documentation

#### Tasks
- [ ] **6.1**: Security audit (dependency scanning, OWASP checks)
- [ ] **6.2**: API key rotation strategy (OpenRouter, Apify)
- [ ] **6.3**: Input validation hardening (Pydantic strict mode)
- [ ] **6.4**: FastMCP server implementation (expose 4-6 key endpoints)
- [ ] **6.5**: MCP integration tests (Claude agent calling Doormat)
- [ ] **6.6**: README complete (setup, usage, architecture, cost explanation)
- [ ] **6.7**: API documentation (OpenAPI + mkdocstrings)
- [ ] **6.8**: CLAUDE.md update (prompt patterns for other projects)
- [ ] **6.9**: Skills bundle creation (for Copilot/Claude Desktop integration)
- [ ] **6.10**: Performance profiling (response times, memory, CPU)
- [ ] **6.11**: Changelog + versioning (Conventional Commits, release-please)
- [ ] **6.12**: Launch checklist (release notes, demo video link, announcement)

**Deliverables**: Security passed, MCP working, docs complete, ready for public release

---

## Database Schema (Alembic Migrations)

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

## Tech Stack Decisions (Locked)

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Backend | FastAPI | OpenAPI quality + instructor integration |
| Database | SQLAlchemy 2.0 + Alembic | Typed, async, migration-safe |
| Storage | SQLite + WAL | Local, fast, swap-in Postgres |
| Vectors | sqlite-vec | Same DB, no external service |
| Logging | structlog JSON | Structured, cost-trackable, prod-ready |
| HTTP Client | httpx async | Sync+async parity, HTTP/2 |
| Retries | tenacity | Async-native, standard in industry |
| Agent Framework | Browser-Use + bare LLM | Avoid LangChain overhead |
| LLM Client | openai SDK → OpenRouter | 200+ models, free tier |
| Structured Output | instructor | Pydantic-typed, auto-retry |
| Frontend | Next.js 15 App Router | Build-time safe, runtime simple |
| Frontend Styling | Tailwind UI + shadcn/ui | Minimal deps, beautiful defaults |
| State (Client) | TanStack Query v5 + nuqs | Standard 2026, shareable URLs |
| Maps | MapLibre GL + react-map-gl | No vendor lock-in |
| Real-time | SSE + sse-starlette | Simple, one-way, browser-native |
| Type Safety | @hey-api/openapi-ts | FE build fails on schema drift |
| Deployment | Docker Compose | Local dev + easy VPS deploy |
| CI/CD | GitHub Actions | Matrix 3.12/3.13, release-please |

---

## Quality Gates

### Before Merge
- [ ] Ruff format + lint: 0 errors
- [ ] mypy strict: 0 errors (all types checked)
- [ ] Pytest: 100% pass, >80% coverage
- [ ] Cost tracking verified (logging working)
- [ ] API schema generated (no drift from code)

### Before Release
- [ ] Security audit: 0 critical/high findings
- [ ] Integration tests: discovery + extraction + scoring full flow
- [ ] Load test: 1000 listings in <10 min, cost <$0.05
- [ ] Documentation: README + API docs + architecture guide
- [ ] MCP integration: tested with external Claude agent

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Extraction failures (site changes) | Feedback loop refines strategy; manual override available |
| Cost overruns | Budget alerts + model routing chooses cheapest option |
| Rate limiting (429 errors) | Respect robots.txt, rate limits per manager, retry with backoff |
| Security (API key exposure) | Pydantic validation, .env for secrets, audit trail |
| Type mismatches (API drift) | FE build fails on schema mismatch (OpenAPI validation) |
| Performance (slow dashboard) | SSE for real-time, TanStack Query caching, lazy-load map |

---

## Approval & Handoff

**Plan Owner**: Doormat Project Lead  
**Approved**: 2026-04-25  
**Next Phase**: `/speckit.tasks` (Task Breakdown)

