# Doormat Constitution

An AI-first rental finder where agents autonomously discover property managers, generate working scrapers, and surface personalized listing matches. Self-hosted, BYOK, single-user, running on under $1/mo in LLM costs.

## Core Principles

### I. Cost Discipline
All LLM and inference spending is tracked, measured, and optimized. Decision-making prioritizes tiered model routing (small models for simple tasks, larger models only when needed), prompt caching, embeddings for pre-filtering, and batch operations. Cost visibility is a first-class feature, not an afterthought.

### II. Self-Contained & Single-User
The application is designed for single-user, self-hosted deployment. No auth walls, no signup, no hosted SaaS. Users own their data entirely and control infrastructure (local machine or $5 VPS). Deployment is via Docker Compose; data storage is local SQLite + WAL on a named volume, with Postgres as a transparent swap-in.

### III. Autonomous Agent Excellence
Browser automation agents are orchestrated deliberately: Browser-Use for web navigation and discovery, bare LLM loops for lighter tasks. Agents solve concrete problems: discovering property managers, validating candidates, generating working scrapers, extracting and scoring listings. Output is structured (Pydantic models) and validated at every boundary.

### IV. Production-Grade Prompt Engineering
Prompts are versioned, evaluated, and cached in source control. Extraction uses two-tier strategies: fast pass (cheap model + embedding pre-filter), then validation pass (stronger model). Feedback loops correct extraction errors iteratively. Performance is verified through evaluation harnesses.

### V. End-to-End Type Safety
FastAPI generates OpenAPI schemas; frontend uses `@hey-api/openapi-ts` to generate typed clients. Type mismatches fail the build. All I/O crosses Pydantic validators. mypy runs in strict mode in CI. Breaking API changes are caught before deployment.

### VI. Observability First
Structured logging via structlog (JSON in prod, console in dev). Metrics exposed at `/metrics` (Prometheus). A live cost dashboard shows spending across model calls, caches, and API usage. Errors are debuggable; structured traces link requests to their cost impact.

### VII. Simplicity Over Frameworks
Avoid unnecessary abstractions. Use standard libraries (httpx, tenacity, structlog) over bloated frameworks. Prefer bare LLM loops over LangChain/PydanticAI overhead. Backend is FastAPI + SQLAlchemy + Alembic; frontend is Next.js App Router with minimal dependencies. Fewer dependencies = faster understanding, faster iteration, lower surface area for bugs.

## Tech Stack (Locked)

**Backend:** Python 3.13, uv, Ruff (lint/format), mypy (strict), Pydantic v2, httpx, tenacity, FastAPI, SQLAlchemy 2.0 (typed), Alembic, sqlite-vec, APScheduler, structlog, instructor (structured outputs)

**Frontend:** Next.js 15 App Router, Tailwind UI, shadcn/ui, TanStack Query v5, nuqs, react-map-gl + MapLibre GL, @hey-api/openapi-ts (typed client generation)

**Deployment:** Docker (uv multi-stage, python:3.13-slim), GitHub Actions (matrix 3.12/3.13), release-please + Conventional Commits

**AI:** OpenRouter (200+ models via openai SDK), Browser-Use (automation), Apify (fallback anti-bot), Claude.md + AGENTS.md + FastMCP server (integration)

**Observability:** structlog (JSON + console), `/metrics` (Prometheus), live cost dashboard

**Docs:** MkDocs Material + mkdocstrings

## Quality Gates

- **Tests:** Unit tests for all business logic, integration tests for scraper validation and agent behavior. Test-first development: tests written, user approval, then implementation.
- **Linting:** Ruff enforces strict formatting; mypy strict mode mandatory in CI.
- **API Contracts:** OpenAPI generation catches schema drift; generated clients fail to build on type mismatches.
- **Cost Visibility:** Every LLM call, cache hit, and API charge is visible in logs and dashboards before deployment.
- **Prompt Versioning:** Prompts live in source control, evaluated before merge.

## Development Workflow

1. **Spec-Driven:** Requirements → specification → implementation plan → tasks → code.
2. **TDD:** Tests written first, user approval before implementation.
3. **Conventional Commits:** Feat/fix/docs/refactor with linked specs and cost impact analysis.
4. **CI/CD:** GitHub Actions matrix on 3.12/3.13, release-please automation.
5. **Documentation:** README + API docs auto-generated from code; CLAUDE.md for AI integration guidance.

## Security & Responsible Use

- No auth in single-user mode (localhost-bound by default); bearer token for self-hosters exposing over network.
- Scraping respects `robots.txt` and rate limits; never floods targets.
- Apache 2.0 license + patent grant (scrapers are protected).
- No hosting/selling listings; read-only consumer of public data.

## Governance

This Constitution supersedes all other development practices. It is the source of truth for architectural decisions, tool choices, and quality standards. All pull requests must verify compliance with cost discipline, type safety, observability, and prompt versioning requirements. Amendments require documentation and commit-history transparency.

**Version**: 1.0 | **Ratified**: 2026-04-25 | **Last Amended**: 2026-04-25
