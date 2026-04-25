# Doormat Task Breakdown

**Version**: 1.0  
**Created**: 2026-04-25  
**Total Tasks**: 82  
**Phases**: 6

---

## Legend

- **Status**: `pending` (not started) | `in_progress` (active) | `done` (complete) | `blocked` (waiting)
- **Priority**: `critical` (blocks other tasks) | `high` (important, early) | `normal` (regular work)
- **Effort**: `xs` (<30 min) | `s` (1-2 hrs) | `m` (4-8 hrs) | `l` (1-2 days) | `xl` (2+ days)

---

## Phase 1: Foundation & Infrastructure (12 tasks, ~60 hrs)

### 1.1 FastAPI Project Scaffold
- **Task**: 1.1.1 - FastAPI app setup with uvicorn, ASGI config
- **Priority**: critical
- **Effort**: m
- **Description**: Create FastAPI app with uvicorn, error handlers, middleware. Set up `/api` versioning, health check at `GET /health`.
- **Dependencies**: None

### 1.2 SQLAlchemy Typed Models
- **Task**: 1.2.1 - Define Preference, PropertyManager, Listing, Cost models
- **Priority**: critical
- **Effort**: m
- **Description**: SQLAlchemy 2.0 with Mapped[T] type annotations. Foreign keys, indexes, timestamps. Strict type checking.
- **Dependencies**: 1.1.1

### 1.3 Alembic Migration Setup
- **Task**: 1.3.1 - Alembic initialization + first migration (schema)
- **Priority**: critical
- **Effort**: m
- **Description**: `alembic init`, configure sqlalchemy.url, create initial schema revision. Test migration up/down.
- **Dependencies**: 1.2.1

### 1.4 Pydantic API Models
- **Task**: 1.4.1 - Request/response models (PreferenceSchema, ListingSchema, etc.)
- **Priority**: high
- **Effort**: m
- **Description**: Pydantic v2 models for API I/O. Validation, serialization, docstrings.
- **Dependencies**: 1.1.1

### 1.5 structlog Setup
- **Task**: 1.5.1 - structlog configuration (JSON prod, console dev)
- **Priority**: high
- **Effort**: s
- **Description**: Configure structlog, bind context (user_id, request_id, cost). Middleware to log all requests.
- **Dependencies**: 1.1.1

### 1.6 Cost Tracking Middleware
- **Task**: 1.6.1 - Middleware logs cost per request (model, tokens, USD)
- **Priority**: high
- **Effort**: m
- **Description**: Intercept LLM calls, log to structlog. Include cache hits/misses, model, cost USD.
- **Dependencies**: 1.5.1

### 1.7 Prometheus Metrics
- **Task**: 1.7.1 - `/metrics` endpoint with cost aggregation
- **Priority**: normal
- **Effort**: m
- **Description**: Prometheus format endpoint. Track: LLM calls, tokens, cost, cache hit rate.
- **Dependencies**: 1.6.1

### 1.8 Docker Setup
- **Task**: 1.8.1 - Dockerfile (uv multi-stage, python:3.13-slim)
- **Priority**: high
- **Effort**: s
- **Description**: Multi-stage build: uv in builder, app in slim. Cache mounts. UV_LINK_MODE=copy.
- **Dependencies**: None

### 1.9 docker-compose.yml
- **Task**: 1.9.1 - docker-compose with FastAPI + SQLite volume
- **Priority**: high
- **Effort**: s
- **Description**: Services: api (FastAPI), db (SQLite mounted). Environment, ports, volumes.
- **Dependencies**: 1.8.1

### 1.10 GitHub Actions CI/CD
- **Task**: 1.10.1 - Matrix workflow (3.12/3.13), ruff lint, mypy strict, pytest
- **Priority**: high
- **Effort**: m
- **Description**: `.github/workflows/ci.yml`: lint, type check, test on matrix. Fail fast on errors.
- **Dependencies**: 1.1.1

### 1.11 pyproject.toml + uv lock
- **Task**: 1.11.1 - Define dependencies, versions, lock file
- **Priority**: critical
- **Effort**: m
- **Description**: FastAPI, SQLAlchemy, Alembic, structlog, httpx, tenacity, etc. Locked versions. uv sync reproducible.
- **Dependencies**: None

### 1.12 Error Handling + Retries
- **Task**: 1.12.1 - tenacity retry logic for transient failures
- **Priority**: normal
- **Effort**: s
- **Description**: Exponential backoff for network errors, timeouts. Logging + metrics on retry.
- **Dependencies**: 1.5.1

---

## Phase 2: Discovery Agent (8 tasks, ~50 hrs)

### 2.1 Browser-Use Setup
- **Task**: 2.1.1 - Browser-Use orchestration (login, navigation, screenshots)
- **Priority**: critical
- **Effort**: l
- **Description**: Browser-Use agent context, action handlers, state management. Test with one property manager site.
- **Dependencies**: 1.1.1, 1.11.1

### 2.2 Discovery LLM Loop
- **Task**: 2.2.1 - Multi-turn discovery agent (search → find managers → validate)
- **Priority**: critical
- **Effort**: l
- **Description**: System prompt for discovery. LLM orchestrates: search engines, directory lookups, filtering duplicates.
- **Dependencies**: 2.1.1, 1.6.1

### 2.3 Validation Agent
- **Task**: 2.3.1 - Verify property manager legitimacy (not spam, real org)
- **Priority**: high
- **Effort**: m
- **Description**: Secondary LLM check: website content, reviews, contact info. Flag suspicious candidates.
- **Dependencies**: 2.2.1

### 2.4 Discovery Caching
- **Task**: 2.4.1 - Store discovered managers per city (DB + local cache)
- **Priority**: high
- **Effort**: m
- **Description**: Cache layer: skip re-discovery if city already in DB. Timestamp invalidation (e.g., 30 days).
- **Dependencies**: 1.2.1, 2.3.1

### 2.5 Feedback Loop
- **Task**: 2.5.1 - Retry invalid discoveries, refine search strategy
- **Priority**: normal
- **Effort**: m
- **Description**: If validation fails, agent refines search. Log feedback for analysis.
- **Dependencies**: 2.3.1

### 2.6 Cost Tracking (Discovery)
- **Task**: 2.6.1 - Log discovery cost per city (target $0.03)
- **Priority**: normal
- **Effort**: s
- **Description**: Track Browser-Use steps, LLM tokens, model used. Aggregate per city.
- **Dependencies**: 1.6.1

### 2.7 Logging & Observability
- **Task**: 2.7.1 - Structured logs for discovery traces (requestID, city, managers found)
- **Priority**: normal
- **Effort**: s
- **Description**: Log each step: search query, candidates found, validation result, cost.
- **Dependencies**: 1.5.1

### 2.8 Unit Tests
- **Task**: 2.8.1 - Discovery logic tests (caching, validation, retry)
- **Priority**: normal
- **Effort**: m
- **Description**: Mock Browser-Use, test LLM loop, caching logic, validation rules.
- **Dependencies**: 2.4.1

---

## Phase 3: Scraper Generation & Extraction (10 tasks, ~60 hrs)

### 3.1 Extraction Strategy Generator
- **Task**: 3.1.1 - LLM generates parsing code for property manager site
- **Priority**: critical
- **Effort**: l
- **Description**: LLM analyzes site structure (HTML, login, pagination). Outputs extraction strategy (JSON). Test with 5+ sites.
- **Dependencies**: 2.4.1

### 3.2 Tier 1 Extraction (Fast)
- **Task**: 3.2.1 - Cheap model extracts listings with instructor structured output
- **Priority**: critical
- **Effort**: l
- **Description**: Claude Mini / GPT-3.5 extracts fields (address, price, beds). Instructor validates schema. Batch process 100s.
- **Dependencies**: 3.1.1, 1.11.1

### 3.3 Tier 2 Validation (Strong)
- **Task**: 3.3.1 - Stronger model validates Tier 1 results + corrects errors
- **Priority**: critical
- **Effort**: l
- **Description**: Claude 3.5 / GPT-4 checks Tier 1 output. Marks pass/fail/partial. Logs discrepancies for feedback loop.
- **Dependencies**: 3.2.1

### 3.4 Feedback Loop (Extraction)
- **Task**: 3.4.1 - Refine strategy on validation failures
- **Priority**: high
- **Effort**: m
- **Description**: If Tier 2 fails, analyze error. Propose refined extraction strategy. Retry failed listings.
- **Dependencies**: 3.3.1

### 3.5 Listing Model + Schema
- **Task**: 3.5.1 - Define Listing Pydantic model (address, price, beds, url, raw_data)
- **Priority**: critical
- **Effort**: s
- **Description**: Pydantic schema for rental listing. Validation rules (price > 0, beds >= 0). Optional fields.
- **Dependencies**: 1.4.1

### 3.6 Batch Extraction
- **Task**: 3.6.1 - Process 100s of listings efficiently (async, rate-limited)
- **Priority**: high
- **Effort**: m
- **Description**: Async loop: extract Tier 1, batch Tier 2 validation. Rate limit per property manager. Progress tracking.
- **Dependencies**: 3.2.1, 3.3.1

### 3.7 Rate Limiting + robots.txt
- **Task**: 3.7.1 - Respect robots.txt, per-manager rate limits
- **Priority**: high
- **Effort**: s
- **Description**: Parse robots.txt, enforce rate limits. Backoff on 429. Log violations.
- **Dependencies**: 3.6.1

### 3.8 Cost Tracking (Extraction)
- **Task**: 3.8.1 - Track Tier 1 + Tier 2 cost per listing (target $0.02 total)
- **Priority**: normal
- **Effort**: s
- **Description**: Log model, tokens in/out, USD cost per listing. Aggregate by property manager.
- **Dependencies**: 1.6.1

### 3.9 Error Handling
- **Task**: 3.9.1 - Graceful degradation on extraction failures
- **Priority**: high
- **Effort**: m
- **Description**: Partial failures don't crash. Retry logic, manual override option, fallback to raw HTML storage.
- **Dependencies**: 3.6.1

### 3.10 Integration Tests
- **Task**: 3.10.1 - Test extraction on 5+ property manager types
- **Priority**: normal
- **Effort**: m
- **Description**: Scrape test sites, verify extraction accuracy. Compare Tier 1 vs. Tier 2.
- **Dependencies**: 3.9.1

---

## Phase 4: Listing Scoring + Frontend (12 tasks, ~70 hrs)

### 4.1 Embedding Model Setup
- **Task**: 4.1.1 - Soft-preference pre-filter using embeddings + sqlite-vec
- **Priority**: high
- **Effort**: m
- **Description**: Set up embedding model (e.g., OpenAI embeddings). sqlite-vec for similarity search. Test soft-filter accuracy.
- **Dependencies**: 1.2.1, 3.5.1

### 4.2 Scoring Agent
- **Task**: 4.2.1 - LLM ranks listings + explains reasoning
- **Priority**: high
- **Effort**: m
- **Description**: Claude ranks listings vs. preferences. Outputs JSON with score + explanation.
- **Dependencies**: 4.1.1

### 4.3 Listing API Endpoints
- **Task**: 4.3.1 - GET /api/listings (paginated, filterable, scoreable)
- **Priority**: high
- **Effort**: m
- **Description**: Pagination (limit, offset), filtering (city, price range, beds). Fetch scores dynamically.
- **Dependencies**: 4.2.1, 1.4.1

### 4.4 Next.js Setup
- **Task**: 4.4.1 - Next.js 15 App Router + Tailwind UI + shadcn/ui scaffold
- **Priority**: critical
- **Effort**: m
- **Description**: Create Next.js project, configure Tailwind, install shadcn/ui components.
- **Dependencies**: None (independent)

### 4.5 TypeScript Client Generation
- **Task**: 4.5.1 - @hey-api/openapi-ts to generate typed client from FastAPI schema
- **Priority**: high
- **Effort**: s
- **Description**: CLI: generate TS client, integrate into Next.js. Verify type safety.
- **Dependencies**: 4.3.1, 4.4.1

### 4.6 Preference Editor Page
- **Task**: 4.6.1 - UI for natural language preference input
- **Priority**: high
- **Effort**: m
- **Description**: Form: description textarea, city selector. Save/edit/delete. Real-time preview (soft-filter count).
- **Dependencies**: 4.4.1

### 4.7 Listings Page
- **Task**: 4.7.1 - Map view + listing card grid with scores
- **Priority**: high
- **Effort**: l
- **Description**: MapLibre GL + react-map-gl for map. Card grid showing listings, price, score, explanation.
- **Dependencies**: 4.3.1, 4.4.1, 4.2.1

### 4.8 SSE Real-time Updates
- **Task**: 4.8.1 - sse-starlette backend + useEffect hook frontend
- **Priority**: high
- **Effort**: m
- **Description**: Backend: SSE endpoint pushes new listings. Frontend: useEffect subscribes, updates state.
- **Dependencies**: 4.3.1, 4.7.1

### 4.9 Filter UI + URL State
- **Task**: 4.9.1 - nuqs for shareable filter URLs (price, beds, neighborhood)
- **Priority**: normal
- **Effort**: m
- **Description**: nuqs integration: update URL on filter change. Shareable links restore filter state.
- **Dependencies**: 4.7.1

### 4.10 Saved Listings Feature
- **Task**: 4.10.1 - Star/save listings, export to CSV/JSON
- **Priority**: normal
- **Effort**: m
- **Description**: DB column for saved flag. Frontend: star button. Export endpoint.
- **Dependencies**: 4.3.1, 4.7.1

### 4.11 Cost Scoring Indicator
- **Task**: 4.11.1 - Show cost breakdown per listing (extraction, scoring)
- **Priority**: normal
- **Effort**: s
- **Description**: Display on listing card: "this match cost $0.003 to find + score".
- **Dependencies**: 4.7.1

### 4.12 Responsive Design + A11y
- **Task**: 4.12.1 - WCAG AA compliance, mobile responsive
- **Priority**: normal
- **Effort**: m
- **Description**: Tailwind responsive, keyboard navigation, alt text. axe testing.
- **Dependencies**: 4.7.1

---

## Phase 5: Cost Optimization & Dashboarding (9 tasks, ~40 hrs)

### 5.1 Cost Aggregation Logic
- **Task**: 5.1.1 - Parse structlog, group by component/model/city
- **Priority**: high
- **Effort**: m
- **Description**: Query cost DB. Aggregate: discovery, extraction T1, extraction T2, scoring. Time-series.
- **Dependencies**: 1.6.1

### 5.2 Cost Dashboard API
- **Task**: 5.2.1 - Endpoints: GET /api/costs, /api/costs/by-component, /api/costs/by-city
- **Priority**: high
- **Effort**: m
- **Description**: Cost endpoints for frontend. Filter by date range, city, component.
- **Dependencies**: 5.1.1

### 5.3 Cost Dashboard UI
- **Task**: 5.3.1 - Frontend charts (total spend, trends, breakdown by component)
- **Priority**: high
- **Effort**: m
- **Description**: Next.js page with Recharts. Show daily/weekly/monthly trends. Pie chart by component.
- **Dependencies**: 5.2.1, 4.4.1

### 5.4 Model Routing Decision Logic
- **Task**: 5.4.1 - Choose cheapest viable model for each task
- **Priority**: normal
- **Effort**: m
- **Description**: Logic: if task simple → Claude Mini. If needs reasoning → Claude 3.5. Track routing decisions.
- **Dependencies**: 1.6.1

### 5.5 Prompt Caching Verification
- **Task**: 5.5.1 - Measure cache hits/misses across discovery + extraction
- **Priority**: normal
- **Effort**: m
- **Description**: Log cache_hit flag for LLM calls. Verify prompt caching reducing tokens/cost.
- **Dependencies**: 1.6.1

### 5.6 Budget Alerts
- **Task**: 5.6.1 - Notify if spending exceeds limit (e.g., $5/month)
- **Priority**: normal
- **Effort**: s
- **Description**: Configurable budget. Alert in dashboard, log warning.
- **Dependencies**: 5.2.1

### 5.7 Performance Profiling
- **Task**: 5.7.1 - Identify hot paths (LLM calls, DB queries, API latency)
- **Priority**: normal
- **Effort**: m
- **Description**: Middleware: track endpoint latency. Query logs for slowest queries. Profile Python code.
- **Dependencies**: 1.5.1

### 5.8 Load Testing
- **Task**: 5.8.1 - Load test: 1000 listings, 5 concurrent cities
- **Priority**: normal
- **Effort**: m
- **Description**: Simulate concurrent users. Verify response times, memory, cost. Use locust or k6.
- **Dependencies**: 5.7.1

### 5.9 Cost Engineering Documentation
- **Task**: 5.9.1 - Write guide: cost breakdown, model routing, optimization tips
- **Priority**: normal
- **Effort**: s
- **Description**: Doc explaining <$1/month achievement. Tips for users. Dev guide for contributors.
- **Dependencies**: 5.1.1

---

## Phase 6: Polish, Security & Launch (13 tasks, ~50 hrs)

### 6.1 Security Audit
- **Task**: 6.1.1 - Dependency scanning, OWASP checks, penetration testing
- **Priority**: critical
- **Effort**: m
- **Description**: Run safety, bandit, OWASP ZAP. Fix 0 critical/high findings.
- **Dependencies**: All phases complete

### 6.2 API Key Rotation Strategy
- **Task**: 6.2.1 - Secure storage + rotation for OpenRouter, Apify keys
- **Priority**: high
- **Effort**: s
- **Description**: .env file, environment-based loading, key rotation procedure.
- **Dependencies**: 1.11.1

### 6.3 Input Validation Hardening
- **Task**: 6.3.1 - Pydantic strict mode, type validation at all boundaries
- **Priority**: high
- **Effort**: s
- **Description**: Audit Pydantic models. Ensure strict mode. Test injection attacks.
- **Dependencies**: 1.4.1

### 6.4 FastMCP Server Implementation
- **Task**: 6.4.1 - Expose 4-6 Doormat endpoints for external Claude agents
- **Priority**: normal
- **Effort**: m
- **Description**: MCP server: discovery endpoint, extraction status, listing scorer. Test with Claude.
- **Dependencies**: All API endpoints complete

### 6.5 MCP Integration Tests
- **Task**: 6.5.1 - Test external Claude agent calling Doormat MCP server
- **Priority**: normal
- **Effort**: m
- **Description**: Write test agent that calls MCP endpoints, verifies results.
- **Dependencies**: 6.4.1

### 6.6 README Complete
- **Task**: 6.6.1 - Setup, usage, architecture, cost explanation
- **Priority**: high
- **Effort**: m
- **Description**: README: quick start, Docker Compose setup, configuration, examples, cost breakdown.
- **Dependencies**: All phases complete

### 6.7 API Documentation
- **Task**: 6.7.1 - OpenAPI + mkdocstrings (auto-generated from code)
- **Priority**: high
- **Effort**: m
- **Description**: FastAPI generates OpenAPI. mkdocs + mkdocstrings for full API reference. Deploy to GitHub Pages.
- **Dependencies**: 6.6.1

### 6.8 CLAUDE.md Update
- **Task**: 6.8.1 - Document prompt patterns for other projects
- **Priority**: normal
- **Effort**: s
- **Description**: CLAUDE.md: discovery pattern, extraction generation, scoring loop. Reusable prompts.
- **Dependencies**: All prompts finalized

### 6.9 Skills Bundle Creation
- **Task**: 6.9.1 - Package for Copilot/Claude Desktop integration
- **Priority**: normal
- **Effort**: m
- **Description**: Skills: /doormat-discover-city, /doormat-score-listings. JSON + prompts.
- **Dependencies**: 6.8.1

### 6.10 Performance Profiling (Final)
- **Task**: 6.10.1 - Final performance audit: response times, memory, CPU
- **Priority**: normal
- **Effort**: m
- **Description**: Measure: API response times (p50, p95, p99), memory peak, CPU sustained.
- **Dependencies**: 5.8.1

### 6.11 Changelog + Versioning
- **Task**: 6.11.1 - Conventional Commits, release-please automation
- **Priority**: normal
- **Effort**: s
- **Description**: Configure release-please. Write changelog. Semantic versioning.
- **Dependencies**: All phases complete

### 6.12 Launch Checklist
- **Task**: 6.12.1 - Release notes, demo video, announcement
- **Priority**: normal
- **Effort**: m
- **Description**: Draft release notes, link demo video, prepare social announcement.
- **Dependencies**: All tasks complete

---

## Summary by Effort

| Effort | Count | Time |
|--------|-------|------|
| xs (<30 min) | 5 | 2.5 hrs |
| s (1-2 hrs) | 15 | 22.5 hrs |
| m (4-8 hrs) | 38 | 228 hrs |
| l (1-2 days) | 18 | 288 hrs |
| xl (2+ days) | 6 | 144 hrs |
| **Total** | **82** | **~685 hrs** |

**Estimate**: ~6-7 weeks at 40 hrs/week (as described in BUILD-GUIDE)

---

## Critical Path (Dependencies)

1. **Phase 1** → All infrastructure ready
2. **Phase 2** (depends on 1.1, 1.6) → Discovery agent working
3. **Phase 3** (depends on 2.4) → Extraction + scoring
4. **Phase 4** (depends on 3.5, 4.3) → Dashboard rendering
5. **Phase 5** (depends on 1.6, all cost tracking) → Cost dashboard live
6. **Phase 6** (depends on all) → Polish + launch

---

## Approval & Handoff

**Task Owner**: Doormat Project Lead  
**Approved**: 2026-04-25  
**Next Phase**: `/speckit.implement` (Start Building)

