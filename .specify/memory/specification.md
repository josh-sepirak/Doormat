# Doormat Specification

**Version**: 2.0  
**Created**: 2026-04-25  
**Last reconciled**: 2026-05-02  
**Status**: Approved — success criteria below track **delivery on `main`**

---

## Executive Summary

**Doormat** is an AI-first rental finder where users describe their dream place in natural language, provide a city, and an autonomous agent discovers local property managers, generates working scrapers for them, pulls listings, scores them against the user's preferences, and surfaces personalized matches with explanations.

**Target User**: Renters seeking a self-hosted, cost-optimized rental search tool that respects their privacy and owns their data.

**Key Differentiator**: Autonomous scraper generation via LLM + two-tier extraction with feedback loops, all running locally for <$1/month.

---

## Functional Requirements

### F1. Natural Language Preference Input
- User describes dream rental in plain English (e.g., "Modern 2-bed in downtown near tech district, under $2000, walkable neighborhood")
- System stores preference as searchable, queryable criteria
- User can save, edit, and manage multiple preference profiles

### F2. Autonomous City Discovery Agent
- Agent autonomously discovers property managers in a specified US city
- Browser-Use orchestrates discovery: searches public directories, validates candidates
- Detects legitimate property management orgs (not spam, duplicates, or spam)
- Caches discoveries per city to avoid re-discovery on future runs
- **Demo capability**: 90-second video showing agent bootstrapping a working system in a new city

### F3. Scraper Generation
- LLM generates working extraction strategies for each property manager website
- Strategy includes: login flow, listing URLs, field extraction patterns, pagination handling
- Strategies are cached and reused across multiple runs
- Feedback loops: if extraction fails, agent refines strategy iteratively

### F4. Two-Tier Extraction Pipeline
- **Tier 1 (Fast)**: Cheap model + structured output extracts listings from property manager sites
- **Tier 2 (Validation)**: Stronger model validates extracted data; catches errors; prompts refinement
- Cost-optimized: Tier 1 runs on 95% of listings; Tier 2 validates edge cases

### F5. Listing Scoring & Personalization
- **Embeddings pre-filter** (sqlite-vec + preference embedding gate): *planned — not enabled in production build today* (see `specs/006-portfolio-pitch-completion/spec.md`).
- Scoring agent ranks listings against user preferences with explanation
- Scores visible: cost vs. budget, features vs. wants, location fit
- Explanations: why this match, why not that one

### F6. Real-time Dashboard
- Next.js frontend renders: map view, listing cards, saved filters, preference editor
- Real-time updates via SSE (Server-Sent Events) as new listings arrive
- URL state: shareable filters via query strings (nuqs / TanStack Query are **optional** upgrades; native `URLSearchParams` patterns exist today)
- Maps: **Leaflet** + react-leaflet (vendor-light; differs from original MapLibre sketch)

### F7. Cost Tracking Dashboard
- Live visibility into spending per component (discovery, extraction, scoring, API calls)
- Cost per city, cost per listing, cumulative spend
- Historical trends: cost efficiency improvements
- Alerts: if spending exceeds budget
- Goal: all users run under $1/month for typical use

### F8. Data Ownership & Privacy
- No hosted SaaS; no signup; no auth wall by default (localhost-bound)
- Single-user only: no multi-user support
- All data stored locally (SQLite + WAL on named volume)
- Optional: bearer token auth for self-hosters who expose over network
- User supplies own API keys (OpenRouter for LLM, Apify for anti-bot fallback)

### F9. Multi-City Support
- User can run discovery in multiple cities sequentially
- Caching: scrapers, property manager lists, extraction strategies reused
- No re-discovery of same managers across cities (shared registry)

### F10. MCP Server Integration
- FastMCP server exposes doormat capabilities for integration into other Claude agents
- Agents can trigger discovery, generate scrapers, pull listings, score results
- Enables third-party agent workflows (e.g., "find rentals for all my friends")

---

## Non-Functional Requirements

### NR1. Performance
- Discovery agent completes per city in < 2 minutes (90-second demo target)
- Extraction: 1000 listings processed in < 5 minutes (tier 1) + < 2 minutes (tier 2 validation)
- Dashboard responsive: map pan/zoom instant, filter updates < 1 second

### NR2. Cost Discipline
- Typical user (1 city, 30 property managers, 300 listings): < $1/month
- Breakdown: discovery $0.03, extraction $0.02, scoring $0.01 (example)
- Model routing: small models (Claude Mini) for extraction, GPT-4 for validation only
- Prompt caching: reuse discovery + extraction strategies across runs

### NR3. Reliability & Error Handling
- Extraction failures: agent retries with refined strategy (feedback loop)
- Rate limiting: respect robots.txt, rate limits per property manager
- Network errors: graceful degradation, cache fallback, manual override option

### NR4. Observability
- All LLM calls logged with tokens, cost, latency
- Structured logging (structlog JSON in prod, console in dev)
- Prometheus metrics: `/metrics` endpoint
- Cost dashboard aggregates logs in real-time

### NR5. Simplicity & Maintainability
- Avoid frameworks: bare LLM loops where appropriate
- No LangChain/PydanticAI overhead; httpx + tenacity for retries
- Frontend: minimal dependencies (Next.js + Tailwind + Headless UI in current tree)
- Code is debuggable: structured logs link errors to costs

---

## User Workflows

### Workflow 1: First-Time Setup
1. User runs `docker compose up`
2. Local dashboard opens at localhost:3000
3. User enters OpenRouter API key + (optional) Apify key
4. User creates preference profile (natural language description)
5. User selects a city
6. Agent discovers property managers (2 min)
7. Scrapers generated (1 min)
8. Listings flow in real-time via SSE
9. User reviews matches, clicks saved listings

### Workflow 2: Update Preferences
1. User opens dashboard, clicks "Edit Preferences"
2. Natural language updated (e.g., add "pet-friendly, no noise above 85dB")
3. System re-scores all cached listings
4. Updated rankings appear in real-time
5. New matches highlighted

### Workflow 3: Explore Another City
1. User selects new city
2. System checks if property managers already discovered (cache hit)
3. If cache miss: discovery agent runs (2 min)
4. Scrapers re-used from previous runs (if same property manager)
5. New listings flow in; cost shown on dashboard

### Workflow 4: Agent Integration (MCP)
1. External Claude agent calls: "Find 2-bed rentals in SF for me"
2. Doormat MCP server: triggers discovery + extraction
3. Results returned structured (Pydantic models)
4. External agent: summarizes results, sends via email

---

## Success Criteria

### MVP (Phases 1–3)

| Criterion | Status |
|-----------|--------|
| Discovery finds property managers in a city with validation + caching | [x] |
| Scraper / strategy generation works across heterogeneous PM sites (ongoing quality work) | [x] core; [ ] formal “3+ archetypes” sign-off |
| Extraction pipelines: fast path + validation / recovery (Modes A, A0 when enabled, B) | [x] |
| Cost tracking visible in logs and APIs | [x] |

### Production (Phases 4–6)

| Criterion | Status |
|-----------|--------|
| Dashboard renders; filters and map usable | [x] |
| Real-time SSE listing stream | [x] |
| Cost dashboard accurate; **<$1/mo** typical use | [x] visibility; [ ] SLO proof for every workload |
| MCP server present; **tested with external Claude agent** | [x] code; [ ] formal external smoke |
| Security audit (third-party or equivalent checklist) | [ ] |
| Documentation: README, `CLAUDE.md`, `specs/`, contributor paths | [x] |
| Skills / contributor bundles for agent workflows | [x] |

---

## Constraints & Assumptions

### Constraints
- **Single-user only**: No multi-user auth, multi-tenancy, or concurrency
- **US rentals only**: Scraper strategies optimized for US property management sites
- **Local storage**: No cloud sync; user manages backups
- **Rate limiting**: Respects robots.txt + rate limits (no aggressive scraping)

### Assumptions
- Users have OpenRouter API key (can use free tier)
- Users have reliable internet connection
- Apify fallback is optional (self-hosters can skip)
- Users can run Docker Compose locally
- Browser-Use + LLM orchestration is faster than maintaining per-site custom scrapers

### Out of Scope
- Real estate platform (read-only consumer, not listing provider)
- Analytics/reporting (logs are the source of truth)
- Mobile app (web-first only)
- Multi-user SaaS (self-hosted single-user only)
- Integration with MLS (public listings only)

---

## Dependencies on Other Specifications

- **BUILD-GUIDE.md**: Architecture, tech stack, 6-week plan
- **CLAUDE.md**: AI agent patterns + prompt engineering standards
- **AGENTS.md**: MCP server integration + FastAPI schema exposure
- **Constitution**: 7 core principles + locked tech stack

---

## Approval & Handoff

**Specification Owner**: Doormat Project Lead  
**Approved**: 2026-04-25  
**Reconciled**: 2026-05-02  
**Next phase**: Feature delivery tracked in `specs/*/tasks.md`; this document sets product intent and high-level acceptance.

