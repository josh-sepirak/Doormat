# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What Doormat Is

AI-first rental finder. User describes their ideal place in natural language → autonomous agent discovers local property managers → generates scrapers → scores listings → surfaces matches. Single-user, self-hosted, BYOK (OpenRouter + Apify keys). No auth, no SaaS.

## Commands

```bash
# Setup (uses uv, not pip)
uv sync --extra dev

# Run dev server
uv run uvicorn doormat.main:app --reload --host 0.0.0.0 --port 8000

# Or via module
uv run python -m doormat.main

# Docker (production-like)
docker compose up

# Tests
uv run pytest
uv run pytest tests/test_main.py          # single file
uv run pytest -k "test_health"            # single test

# Lint + format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type check
uv run mypy src/

# Migrations
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
uv run alembic downgrade -1
```

## Architecture

**Single FastAPI process** with SQLite + WAL. All in one Docker container.

```
src/backend/doormat/
├── main.py          # FastAPI app, lifespan, CORS, metrics middleware
├── config.py        # Pydantic Settings (reads .env, env vars)
├── schemas.py       # All Pydantic I/O schemas
├── models/orm.py    # SQLAlchemy 2.0 ORM (Mapped[T] typed columns)
├── db/base.py       # DeclarativeBase
├── logging_config.py  # structlog (JSON prod, console dev)
├── metrics.py       # Prometheus counters/gauges
├── cost_tracking.py # Per-LLM-call cost recording
├── retry.py         # tenacity retry helpers
└── api/             # FastAPI routers (not yet built out)
```

**Planned subsystems** (from BUILD-GUIDE.md):
1. **Preference extraction** — chat+form → structured `PreferenceProfile`
2. **City discovery agent** — Browser-Use → finds property managers, caches extraction strategies
3. **Listing extraction** — Mode A (deterministic) → Mode B (Browser-Use agentic fallback)
4. **Soft-preference scoring** — embedding pre-filter + LLM scoring with explanation
5. **Conversational refinement** — sidebar chat with tool use

**LLM**: `openai` SDK pointed at OpenRouter (BYOK). `instructor` for structured outputs. Tiered model routing for cost control.

**Storage**: SQLite default (swap to Postgres via `DATABASE_URL`). `sqlite-vec` for embeddings.

**Scheduler**: APScheduler in-process (pin `<4`).

**MCP server**: FastMCP exposing `search_listings`, `get_listing`, `explain_score`, `trigger_scrape`.

**Frontend** (not yet built): Next.js 15 App Router + Tailwind UI + shadcn/ui. TypeScript client auto-generated from OpenAPI via `@hey-api/openapi-ts`.

## Key Conventions

- **Python 3.13**, strict mypy, Ruff (line-length 100)
- SQLAlchemy 2.0: always use `Mapped[T]` typed columns, not bare `Column()`
- Alembic migrations use `render_as_batch=True` (SQLite ALTER TABLE workaround)
- All env vars in `config.py` via `pydantic-settings`; no `os.environ` elsewhere
- structlog everywhere — `get_logger("doormat.module_name")`, never `print`/`logging.getLogger`
- All LLM calls go through `LLMClient` Protocol (cost tracking, caching, retries baked in)
- `asyncio_mode = "auto"` in pytest — all test coroutines run automatically
- Migrations live in `alembic/versions/`, not `migrations/`

## Environment Variables

Copy `.env.example` to `.env`. Required for LLM features:
- `OPENROUTER_API_KEY` — LLM calls via OpenRouter
- `APIFY_API_TOKEN` — anti-bot fallback for protected aggregators

Optional:
- `DATABASE_URL` — defaults to `sqlite+aiosqlite:///./doormat.db`
- `DEBUG`, `LOG_LEVEL`, `LOG_FORMAT`

### Feature Flags (Phase E)

**API Recipe (Mode A0) — Zero-cost extraction**:
- `API_RECIPE_ENABLED` — Enable Mode A0 fast path (default: `False`). Set to `True` to skip Mode A/B for JSON APIs once recipes are validated.
- `API_RECIPE_PROMOTION_REQUIRES_HELD_OUT` — Require held-out listing validation before merging recipes (default: `True`). Set to `False` to promote recipes on Mode B success alone.
- `API_RECIPE_EXECUTION_TIMEOUT` — Timeout for Mode A0 HTTP calls in seconds (default: `10`).
- `API_RECIPE_MAX_CONSECUTIVE_FAILURES` — Max consecutive failures before retiring a recipe (default: `3`).
- `MODE_B_NETWORK_CAPTURE` — During Mode B, subscribe to CDP Network events and record same-origin JSON/XHR responses for observability (default: `True`). Set `False` to disable.
- `MODE_B_NETWORK_CAPTURE_WAIT_S` — Max seconds to wait for CDP before giving up on installing listeners (default: `30`).

**Rollout sequence**:
1. Start with all flags off — baseline behavior unchanged
2. After recipes accumulate (50+ validated per source), set `API_RECIPE_ENABLED=True` in dev
3. Once soak test passes (extraction success rate maintained), enable globally
4. Later: set `API_RECIPE_PROMOTION_REQUIRES_HELD_OUT=False` for faster refinement when desired

## Design Context

### Users
Solo developer self-hosting to automate their own rental search. Sets it up once, returns to see results. Stressed about housing — the tool should feel like a relief.

### Brand Personality
**Warm, capable, quiet.** Like Notion or Loom: human, clear, a little personality in the small moments. Not startup-bold, not enterprise-cold. The name is self-deprecating on purpose.

### Aesthetic Direction
Clean, warm-minimal, type-led. Inter body + Lexend display. Blue-600 (`#2563EB`) as sole accent; everything else is slate. Rounded-2xl cards, subtle borders, no harsh shadows.

**Both light and dark mode** (system preference). Dark: deep slate, not pure black, same blue-600 accent.

Anti-reference: no neon AI-startup gradients, no heavy enterprise sidebars.

### Design Principles
1. **Trust through clarity** — status always legible; user always knows what's running
2. **Confidence without anxiety** — "it's working, step away" not "watch me carefully"
3. **Warmth in the margins** — personality in empty states and micro-copy, not flashy visuals
4. **Dark mode as equal citizen** — both themes intentionally designed
5. **Personal, not enterprise** — one person's housing search; no unnecessary chrome
