# `doormat` — the complete build guide

Everything you need to build doormat from scratch, in one document. This
guide consolidates the entire architecture, all the prompts, all the
skills, the AI engineering decisions, the cost analysis, the six-week
plan, and the launch playbook.

This is the brief you hand to yourself or to Claude Code when you sit
down to build. Read it once end-to-end before you start coding. Refer
back to it section by section as you build.

---

## Table of contents

1. [Vision & positioning](#1-vision--positioning)
2. [The locked tech stack](#2-the-locked-tech-stack)
3. [Architecture overview](#3-architecture-overview)
4. [Prerequisites & setup](#4-prerequisites--setup)
5. [The repo structure](#5-the-repo-structure)
6. [Six-week build plan](#6-six-week-build-plan)
7. [The five AI subsystems](#7-the-five-ai-subsystems)
8. [Prompts library — full inline](#8-prompts-library--full-inline)
9. [Skills bundle — full inline](#9-skills-bundle--full-inline)
10. [The frontend](#10-the-frontend)
11. [Cost engineering](#11-cost-engineering)
12. [Testing strategy](#12-testing-strategy)
13. [CI/CD](#13-cicd)
14. [Launch playbook](#14-launch-playbook)
15. [The interview pitch](#15-the-interview-pitch)
16. [Appendix: troubleshooting & FAQ](#16-appendix-troubleshooting--faq)

---

## 1. Vision & positioning

**doormat** is an AI-first rental finder. The user describes their
dream place in plain English, gives doormat a city, and an agent
autonomously discovers local property managers, generates working
scrapers for them, pulls listings, scores them against the user's
preferences, and surfaces matches in a beautiful dashboard.

**It is single-user, self-hosted, and BYOK.** The user runs it on their
own machine or a $5 VPS, brings their own API keys (OpenRouter for the
LLM, Apify for protected aggregators), and owns all their data. There
is no hosted SaaS version. There is no signup. There is no auth wall.

**The flagship feature is the city-discovery agent.** When you give
doormat a new city, a Browser-Use-driven agent searches for property
managers in that area, validates each candidate, generates a working
extraction strategy for it, runs an initial scrape, and caches the
strategy for future runs. This is the "AI engineer" demo: a 90-second
video of an agent autonomously bootstrapping a working system in a
city it has never seen before.

**The audience is two-tiered:**

- **Engineers and AI tinkerers** clone the repo and run
  `docker compose up`. They get a beautiful local dashboard, an MCP
  server they can wire into Claude Desktop, a skills bundle they can
  install in their own Claude Code or Zo Computer, and a prompts
  library they can lift for their own projects.
- **Recruiters and senior engineers** read the README, the prompts
  directory, the architecture docs, and the cost-engineering section.
  They see end-to-end-typed contracts (FastAPI OpenAPI →
  hey-api-generated TS client), production-grade prompt engineering
  with versioned evals, two-tier extraction with feedback loops,
  cost dashboards, MCP integration, Browser-Use orchestration, and
  the AI engineering taste behind every choice.

**Origin story (this is also marketing):** doormat started as a Zo
Computer skill that I built to find an apartment in Redding,
California, in March 2026. After three weeks of iteration it was
working — emailing me twice a day with new listings and price drops.
Friends in other cities asked for it; the Zo skill didn't generalize.
So I rebuilt it as this open-source app: an AI agent autonomously
discovers property managers in any US city, generates scrapers for
them, surfaces personalized matches. The original skill ships in this
repo at `skills/doormat-mvp/` for users who want the lighter-weight
version.

**The interview pitch sentence:**

> *I built doormat, an AI-first rental finder where you describe your
> dream place in natural language and an agent autonomously discovers
> local property managers in any US city, generates working scrapers
> for them, and surfaces personalized matches with explanations. It's
> self-hosted, BYOK, and runs on under a dollar a month of LLM costs
> for typical use. The cost discipline is the engineering — tiered
> model routing, prompt caching, two-mode extraction with feedback
> loops, embedding pre-filter — all visible in the live cost
> dashboard.*

**What doormat is not:**

- Not a hosted service. (Use it locally.)
- Not multi-user. (Single user; self-hosted.)
- Not a real estate platform. (Read-only consumer of public listings.)
- Not a scraping farm. (Respects robots.txt; respects rate limits.)
- Not affiliated with any rental site.

---

## 2. The locked tech stack

Lock these now. Don't relitigate during build.

| Layer | Pick | One-line justification |
|---|---|---|
| Python | 3.13 | Mature, uv installs transparently |
| Packaging | uv (Astral) | Replaces pip + Poetry + pyenv + pip-tools in one binary |
| Lint + format | Ruff | Replaces Black + isort + flake8 + pyupgrade |
| Type checker | mypy strict in CI | Plus pydantic.mypy plugin |
| Validation | Pydantic v2 + pydantic-settings | At every I/O boundary |
| HTTP client | httpx async | Sync+async parity, HTTP/2 |
| Retries | tenacity | Industry standard, async-native |
| Logging | structlog (JSON in prod, console in dev) | Plays nicely with stdlib |
| Web framework | FastAPI | OpenAPI quality, AI-tool training depth |
| ORM | SQLAlchemy 2.0 typed (`Mapped[T]`) | Mature, async, plugin-friendly |
| Migrations | Alembic with `render_as_batch=True` | Only serious option |
| DB default | SQLite + WAL on a named volume | Postgres swap-in via `DATABASE_URL` |
| Vector store | sqlite-vec | Embeddings for soft-preference pre-filter; same DB |
| Scheduler | APScheduler 3.11 in-process | Pin `<4`; 4.x is alpha |
| Email | Resend (default) + SMTP fallback | Resend has 3k/mo free permanent |
| LLM client | `openai` SDK pointed at OpenRouter | One SDK, 200+ models, free tier support |
| Structured output | `instructor` | Pydantic-typed responses, retries on schema violations |
| Agent framework | Browser-Use for browser automation; bare LLM loops elsewhere | Avoid LangChain/PydanticAI overhead |
| Anti-bot | Apify-as-fallback (BYOK) | Drop self-hosted Playwright as default |
| Frontend | Next.js 15 App Router + Tailwind UI + shadcn/ui | Build-time impressive, runtime simple |
| Mapping | MapLibre GL + react-map-gl + MapTiler free tier | No vendor lock-in |
| Server state | TanStack Query v5 | Standard 2026 |
| URL state | nuqs | Filter URLs are shareable |
| Real-time | SSE via `sse-starlette` | One-way data, plain HTTP, browser-native |
| Typed client | `@hey-api/openapi-ts` with TanStack Query plugin | FE build fails on schema drift |
| Auth | None in single-user mode | Localhost-bound by default; bearer for self-hosters who expose it |
| Container | uv multi-stage Dockerfile, `python:3.13-slim` | `UV_LINK_MODE=copy`, cache mounts |
| Observability | structlog JSON + `/metrics` Prometheus | OTel deferred to v1.x |
| CI | GitHub Actions, matrix 3.12/3.13 | release-please + Conventional Commits |
| Docs | MkDocs Material + mkdocstrings + mike | Pure-Python toolchain |
| License | Apache 2.0 + NOTICE + Responsible Use README section | Patent grant matters for scrapers |
| AI integration | CLAUDE.md + AGENTS.md + `.claude/skills/` + FastMCP server | Project's strongest distinct positioning |

---

## 3. Architecture overview

```
┌───────────────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js 15 App Router + Tailwind UI + shadcn)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐      │
│  │Onboarding│ │Dashboard │ │ Listing  │ │  Sidebar │ │ Discovery   │      │
│  │  (chat)  │ │ (cards)  │ │ (detail) │ │   chat   │ │  progress   │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └─────────────┘      │
└────────────────────────────────┬──────────────────────────────────────────┘
                                 │ REST + SSE
┌────────────────────────────────▼──────────────────────────────────────────┐
│  FastAPI                                                                  │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  LLMClient (Protocol)                                               │  │
│  │  ├─ OpenRouter (default, BYOK, 200+ models incl. free tier)         │  │
│  │  ├─ Anthropic direct                                                │  │
│  │  ├─ OpenAI direct                                                   │  │
│  │  └─ Ollama (localhost, opt-in)                                      │  │
│  │  Wraps: cost tracking, prompt caching, instructor for structured    │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  Five AI subsystems:                                                │  │
│  │  1. Preference extraction (chat + form → PreferenceProfile)         │  │
│  │  2. City discovery agent (Browser-Use → adapters + listings)        │  │
│  │  3. Listing extraction (Mode A deterministic, Mode B agentic)       │  │
│  │  4. Soft-preference scoring + explanation (with embedding prefilter)│  │
│  │  5. Conversational refinement (sidebar chat with tool use)          │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  Sources:                                                           │  │
│  │  ├─ Aggregators (Apify): Zillow, Facebook Marketplace, Realtor opt-in│ │
│  │  ├─ Direct: Craigslist (per-city subdomain)                         │  │
│  │  └─ Local PMs: agent-discovered per city, cached strategies         │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  Storage:                                                           │  │
│  │  ├─ SQLite (listings, runs, strategies, eval results)               │  │
│  │  ├─ sqlite-vec (embeddings for preference pre-filter)               │  │
│  │  ├─ Volume photos/ (downloaded listing photos)                      │  │
│  │  └─ Volume cache/ (raw HTML for re-extraction debugging)            │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  APScheduler (in-process)                                           │  │
│  │  ├─ scrape (cron: twice daily)                                      │  │
│  │  ├─ digest (cron: 9am)                                              │  │
│  │  ├─ photo backfill (interval: every 5 min while pending > 0)        │  │
│  │  └─ strategy health check (daily)                                   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  FastMCP server (console-script entry point)                        │  │
│  │  ├─ search_listings tool                                            │  │
│  │  ├─ get_listing tool                                                │  │
│  │  ├─ explain_score tool                                              │  │
│  │  └─ trigger_scrape tool                                             │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────┘
```

The whole thing runs in one Docker container. Optional `--profile playwright`
adds a sidecar for users who want to opt into local headless browser
scraping instead of (or in addition to) Apify.

---

## 4. Prerequisites & setup

### What you need before you start

- macOS, Linux, or WSL2 on Windows. Native Windows is not supported.
- 16GB+ RAM, 20GB+ free disk.
- Git, GitHub CLI (`gh`), Docker Desktop or Docker Engine + Compose v2.
- A code editor with Claude Code (recommended), Cursor, or any
  AGENTS.md-aware IDE.

### Accounts you'll need

- **GitHub** — public repo, Actions, Pages for the docs site, GHCR
  for the container image.
- **OpenRouter** — sign up at openrouter.ai. Add $10 in credits to
  start; you can also use the genuinely-free models (DeepSeek V3,
  Llama 3.3 70B, Gemini Flash) without ever loading credits. Get
  your API key.
- **Apify** — sign up at console.apify.com. Free tier gives $5/mo in
  credit, enough for ~2500 Zillow + ~1000 FB Marketplace items.
  Get your API key.
- **Resend** — sign up at resend.com. Free tier is 3000 emails/mo.
  Verify your domain via DNS records (or use the default
  `onboarding@resend.dev` for testing). Get API key.
- **MapTiler** — sign up at maptiler.com. Free tier is 100k tile
  requests/mo. Get API key.
- **Tailwind UI license** ($300 once) — purchase at tailwindui.com.
  Yes, this is a real prerequisite; it's the design substrate.
- **PyPI** — for publishing. Set up Trusted Publishing via OIDC
  (no API token).

Total monthly cost at typical use: **$5-10** (Apify ~$5, OpenRouter
~$1-5 with paid models, $0 with free models). Plus the Tailwind UI
one-time $300.

### Tools to install

```bash
# uv — Python packaging
curl -LsSf https://astral.sh/uv/install.sh | sh

# pnpm — frontend packaging
npm install -g pnpm@latest

# vhs — terminal recording (for the README hero GIF)
brew install vhs        # macOS
# Or apt install vhs / download from charm.sh on Linux

# gh — GitHub CLI
brew install gh         # macOS
# Or per https://cli.github.com/

# pre-commit
uv tool install pre-commit
```

### Initial repo creation

```bash
# Create the repo locally, then push to GitHub
mkdir doormat && cd doormat
git init
gh repo create doormat --public --source=. --remote=origin --push
```

---

## 5. The repo structure

This is the layout you scaffold in week 1. Everything below assumes
this structure.

```
doormat/
├── pyproject.toml               # uv-managed, single source of truth
├── uv.lock
├── .python-version              # "3.13"
├── .pre-commit-config.yaml
├── .env.example                 # all env vars with dummy values
├── README.md
├── CLAUDE.md                    # symlinked → AGENTS.md
├── AGENTS.md                    # ≤80 lines
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── migrations/
├── src/
│   └── doormat/
│       ├── __init__.py
│       ├── __main__.py          # python -m doormat
│       ├── cli.py               # Typer CLI
│       ├── config.py            # Pydantic Settings
│       ├── logging.py           # structlog config
│       ├── exceptions.py        # custom exception hierarchy
│       ├── api/
│       │   ├── app.py
│       │   ├── deps.py          # Depends() injectors
│       │   ├── routers/
│       │   │   ├── listings.py
│       │   │   ├── runs.py
│       │   │   ├── filters.py
│       │   │   ├── discovery.py
│       │   │   ├── chat.py
│       │   │   ├── cost.py
│       │   │   └── events.py    # SSE
│       │   └── schemas.py
│       ├── db/
│       │   ├── base.py          # SA 2.0 DeclarativeBase
│       │   ├── session.py
│       │   └── models.py
│       ├── llm/
│       │   ├── client.py        # LLMClient Protocol + 4 impls
│       │   ├── prompts.py       # the loader
│       │   ├── caching.py       # prompt cache helpers
│       │   ├── tracking.py      # cost middleware
│       │   └── routing.py       # tiered model routing
│       ├── sources/
│       │   ├── _base.py
│       │   ├── _registry.py     # entry-point loader
│       │   ├── _http.py         # shared httpx client w/ rate limiting
│       │   ├── apify.py         # Zillow, FB, Realtor wrappers
│       │   ├── craigslist/
│       │   └── pm/              # agent-discovered, dynamic
│       ├── extraction/
│       │   ├── mode_a.py        # deterministic-first
│       │   ├── mode_b.py        # Browser-Use agentic recovery
│       │   ├── strategy.py      # cached strategies + validator
│       │   └── photos.py        # async photo download
│       ├── discovery/
│       │   ├── agent.py         # the city-discovery loop
│       │   ├── search.py        # web search tool
│       │   ├── classifier.py    # is-this-a-PM-site?
│       │   └── adapter_gen.py   # generates ExtractionStrategy
│       ├── scoring/
│       │   ├── hard.py          # SQL-driven hard filters
│       │   ├── embed.py         # sqlite-vec pre-filter
│       │   └── soft.py          # LLM scoring + explanation
│       ├── digest/
│       │   ├── compose.py
│       │   └── send.py
│       ├── chat/
│       │   ├── tools.py         # tool definitions
│       │   └── orchestrator.py
│       ├── scheduler/
│       │   └── jobs.py
│       ├── email/
│       │   ├── _base.py         # EmailSender Protocol
│       │   ├── resend.py
│       │   ├── smtp.py
│       │   └── ses.py
│       ├── mcp/
│       │   └── server.py        # FastMCP entry point
│       ├── domain/              # pure logic, no I/O
│       └── static/              # built SPA goes here
├── prompts/                     # versioned prompts (loaded at runtime)
│   ├── README.md
│   ├── STYLE.md
│   ├── _shared/
│   │   ├── system-preamble.md
│   │   └── output-contract.md
│   ├── extraction/
│   │   ├── listing-extraction.md       # the agentic-first one (v2)
│   │   └── photo-classifier.md
│   ├── discovery/
│   │   ├── pm-website-classifier.md
│   │   ├── adapter-generator.md
│   │   └── city-search.md
│   ├── scoring/
│   │   ├── fit-score-with-explanation.md
│   │   └── digest-summary.md
│   ├── preferences/
│   │   └── preference-extraction.md
│   └── refinement/
│       ├── filter-translator.md
│       └── listing-comparison.md
├── skills/                      # portable Anthropic Agent Skills
│   ├── README.md
│   ├── doormat-mvp/             # the original Zo skill, refactored
│   │   ├── SKILL.md
│   │   ├── references/
│   │   └── scripts/
│   ├── add-rental-source/
│   └── debug-failing-source/
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── html/                # scrubbed real HTML, per source
│   │   ├── sites/               # local mock sites for Mode B evals
│   │   └── cassettes/           # VCR.py
│   ├── unit/
│   ├── integration/
│   ├── prompts/                 # eval queries per prompt
│   └── sources/
├── web/                         # Next.js 15 SPA, independent package.json
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   └── src/
│       ├── app/                 # App Router pages
│       │   ├── layout.tsx
│       │   ├── page.tsx         # dashboard
│       │   ├── onboarding/
│       │   ├── listings/[id]/
│       │   ├── preferences/
│       │   └── discovery/[city]/
│       ├── components/          # shadcn/ui components + custom
│       ├── lib/
│       │   ├── api.ts           # generated by hey-api
│       │   ├── sse.ts           # SSE client
│       │   └── store.ts         # Zustand
│       └── styles/
├── docs/                        # MkDocs Material
│   ├── index.md
│   ├── getting-started.md
│   ├── architecture.md
│   ├── ai-engineers-guide.md    # the recruiter-facing one
│   ├── adding-a-source.md
│   ├── deployment/
│   │   ├── raspberry-pi.md
│   │   ├── hetzner.md
│   │   ├── fly.md
│   │   └── railway.md
│   └── adr/                     # MADR 4.0
├── .claude/
│   ├── settings.json            # team-shared hooks
│   ├── settings.local.json      # gitignored
│   ├── commands/
│   │   ├── scrape-test.md
│   │   └── release-checklist.md
│   ├── agents/
│   │   ├── source-validator.md
│   │   ├── cassette-refresher.md
│   │   └── docs-writer.md
│   └── hooks/
│       └── post-edit-format.sh
└── .github/
    ├── ISSUE_TEMPLATE/
    │   ├── bug.yml
    │   ├── new-source.yml
    │   └── feature.yml
    ├── PULL_REQUEST_TEMPLATE.md
    ├── workflows/
    │   ├── ci.yml
    │   ├── release-please.yml
    │   ├── docker.yml
    │   └── docs.yml
    └── dependabot.yml
```

---

## 6. Six-week build plan

The plan is calibrated for a focused, full-time-equivalent engineer
shipping 4–6 hours/day. Adjust if part-time. Each week ends with a
specific demo-able deliverable.

### Week 1 — Foundations & LLM abstraction

**Goal:** A Python project that can talk to any LLM via a unified
interface, with all the production-grade scaffolding in place.

**Deliverable:** `python -m doormat chat "what's the weather"` works
against any provider configured via env var, and `uv run pytest` runs
green on a stub test.

**Steps:**

1. `uv init doormat`. Set `requires-python = ">=3.13"` and
   `.python-version` to "3.13".
2. Install core deps: `uv add fastapi uvicorn[standard] httpx selectolax sqlalchemy[asyncio] alembic psycopg[binary] aiosqlite pydantic pydantic-settings tenacity structlog apscheduler typer resend fastmcp sse-starlette apify-client instructor browser-use openai sqlite-vec`.
3. Install dev deps: `uv add --dev ruff mypy pytest pytest-asyncio pytest-cov respx vcrpy syrupy hypothesis mkdocs-material mkdocstrings[python] mike`.
4. Configure `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]`
   in `pyproject.toml` (full config in §11).
5. Set up `.pre-commit-config.yaml` with ruff, mypy, and a fixture-PII
   scrubber check.
6. Write `src/doormat/llm/client.py` with the `LLMClient` Protocol and
   four implementations: OpenRouter, Anthropic, OpenAI, Ollama. Use
   the OpenAI SDK pointed at OpenRouter for the default; use native
   SDKs for the others.
7. Write `src/doormat/llm/tracking.py` — a wrapper that intercepts
   every LLM call and records (timestamp, prompt_name, model,
   prompt_tokens, completion_tokens, cached_tokens, cost_usd) into
   the `llm_calls` table. This is the data backing the cost
   dashboard.
8. Write `src/doormat/llm/prompts.py` — the prompt loader
   (specification in §8).
9. Write `src/doormat/config.py` — Pydantic Settings reading env
   vars and an optional `config.yaml` overlay.
10. Set up SQLAlchemy 2.0 + Alembic with the first migration:
    `users` (single row), `llm_calls`, `runs`. Migration script
    `migrations/env.py` configured for SQLite + Postgres.
11. Configure structlog (JSON in prod, console in dev). The dev
    config uses `rich` traceback formatting.
12. Write `src/doormat/cli.py` with Typer, expose `doormat chat`,
    `doormat doctor` (verifies API keys + DB), `doormat serve`
    (the FastAPI app).
13. Write a stub FastAPI app at `src/doormat/api/app.py` with `/health`,
    `/version`, and `/metrics` (Prometheus instrumentator).
14. Set up GitHub Actions CI: lint, typecheck, test on Python 3.12
    and 3.13. release-please workflow on main. Branch protection.
15. Write `.env.example` with every var documented.

**Common gotchas:**

- uv's `--locked` flag means CI won't install if `uv.lock` is stale.
  Get used to running `uv sync` and committing the lockfile.
- `mypy --strict` plus the Pydantic plugin will flag any missing type
  annotation. Don't use `# type: ignore` to silence it; fix the type.
- `instructor` patches the LLM client; if you've forgotten to wrap
  the client with `instructor.from_openai(...)`, structured calls
  will silently return strings.

### Week 2 — Preference + listing extraction

**Goal:** The backend can take a city + a preference string and
produce filtered, scored listings via aggregators only (no discovery
yet).

**Deliverable:** `doormat scrape --city "Asheville, NC"
--prefs "3bd, $2200 max, dog friendly"` outputs a JSON list of fit-
scored listings.

**Steps:**

1. Define schemas in `src/doormat/schemas/`:
   - `Listing`, `PetsPolicy`, `StrategyUpdate`, `ListingExtractionResult`
     (full definitions in §8)
   - `PreferenceProfile` with hard and soft fields
   - `FitScore` with reasoning, score, explanation, matched/missed lists
2. Write `src/doormat/extraction/mode_a.py` — deterministic extraction
   using cached strategies, calling the LLM only when selectors are
   missing for required fields. Bypass the LLM entirely for sources
   with full strategies.
3. Write `src/doormat/scoring/hard.py` — pure SQL hard filters.
4. Write `src/doormat/scoring/embed.py` — embedding-based pre-filter
   using `sqlite-vec`. Embed each listing's amenity+description on
   ingestion; embed the user's preference summary; cosine-rank to
   pre-filter to top 50% before scoring.
5. Write `src/doormat/scoring/soft.py` — soft preference scoring with
   the `fit-score-with-explanation.md` prompt.
6. Write `src/doormat/sources/apify.py` — generic Apify client that
   takes an actor slug + input and returns a list of dicts.
7. Implement Zillow + FB Marketplace adapters as Apify wrappers.
   Realtor adapter exists but `enabled: false` by default.
8. Write `src/doormat/sources/craigslist/` — direct httpx scraper
   with city-subdomain lookup table.
9. Hash-based dedup before extraction (use the existing `Listing.hash`
   approach — normalize address + bed/bath into a hash, skip if seen).
10. Wire the orchestrator: scrape → dedup → extract → filter → embed
    pre-filter → score → store. Each step is a function in the domain
    module; the orchestrator composes them.
11. Write the preference-extraction prompt
    (`prompts/preferences/preference-extraction.md`, full content in
    §8).
12. Write `src/doormat/cli.py scrape` command end-to-end.
13. Tests: snapshot tests for extraction (golden-file fixtures),
    property tests for the hash function and address regex, eval
    queries for both prompts run via `doormat prompt eval`.

**Common gotchas:**

- The embedding pre-filter is a v0.1 stretch goal. Ship without it
  initially; add it when the listings table has enough rows that
  scoring everything becomes noticeable cost. The threshold is
  about 200 new listings per scrape.
- Apify's "free tier resets" can fail mid-month. Wrap calls with
  tenacity retry and a 402 → empty-result graceful degrade.
- The Craigslist subdomain map is finite; precompute it from
  https://www.craigslist.org/about/sites and commit as YAML.

### Week 3 — Discovery agent (the flagship)

**Goal:** Type a city name, watch a Browser-Use agent autonomously
discover local property managers and generate adapters.

**Deliverable:** `doormat discover "Sacramento, CA"` streams progress
to terminal, ends with N working strategies in `strategies` table
and an initial scrape's worth of listings in `listings`.

**Steps:**

1. Set up Browser-Use via `uv add browser-use`. Install the Chromium
   binary: `uv run python -m playwright install chromium`.
2. Write `src/doormat/discovery/search.py` — a thin wrapper around an
   LLM web search. Use OpenRouter's web-search-enabled model variant
   (Perplexity Sonar or one of the search-capable Anthropic offerings)
   so we don't take a Tavily/Exa dependency.
3. Write the city-search prompt (`prompts/discovery/city-search.md`,
   full content in §8). It generates 10–20 candidate URLs from
   queries like "property management rentals [city]", "[city]
   apartment rentals owners", "rental listings [city] [state]".
4. Write the PM classifier prompt
   (`prompts/discovery/pm-website-classifier.md`). Takes a candidate
   URL + a small fetched preview, returns a `PMClassification` (is
   this a property manager? is this a rental aggregator? is this
   noise?). Run on Haiku — high volume, simple task.
5. Write `src/doormat/discovery/adapter_gen.py` — drives Browser-Use
   to navigate a candidate site, identify how listings are structured,
   sample 5 listings, generate an `ExtractionStrategy` with selectors
   + pre-extraction actions. Validate the strategy against the same 5
   listings before committing it.
6. Write the adapter generator prompt
   (`prompts/discovery/adapter-generator.md`, full content in §8).
   This is the biggest prompt in the system.
7. Write `src/doormat/discovery/agent.py` — the orchestrator that
   stitches it all together: search → classify → for each PM:
   adapter_gen → validate → store. Stream events via an
   `asyncio.Queue` for SSE consumption.
8. Cache strategies in the `extraction_strategies` table, keyed by
   `(source_id, schema_version)`.
9. SSE endpoint: `GET /api/v1/discovery/{city}/events` — streams
   progress events to the frontend.
10. CLI: `doormat discover "City, ST"` runs the same loop and pretty-
    prints events to terminal.

**Common gotchas:**

- Browser-Use's `use_vision=True` is tempting but expensive. Default
  to vision-off; only let the agent request a screenshot when
  explicitly justified in its plan.
- Pages with cookie banners block extraction. Pre-extraction actions
  should include "if there's a cookie accept button, click it."
- Some PM sites are hostile to non-residential IPs (rare for small
  PMs, common for the big aggregators which we already route through
  Apify). If discovery fails on a candidate after 2 navigation
  retries, mark it dead and move on.
- The discovery agent is the most expensive part of doormat. Cap
  total token budget per discovery run via the cost-tracking
  middleware (default $5; if exceeded, emit a `budget_exceeded`
  event and stop, returning whatever strategies are already saved).

### Week 4 — Frontend

**Goal:** A working, beautiful dashboard for the user.

**Deliverable:** Screen recording of the full user flow — onboarding
→ city setup with discovery progress → dashboard with listings →
clicking into a listing → using the sidebar chat.

**Steps:**

1. `pnpm create next-app web --typescript --tailwind --app` (Next.js
   15 App Router).
2. Install Tailwind UI, copy the templates you'll use into
   `web/src/components/templates/`. The four screens map to specific
   templates (§10).
3. Install shadcn/ui CLI, scaffold base components.
4. Install TanStack Query v5, Zustand with `persist`, nuqs.
5. Configure `@hey-api/openapi-ts` to consume FastAPI's `/openapi.json`
   and emit a typed client + TanStack Query options into
   `web/src/lib/api.ts`. Wire a pnpm script:
   `"api:gen": "openapi-ts"`.
6. Build the four screens:
   - **Onboarding** (`/onboarding`) — two-pane chat + form, calls
     `POST /api/v1/preferences/extract` to convert chat input to
     structured `PreferenceProfile`; saves on submit.
   - **Dashboard** (`/`) — card grid using `useQuery` against
     `GET /api/v1/listings`. Photos prominent, score badges, fit
     explanation tooltips, sort controls.
   - **Listing detail** (`/listings/[id]`) — photo gallery with
     `next/image`, MapLibre map, score breakdown, sidebar chat.
   - **Preferences** (`/preferences`) — structured form with live
     count preview ("47 listings would match this filter").
   - **Discovery progress** (`/discovery/[city]`) — terminal-style
     animated event log consuming the SSE stream. This is the wow
     screen.
7. Build the discovery progress component carefully — it's the
   marketing demo. Use Framer Motion for the per-event entry
   animation. Each event type has its own icon + color.
8. Wire the FastAPI app to serve the built SPA from
   `src/doormat/static/` at the root path; `pnpm build && cp -r web/dist
   src/doormat/static/`.
9. The Dockerfile (§10) bakes the SPA in at build time.

**Common gotchas:**

- Tailwind UI templates are React but not always shadcn-shaped. Plan
  to spend time adapting them to your component system. Budget half
  a day per template.
- MapLibre rendering inside a flexbox container needs explicit
  `width: 100%; height: 100%` plus `mapRef.current?.resize()` in a
  `ResizeObserver`. This bites every map integration.
- SSE in Next.js requires App Router server components or a client
  `EventSource`. Use `EventSource` directly; the `sse-starlette`
  endpoint is plain HTTP, no special client SDK needed.
- The `next.config.ts` needs to whitelist the FastAPI host's images
  domain *and* allow loading from the local FastAPI instance during
  dev. Use `output: "export"` at build time so the static bundle
  drops into FastAPI cleanly.

### Week 5 — Polish, AI features, packaging

**Goal:** Production-grade docker-compose-up experience.

**Deliverable:** `docker compose up`, open localhost:8000, complete
flow works for a fresh user.

**Steps:**

1. Implement the conversational refinement chat (sidebar, tools list
   in §7). Tool definitions: `update_filter`, `get_listing`,
   `similarity_search`, `explain_score`.
2. Implement daily summary email generation
   (`prompts/scoring/digest-summary.md`). Wire to APScheduler.
3. Build the cost dashboard widget. SQL view over `llm_calls`
   grouped by `prompt_name`, `model`, `day`. Component: line chart
   of daily spend + breakdown table.
4. Multi-stage Dockerfile (full content in §10). Test build locally;
   image should be <500MB.
5. `docker-compose.yml` with one service for the app, optional
   `playwright` profile for power users (also in §10).
6. Railway one-click deploy template (`railway.json`).
7. Fly.io deploy config (`fly.toml`).
8. Build the FastMCP server. Console-script entry point in
   `pyproject.toml`. Document the Claude Desktop config snippet in
   `docs/mcp.md`.
9. Configure prompt caching globally — it's enabled per-prompt via
   the frontmatter; the loader sets the right flag based on model.
10. Drop the prompts into `prompts/`. All five subsystems' prompts
    are written; they live as markdown files (full content in §8).

**Common gotchas:**

- Prompt caching has different mechanics across providers. Anthropic
  uses cache_control on individual content blocks; OpenAI caches
  prompts >1024 tokens automatically. Your loader has to handle both.
- The cost dashboard should round to 4 decimal places ($0.0008) at
  the per-call level and 2 at the daily aggregate ($0.32).
- Email rendering: ship as plain-text + HTML multipart. Use
  `premailer` to inline CSS in the HTML version.

### Week 6 — Launch

**Goal:** v0.1.0 publicly shipped.

**Deliverable:** GitHub release with a hero GIF, PyPI publish, public
demo deployed.

**Steps:**

1. README.md with origin story, hero GIF made via vhs, badges,
   60-second quickstart, MCP snippet, link to docs.
2. MkDocs site with the recruiter-facing
   `docs/ai-engineers-guide.md` page that walks through every AI
   subsystem with code references.
3. Three ADRs in `docs/adr/`:
   1. Two-mode extraction (Mode A deterministic + Mode B agentic)
   2. Apify-as-fallback over self-hosted Playwright
   3. APScheduler in-process over Celery+Beat
4. CONTRIBUTING.md with the "add a new source" walkthrough.
5. SECURITY.md with private vulnerability reporting.
6. Code of Conduct: Contributor Covenant 3.0.
7. `LICENSE` (Apache 2.0) + `NOTICE`.
8. Issue templates as YAML.
9. Tag v0.1.0; release-please opens the release PR; merge it; PyPI
   publishes via Trusted Publishing OIDC; Docker image pushes to
   GHCR.
10. Deploy a read-only public demo on Hetzner with synthetic data.
    Real listings would burn Apify credits and create legal exposure;
    synthetic is correct.
11. Launch posts:
    - **Show HN** with the headline *"I built doormat: an AI agent
      that finds rentals in any city by autonomously discovering
      local property managers."*
    - **r/Python** Showcase Saturday.
    - **r/selfhosted** weekly thread.
    - **awesome-python**, **awesome-mcp-servers**,
      **awesome-claude-code**, **awesome-selfhosted** PRs.
    - **Blog post**: *"How I built an autonomous rental-finder
      agent: from Zo Computer skill to AI-native open source."* The
      origin story is the strongest hook.
12. Triage feedback ruthlessly for two weeks. Resist feature creep.

---

## 7. The five AI subsystems

Each subsystem in detail. Read the prompts inline in §8.

### 7.1 Preference extraction

**Job:** Convert natural-language preference input into a structured
`PreferenceProfile`.

**Trigger:** User types in the onboarding chat OR edits the prefs page.

**Mechanics:**

```python
class HardFilters(BaseModel):
    city: str
    state: str
    rent_max: int = Field(ge=200, le=50_000)
    rent_min: int = Field(ge=0, default=0)
    bedrooms_min: int = Field(ge=0, le=20, default=0)
    bathrooms_min: float = Field(ge=0, le=20, default=0)
    pets_small_dog: bool = False
    pets_strict: bool = Field(
        default=False,
        description="True = require explicit yes; False = allow unknown.",
    )
    zip_allowlist: list[str] = Field(default_factory=list)

class SoftPreference(BaseModel):
    description: str = Field(max_length=200)
    weight: float = Field(ge=0, le=1)

class PreferenceProfile(BaseModel):
    hard_filters: HardFilters
    soft_preferences: list[SoftPreference] = Field(max_length=10)
    summary: str = Field(max_length=400)
    embedding: list[float] | None = None  # populated by embed step
```

The summary field is what `embed()` sees; it's a one-paragraph
human-readable rendition of all the prefs combined. Used for the
embedding pre-filter.

**Prompt:** `prompts/preferences/preference-extraction.md` (§8)

**Model:** Haiku 4.5 default, GPT-5-mini fallback. ~$0.001 per call.

### 7.2 City discovery agent

**Job:** Given a city + state, autonomously find local property
managers, generate working extraction strategies for them, and run
an initial scrape.

**Trigger:** User adds a new city in the onboarding flow, or the
`doormat discover` CLI command.

**Mechanics:** A multi-step agentic loop:

1. **Search.** LLM with web-search tool. Generate 10–20 candidate
   URLs from queries like *"property management rentals {city}"*,
   *"{city} apartment listings"*, *"rental homes {city} {state}"*.
   Prompt: `prompts/discovery/city-search.md`.
2. **Classify.** Per candidate, fetch a small preview, classify with
   Haiku as `property_manager`, `aggregator`, or `noise`. Prompt:
   `prompts/discovery/pm-website-classifier.md`.
3. **Adapter generation.** Per validated PM, drive Browser-Use to
   navigate the listings page, sample 5 listings, generate a typed
   `ExtractionStrategy` (CSS selectors per field, pre-extraction
   actions, photo selector strategy). Prompt:
   `prompts/discovery/adapter-generator.md`.
4. **Validate.** Run the generated strategy against the 5 sampled
   listings in deterministic Mode A. If 4/5 pass, commit the
   strategy. Else iterate up to 3 times, refining selectors based
   on failure modes.
5. **Cache.** Store the strategy in `extraction_strategies` table
   keyed by `(source_id, schema_version)`. Future scrapes use
   Mode A directly from cache.
6. **Initial scrape.** Run a first scrape against the new sources.
   Listings flow through the normal extraction → filter → score
   pipeline.

**Streaming:** Every step emits events to an asyncio queue. The SSE
endpoint streams them. The frontend renders them as a live terminal-
style log.

**Cost cap:** Default budget is $5 per discovery run, enforced by the
LLM tracking middleware. If exceeded, the agent stops cleanly and
returns whatever strategies it has.

**Models:** Sonnet 4.7 for the agent's reasoning + adapter generation
(it's where the smarts matter); Haiku 4.5 for the
classifier (high volume, simple task). Browser-Use's
`page_extraction_llm` is set to Haiku separately. Ollama-via-OpenRouter
is supported but discovery is meaningfully worse on local 70B models.
Document this.

### 7.3 Listing extraction (two-mode)

**Job:** Convert a single listing's HTML or URL into a typed `Listing`.

**Trigger:** Per new listing during a scrape, after dedup.

**Mechanics:** The two-mode design (full prompt in §8):

- **Mode A** (deterministic-first): pre-fetched HTML, cached strategy,
  ~$0.0008/listing on Haiku, prompt cached.
- **Mode B** (agentic recovery): URL + Browser-Use tools, ~$0.025/
  listing on Sonnet, fires for ~1% of listings, emits a
  `strategy_update` that improves Mode A for future calls.

**Validation gate:** Before merging a Mode B strategy_update into the
cached strategy, the runtime re-runs Mode A with the proposed strategy
on the most recent 5 listings from that source. If it doesn't improve
extraction confidence on at least 3 of them, the patch is logged and
discarded. This prevents one weird listing from poisoning the entire
source's strategy.

**Health monitoring:** The `extraction_strategies` table has a
`health_score` column updated nightly (success rate × recency). When
health drops below 0.5, the strategy is flagged for human review and
the source temporarily routes everything to Mode B until a fresh
strategy is generated.

### 7.4 Soft-preference scoring

**Job:** Score each filtered listing against the user's soft
preferences, with a one-sentence explanation.

**Trigger:** Per listing that passes hard filters, after the embedding
pre-filter has selected the top half.

**Mechanics:** Embedding pre-filter cuts cost dramatically. Without
it, scoring 300 listings × 1 LLM call = $0.30/run. With it, ~150
listings × 1 LLM call = $0.15/run.

```python
async def score_user_listings(
    user: User, listings: list[Listing]
) -> list[ScoredListing]:
    # Step 1: Hard filters via SQL — happened before this fn called.

    # Step 2: Embedding pre-filter
    pref_embed = await embed(user.preferences.summary)
    listing_embeds = await embed_batch([l.embedding_text for l in listings])
    scored = sorted(
        [(cosine(pref_embed, e), l) for e, l in zip(listing_embeds, listings)],
        reverse=True,
    )
    top_half = [l for _, l in scored[: max(20, len(scored) // 2)]]

    # Step 3: LLM scoring with explanation
    return await asyncio.gather(*[
        score_with_explanation(l, user.preferences) for l in top_half
    ])
```

The 20-minimum guarantees small-sample correctness in early-day cities
where the listings table has few rows.

**Prompt:** `prompts/scoring/fit-score-with-explanation.md`. Uses a
structured `reasoning` field as scratchpad CoT. Returns
`{score, explanation, matched_preferences[], missed_preferences[]}`.

**Tier badges:** Score-to-tier mapping in code, not in prompt:
- `score ≥ 0.85` → 🔥 hot
- `0.7 ≤ score < 0.85` → 👀 worth a look
- `score < 0.7` → 📋 standard

### 7.5 Conversational refinement

**Job:** Sidebar chat that lets the user refine filters, ask about
listings, or compare options.

**Trigger:** User types in the listing-detail page sidebar or the
dashboard's floating chat panel.

**Mechanics:** Tool-using LLM loop. Tools:

```python
@tool
def update_filter(
    field: Literal["amenities", "rent_max", "bedrooms_min", "bathrooms_min"],
    operation: Literal["set", "add", "remove"],
    value: Any,
) -> str:
    """Modify the user's active filter. Frontend invalidates the listings query."""

@tool
def get_listing(listing_id: int) -> Listing:
    """Fetch a listing by ID."""

@tool
def similarity_search(listing_id: int, top_k: int = 5) -> list[Listing]:
    """Find listings similar to the given one via embedding cosine."""

@tool
def explain_score(listing_id: int) -> FitScore:
    """Get the saved fit score + explanation for a listing."""
```

The orchestrator runs the standard LLM-with-tools loop, max 5 turns
per user message, max 8 tool calls. Streamed via SSE so the user
sees thinking happen.

**Prompt:** Lives in `prompts/refinement/sidebar-chat.md`. Concise
system prompt + dynamic context (current filter state + visible
listings as compact summaries).

---

## 8. Prompts library — full inline

This section contains the actual content of every prompt the system
ships with. Drop these into `prompts/` as-is.

### 8.1 `prompts/README.md`

```markdown
# `prompts/` — doormat's prompt engineering library

Every LLM call in doormat reads its prompt from this directory.
Prompts are versioned, testable, and model-portable.

## Why prompts live here, not in code

Prompts change faster than code. Tweaking a prompt to fix a regression
shouldn't require a Python deploy. The runtime loads prompts at request
time via `prompts.load("extraction/listing-extraction")`.

Prompts are reviewable artifacts. A senior engineer can audit doormat's
AI behavior without reading any Python. Every prompt has its rationale,
its eval queries, and its model-by-model notes in one place.

Prompts are the user-facing surface for power users. Anyone running
doormat against their own LLM (OpenRouter free models, local Ollama)
gets the same prompts the production app uses.

## Structure

prompts/
├── README.md                       # this file
├── STYLE.md                        # the conventions every prompt follows
├── _shared/
│   ├── system-preamble.md          # role + boundaries used by most calls
│   └── output-contract.md          # rules about uncertainty, refusal
├── extraction/
│   └── listing-extraction.md       # raw HTML → typed Listing (Mode A + B)
├── discovery/
│   ├── pm-website-classifier.md
│   ├── adapter-generator.md
│   └── city-search.md
├── scoring/
│   ├── fit-score-with-explanation.md
│   └── digest-summary.md
├── preferences/
│   └── preference-extraction.md
└── refinement/
    └── sidebar-chat.md

Each prompt is a single Markdown file with frontmatter, a `## System`
section, a `## User template` section with explicit `{{variable}}` slots,
a `## Output schema` section pointing at the Pydantic model, an `## Examples`
section with 2–3 canonical few-shot pairs, an `## Eval queries` section
with should-pass / should-fail cases, and a `## Notes` section.

## The principles every prompt follows

These are derived from Anthropic's published guidance on prompt and context
engineering, plus what the wider AI engineering community converged on in
2025–2026.

### 1. Context engineering, not just prompt engineering

Every token pays rent. We don't laundry-list edge cases; we curate 2–3
canonical examples that span the space.

### 2. Output contracts before instructions

The Pydantic schema *is* the contract. Field descriptions in
`Field(description=...)` do most of the work that prose used to do.

### 3. Role assignment with altitude

Every system prompt opens with a specific role. No "you are a world-class
expert" flattery — the modern models don't need it.

### 4. Reasoning as a structured field

Asking "think step by step" is the 2024 way. The 2026 way is to put
reasoning *into the output schema* as a field that comes *before* the
answer fields, so the model reasons before committing.

### 5. Few-shot with canonical examples, not exhaustive ones

Two to three examples per prompt: easy case, ambiguous case, edge case.

### 6. Uncertainty is a first-class output

Every schema includes a way for the model to say "I don't know" — `Maybe`
pattern, `OTHER` enum value, `Optional` field, or `confidence` literal.

### 7. XML for Claude, markdown sections everywhere else

Markdown headers as primary structure. The loader wraps relevant sections
in XML when targeting Claude.

### 8. No verbatim sensitive data

API keys, user PII, internal IDs — none of these go in prompt templates.
The loader injects them at call time.

### 9. Eval queries ship with every prompt

CI runs them against the prompt's recommended model on every PR. A prompt
change that drops eval pass rate fails the build.

### 10. Model-by-model notes are explicit

Each prompt's `## Notes` section calls out where it's been tested, where
it's known to fail, and what model is recommended.

## How prompts are loaded

```python
from doormat.llm import prompts, client

extract = prompts.load("extraction/listing-extraction", mode="A")
result = await extract(client, html=raw_html, source="hignell",
                       strategy_version=3)
# result is a typed ListingExtractionResult; validation already happened.
```

## How to contribute a new prompt

The `add-prompt` skill in `.claude/skills/add-prompt/` walks you through
creating one.

1. Define the schema as a Pydantic model in `src/doormat/schemas/`.
2. Copy `_shared/template.md` to a new file under the appropriate subdirectory.
3. Fill in role, user template, examples, eval queries.
4. Run `uv run doormat prompt eval extraction/your-new-prompt`.
5. Open a PR. CI runs the eval set across all configured models.

## Further reading

- Anthropic — Effective context engineering for AI agents
- Anthropic — Prompt engineering best practices
- Instructor — Prompt engineering best practices
```

### 8.2 `prompts/STYLE.md`

```markdown
# `prompts/STYLE.md` — conventions every prompt and skill follows

This document is the spec. Every prompt in `prompts/` and every skill
in `skills/` complies with it.

## File template

Every prompt file in `prompts/` is a single Markdown file with this
exact section order:

---
name: kebab-case-name
version: semver
schema: dotted.path.to.PydanticModel
recommended_model: <model-id>
fallback_models: [<id>, <id>, <id>]
prompt_cache: true|false
expected_input_tokens: <int>
expected_output_tokens: <int>
estimated_cost_usd: <float>
---

# Human-readable title

One-paragraph description of what this prompt does and where it sits
in the pipeline.

## System

The system message. No "you are an AI assistant" preamble. Open with
the role assignment.

## User template

The user message with `{{variable}}` slots. Variables must match
the keyword arguments the runtime passes to the loader.

## Output schema

A pointer to the Pydantic model and an inline excerpt for context.

## Examples

Two to three canonical input/output pairs. Use `<input>` and `<o>`
tags so the loader can extract them programmatically.

## Eval queries

A YAML block listing should-pass and should-fail cases that CI runs
against the prompt's recommended model on every PR.

## Notes

Anything else: model recommendations, prompt-cache behavior, known
failure modes, the changelog.

## Frontmatter rules

- `name` — kebab-case, must match the file path stem.
- `version` — semver. Bump on any change.
- `schema` — dotted path to the Pydantic model.
- `recommended_model` — the model this prompt was tuned on. CI evals
  run against this model.
- `fallback_models` — list of models tested and working, in preference
  order.
- `prompt_cache` — whether the loader sets the cache control flag.
- `expected_input_tokens` and `expected_output_tokens` — for cost
  forecasting.
- `estimated_cost_usd` — per-call cost on the recommended model with
  prompt cache hit.

## Versioning

- **Major** — schema changed in a breaking way, OR contract changed.
- **Minor** — added a field with default, refined system prompt, fixed
  known failure. Eval pass rate must not drop.
- **Patch** — typo fix, doc-only change.

Every version bump requires a CI eval pass.

## Required content rules

### Role assignment

The first sentence of every system prompt is the role. Specific, not
flattery.

### Reasoning fields

Prompts that need chain-of-thought put the reasoning in the schema as
a field that comes *before* the answer fields. The field is named
`reasoning` and is typed `str | None` with `default=None`.

### Uncertainty fields

Every extraction prompt's schema includes either a `confidence` literal
field, an `Optional` for fields that may not be present, or both.

### Few-shot examples

Two minimum, four maximum. Each example covers a distinct case.

### Eval queries

Minimum five queries: at least three should-pass, at least one
should-fail-gracefully, at least one explicit refuse-or-error case.

## Forbidden patterns

- "Think step by step" or any equivalent prose CoT instruction.
- "You are a helpful AI assistant" — pure token waste.
- "Be sure to..." / "Make sure you..." / "Don't forget to..."
- Exhaustive edge-case enumeration in the system prompt.
- Verbatim secrets, API keys, or user PII.
- Hidden chain-of-thought via "respond in JSON wrapped in a markdown block."
- Excessive role-play framing ("Imagine you are...", "Pretend to be...").

## CI enforcement

CI runs on every PR that touches `prompts/` or `skills/`:

1. Frontmatter validation
2. Naming validation
3. Eval queries pass
4. Skill description quality (length + trigger enumeration)
5. No forbidden patterns (regex grep)
6. Prompt-rendered length under declared budget +20%
```

### 8.3 `prompts/extraction/listing-extraction.md`

This is the agentic-first rewrite. Full content is in the
companion file `listing-extraction-v2.md` accompanying this guide.
The summary form to drop into the repo:

```markdown
---
name: listing-extraction
version: 2.0.0
schema: doormat.schemas.ListingExtractionResult
recommended_model_mode_a: claude-haiku-4-5
recommended_model_mode_b: claude-sonnet-4-7
fallback_models: [openai/gpt-5-mini, openai/gpt-5, deepseek/deepseek-v3]
prompt_cache: true
tools_required_mode_b: [browser_navigate, browser_get_dom, browser_click, browser_scroll, browser_screenshot]
---

# Listing extraction — agentic-first

Two-mode design:
- Mode A (deterministic-first, ~99% of calls, $0.0008/listing on Haiku)
- Mode B (agentic recovery via Browser-Use, ~1% of calls, $0.025/listing
  on Sonnet, emits strategy_update that improves Mode A)

[See full content in listing-extraction-v2.md companion file.]
```

### 8.4 `prompts/discovery/adapter-generator.md`

The single most important prompt in the system after listing-extraction.
Generates the cached `ExtractionStrategy` for a newly-discovered
property manager site.

```markdown
---
name: adapter-generator
version: 1.0.0
schema: doormat.schemas.ExtractionStrategy
recommended_model: claude-sonnet-4-7
fallback_models: [openai/gpt-5, anthropic/claude-opus-4-7]
prompt_cache: true
expected_input_tokens: 6000
expected_output_tokens: 800
estimated_cost_usd: 0.035
tools_required: [browser_navigate, browser_get_dom, browser_click, browser_scroll]
---

# Adapter generator

Generates a reusable `ExtractionStrategy` for a newly-discovered
property manager website. Runs once per (source, schema_version);
the resulting strategy is cached and used by Mode A extraction
indefinitely.

This is the single highest-impact agentic prompt in doormat. A good
strategy makes 1000s of subsequent listings extractable for ~$0.0008
each. A bad strategy means continuous Mode B fallback, costing ~$0.025
each. Be thorough.

## System

You are generating a reusable extraction strategy for a property
management website. You'll navigate the site, sample 5 listings,
identify the structural patterns, and emit a strategy that lets
deterministic code extract listings going forward.

Strategy emission is more important than getting the listings right.
The listings will be re-extracted by Mode A using your strategy. What
matters is that your strategy *generalizes* across the site's listings.

A good strategy:
- Uses stable selectors (semantic class names, data attributes, role
  attributes). Not auto-generated CSS-in-JS classes that change
  weekly.
- Has fallback selectors per field where reasonable (`[data-test=price],
  .listing-price, .price`).
- Includes pre-extraction actions (clicks, scrolls) that the runtime
  needs to execute before the DOM is queryable.
- Specifies how to find the photo gallery (often the trickiest part,
  due to lazy loading).
- Specifies the listing index URL pattern so the runtime can paginate.

A bad strategy:
- Hardcodes specific listing values you saw during sampling.
- Uses positional selectors (`:nth-child(3)`) that break if the layout
  varies.
- Skips the pre-extraction actions, hoping the page is fully rendered
  on initial load.
- Includes selectors for fields you weren't able to verify on sample
  listings.

Sample five listings before emitting the strategy. Verify each
selector returns the expected field on at least 3 of the 5 samples.
If a field's selectors don't pass that bar, omit them — Mode B will
recover for those fields, and the runtime will eventually generate a
better strategy. Better to emit a partial strategy that works
reliably than a complete strategy with brittle selectors.

If the site is unsuitable (login wall, redirects to an aggregator,
no listings), return an `ExtractionStrategy` with `valid: false` and
a `rejection_reason`. The runtime will mark the source as inactive.

## User template

Mode: discovery
Source candidate URL: `{{candidate_url}}`
Source name: `{{source_name}}`
City context: `{{city}}, {{state}}`

Generate a reusable extraction strategy for this site. Sample at
least 5 listings before emitting the strategy.

Available tools:

- `browser_navigate(url)` — load a URL.
- `browser_get_dom(selector?)` — return cleaned DOM.
- `browser_click(selector)` — click an element.
- `browser_scroll(direction, amount?)` — scroll.
- `browser_screenshot(region?)` — only if visual disambiguation is
  required.

Constraints:

- Budget: 25 tool calls.
- Stay on the source's domain.
- Never interact with login forms, payment forms, or "Apply" buttons.
- If the listings index is paginated, identify the pagination pattern
  but don't paginate during discovery (we only need to confirm the
  first page works).

## Output schema

class ExtractionStrategy(BaseModel):
    valid: bool = Field(description="False if site unsuitable")
    rejection_reason: str | None = None

    listing_index_url: str = Field(
        description="URL pattern for the listings index. {page} placeholder "
                    "if paginated. Example: 'https://acme-pm.com/rentals?page={page}'"
    )

    listing_link_selector: str = Field(
        description="CSS selector that, on the index page, matches anchor "
                    "tags whose href is a single-listing URL."
    )

    detail_pre_extraction_actions: list[str] = Field(
        default_factory=list,
        description="Actions to run on a listing page before extraction. "
                    "Examples: 'click button.show-amenities', 'scroll down 800', "
                    "'click .cookie-accept'."
    )

    field_selectors: dict[str, list[str]] = Field(
        description="Per-field selectors. Each field has a list of selectors "
                    "tried in order; first match wins. Required keys: address, "
                    "rent, bedrooms, bathrooms. Optional: sqft, pets_policy, "
                    "amenities, photos, description."
    )

    photo_gallery_strategy: PhotoGalleryStrategy = Field(
        description="How to find photo URLs. See sub-schema."
    )

    notes: str = Field(
        max_length=1000,
        description="Free-form notes about the source's quirks for the next "
                    "engineer reviewing this strategy."
    )

## Examples

[See actual prompt file in repo for full examples.]

## Eval queries

```yaml
- name: appfolio_site_strategy
  fixture_url: file://tests/fixtures/sites/appfolio-clone/index.html
  expect:
    valid: true
    field_selectors_has_keys: [address, rent, bedrooms, bathrooms]
    detail_pre_extraction_actions_length_at_most: 3

- name: login_wall_rejected
  fixture_url: file://tests/fixtures/sites/login-required/index.html
  expect:
    valid: false
    rejection_reason_contains: ["login", "auth"]
```

## Notes

This prompt costs ~$0.035 per discovery. The runtime caps total
discovery cost per city at $5 by default. If a city has 30 candidate
PMs, that's only ~$1 worth of generation calls — well under budget.

The strategy returned by this prompt is validated against 5 sample
listings before being committed to the cache. If 4/5 don't pass,
the strategy is regenerated up to 3 times with feedback on which
fields failed.

A strategy is considered "stable" once it's processed 50 listings
with >90% Mode A success. Below that threshold, the runtime tracks
it as "tentative" and runs Mode B in shadow mode (extracts in both
modes, compares, doesn't merge strategy_updates yet).
```

### 8.5 `prompts/preferences/preference-extraction.md`

```markdown
---
name: preference-extraction
version: 1.0.0
schema: doormat.schemas.PreferenceProfile
recommended_model: claude-haiku-4-5
fallback_models: [openai/gpt-5-mini, deepseek/deepseek-v3]
prompt_cache: true
expected_input_tokens: 800
expected_output_tokens: 400
estimated_cost_usd: 0.0006
---

# Preference extraction

Converts natural-language preference input into a typed
`PreferenceProfile` with hard filters and weighted soft preferences.

## System

You convert apartment-hunters' natural-language preferences into a
structured `PreferenceProfile`.

Hard filters are properties any acceptable listing must have:
budget, minimum bedrooms/bathrooms, pet requirements, ZIPs, city.
Don't infer hard filters that the user didn't state — better to
under-constrain and let them refine.

Soft preferences are everything that's "ideally" or "would prefer."
Each gets a weight 0–1 reflecting how strongly the user expressed it.
Strong language ("must have", "really need") = 0.8–1.0. Mild
preferences ("would be nice", "ideally") = 0.4–0.6. Casual mentions
= 0.2–0.4.

Pet handling is binary at the hard-filter level (`pets_small_dog`)
but soft at the weight level if the user expresses degree:
- *"I have a small dog"* → `pets_small_dog: true`, no soft pref.
- *"I have a small dog and a yard would be ideal"* → `pets_small_dog:
  true`, soft pref *"yard or large outdoor space"* weight 0.7.
- *"Pet-friendly is a nice-to-have"* → `pets_small_dog: false` (they
  don't actually have a pet), soft pref *"pet-friendly"* weight 0.4.

The summary field is your one-paragraph rendering of what you parsed,
in the user's voice. The frontend echoes this back as a "did I get
this right?" confirmation. Make it readable, not verbose.

## User template

User's natural-language preferences:

{{user_input}}

City: `{{city}}`
State: `{{state}}`

If city/state are not stated by the user and not present above, set
them to empty strings; the frontend will prompt for them separately.

## Output schema

class PreferenceProfile(BaseModel):
    reasoning: str | None = Field(default=None, max_length=300)
    hard_filters: HardFilters
    soft_preferences: list[SoftPreference] = Field(max_length=10)
    summary: str = Field(max_length=400)

class HardFilters(BaseModel):
    city: str
    state: str
    rent_max: int = Field(ge=200, le=50_000)
    rent_min: int = Field(ge=0, default=0)
    bedrooms_min: int = Field(ge=0, le=20, default=0)
    bathrooms_min: float = Field(ge=0, le=20, default=0)
    pets_small_dog: bool = False
    zip_allowlist: list[str] = Field(default_factory=list)

class SoftPreference(BaseModel):
    description: str = Field(max_length=200)
    weight: float = Field(ge=0, le=1)

## Examples

<input>
user_input: "I have a small dog and want a yard, ideally not on a busy street, near coffee shops, max $2800, two bedrooms minimum."
city: "Asheville"
state: "NC"
</input>

<o>
{
  "hard_filters": {
    "city": "Asheville",
    "state": "NC",
    "rent_max": 2800,
    "rent_min": 0,
    "bedrooms_min": 2,
    "bathrooms_min": 0,
    "pets_small_dog": true,
    "zip_allowlist": []
  },
  "soft_preferences": [
    {"description": "fenced yard or large outdoor space", "weight": 0.85},
    {"description": "quiet street, not on a major road", "weight": 0.65},
    {"description": "near coffee shops or walkable amenities", "weight": 0.5}
  ],
  "summary": "Asheville, NC, max $2,800/mo, 2+ bedrooms, must allow a small dog. Strong preference for a fenced yard. Prefers quiet streets and walkable to coffee shops."
}
</o>

<input>
user_input: "Just need somewhere cheap, doesn't matter where as long as it's in Sacramento."
city: "Sacramento"
state: "CA"
</input>

<o>
{
  "hard_filters": {
    "city": "Sacramento",
    "state": "CA",
    "rent_max": 0,
    "rent_min": 0,
    "bedrooms_min": 0,
    "bathrooms_min": 0,
    "pets_small_dog": false,
    "zip_allowlist": []
  },
  "soft_preferences": [
    {"description": "cheapest available", "weight": 1.0}
  ],
  "summary": "Sacramento, CA. Prioritizing the lowest available rent. No specific room or amenity requirements."
}
</o>

(Note: rent_max: 0 means "no upper bound configured." Frontend
detects this and prompts for a budget.)

## Eval queries

```yaml
- name: full_preference_input
  user_input: "I have a small dog and want a yard, ideally not on a busy street, near coffee shops, max $2800, two bedrooms minimum."
  expect:
    hard_filters.rent_max: 2800
    hard_filters.bedrooms_min: 2
    hard_filters.pets_small_dog: true
    soft_preferences.length_at_least: 2

- name: minimal_input
  user_input: "Just somewhere cheap in Sacramento."
  expect:
    hard_filters.rent_max: 0
    soft_preferences_includes_concept: ["cheap", "lowest", "affordable"]

- name: zip_extraction
  user_input: "Looking in 28801 or 28804, 3 bedrooms, $3000."
  expect:
    hard_filters.zip_allowlist: ["28801", "28804"]
    hard_filters.bedrooms_min: 3
    hard_filters.rent_max: 3000
```

## Notes

The summary field is the most important output of this prompt. The
frontend echoes it back to the user as confirmation. If the summary
isn't natural-sounding, the user loses trust. Spend tokens here.
```

### 8.6 `prompts/scoring/fit-score-with-explanation.md`

```markdown
---
name: fit-score-with-explanation
version: 1.0.0
schema: doormat.schemas.FitScore
recommended_model: claude-haiku-4-5
fallback_models: [openai/gpt-5-mini, deepseek/deepseek-v3, google/gemini-2.5-flash]
prompt_cache: true
expected_input_tokens: 1200
expected_output_tokens: 200
estimated_cost_usd: 0.0006
---

# Fit score with explanation

Scores a single listing against the user's soft preferences. Returns
a 0–1 score, a one-sentence explanation, and lists of matched/missed
preferences. Hard filters are not this prompt's job — they're applied
in SQL before this prompt sees the listing.

## System

You score how well a rental listing matches a user's soft preferences.

For each preference, decide whether the listing definitely matches
(add to `matched_preferences`), definitely misses (add to
`missed_preferences`), or is ambiguous from the listing's data
(don't list it either way).

The score is a weighted average:
- Each matched preference contributes its weight to the numerator.
- Each *expressed* preference (matched or missed) adds its weight to
  the denominator.
- Ambiguous preferences don't count either way.

So a listing that matches all expressed prefs scores 1.0. A listing
that misses all expressed prefs scores 0.0. A listing where every
preference is ambiguous scores 0.5 by convention (treat as neutral).

The explanation is one sentence. It should mention the strongest
matched preference and, when applicable, the most notable missed
preference. Don't enumerate everything — that's what the lists are
for. Aim for the *signal* a human would care about.

The reasoning field is your scratchpad. Use it when scoring is
ambiguous; skip it when obvious.

## User template

LISTING:
- Address: `{{address}}`
- Rent: `${{rent}}/mo`
- Beds/Baths: `{{bedrooms}}bd/{{bathrooms}}ba`
- Sqft: `{{sqft}}`
- Pets: `{{pets_policy}}`
- Amenities: `{{amenities}}`
- Description: {{description}}

USER PREFERENCES (each weighted 0–1):

{{soft_preferences_yaml}}

Score this listing.

## Output schema

class FitScore(BaseModel):
    reasoning: str | None = Field(default=None, max_length=300)
    score: float = Field(ge=0, le=1)
    explanation: str = Field(max_length=200)
    matched_preferences: list[str]
    missed_preferences: list[str]

## Examples

<input>
listing: { rent: 2350, bedrooms: 4, bathrooms: 2.5, sqft: 1615,
           pets_policy: "allowed_with_small_dog",
           amenities: ["yard", "garage", "solar"],
           description: "...newly built peaceful Redding neighborhood..." }
soft_preferences:
  - { description: "fenced yard or large outdoor space", weight: 0.85 }
  - { description: "quiet street", weight: 0.65 }
  - { description: "near coffee shops", weight: 0.5 }
</input>

<o>
{
  "score": 0.74,
  "explanation": "Strong yard match in a peaceful neighborhood; can't tell from the listing whether it's near coffee shops.",
  "matched_preferences": ["fenced yard or large outdoor space", "quiet street"],
  "missed_preferences": []
}
</o>

(Score arithmetic: matched = 0.85 + 0.65 = 1.5; total expressed
weight excluding the ambiguous coffee-shops pref = 0.85 + 0.65 = 1.5;
score = 1.5 / 1.5 = 1.0. But the user has 3 prefs total, and
"near coffee shops" is ambiguous, so we use partial credit:
1.5 / (0.85 + 0.65 + 0.5) = 0.74.)

<input>
listing: { rent: 1800, bedrooms: 2, bathrooms: 1, sqft: null,
           pets_policy: "none_allowed",
           amenities: [],
           description: "Charming bungalow downtown." }
soft_preferences:
  - { description: "fenced yard", weight: 0.8 }
  - { description: "pet-friendly", weight: 0.7 }
  - { description: "downtown location", weight: 0.6 }
</input>

<o>
{
  "reasoning": "No mention of yard; pet-friendly is explicitly false; downtown matches the description.",
  "score": 0.29,
  "explanation": "Downtown match, but no pets allowed and no yard mentioned.",
  "matched_preferences": ["downtown location"],
  "missed_preferences": ["pet-friendly"]
}
</o>

(0.6 / (0.8 + 0.7 + 0.6) = 0.29; the yard preference is ambiguous
because the listing doesn't mention yard either way.)

## Eval queries

```yaml
- name: all_match
  fixture: tests/fixtures/scoring/all-match.json
  expect:
    score_at_least: 0.9
    matched_preferences_length_at_least: 3

- name: clear_miss
  fixture: tests/fixtures/scoring/no-pets-vs-pet-required.json
  expect:
    score_at_most: 0.4
    missed_preferences_includes: ["pet-friendly"]

- name: ambiguous_treated_neutral
  fixture: tests/fixtures/scoring/ambiguous.json
  expect:
    score_between: [0.4, 0.6]
```

## Notes

This is the highest-volume scoring call after extraction. Cache the
system prompt aggressively (the soft_preferences yaml goes in the user
message, which is dynamic; the system stays cacheable across calls).

The score arithmetic is "show your work" math; the model handles it
naturally. Don't try to make the model output the formula explicitly
— the schema captures what matters.
```

### 8.7 `prompts/scoring/digest-summary.md`

```markdown
---
name: digest-summary
version: 1.0.0
schema: doormat.schemas.DigestSummary
recommended_model: claude-haiku-4-5
fallback_models: [openai/gpt-5-mini]
prompt_cache: true
expected_input_tokens: 2000
expected_output_tokens: 350
estimated_cost_usd: 0.001
---

# Daily digest summary

Generates the personalized intro paragraph + per-listing comments for
the daily email digest.

## System

You write the morning email digest for a rental hunter. Your job:
brief, useful, human. Not a status report.

The user has chosen to be told what's worth their time. Lead with the
single best new listing if there is one — name it, say why it stands
out, suggest action. Then briefly cover the other notable new ones.
Skip the rest.

Tone: like a friend who has been keeping an eye out. Not a marketing
email. Not a robot. No bullet lists in the intro. Plain English.

If there are no new listings worth surfacing, say so honestly. "Nothing
new today worth your time" is a fine output. Don't pad.

## User template

Today's new listings (already filtered to this user's hard filters and
ranked by fit score):

{{listings_yaml}}

User's preferences:

{{preferences_yaml}}

User's name (for greeting; "Hey there" if blank): {{name}}

Write the morning digest. Lead with the punch line.

## Output schema

class DigestSummary(BaseModel):
    intro: str = Field(max_length=600,
        description="One-paragraph morning-briefing-style intro. Plain English.")
    standout_listing_id: int | None = Field(default=None,
        description="The single listing the intro highlights. None if no clear standout.")
    per_listing_notes: dict[int, str] = Field(default_factory=dict,
        description="Listing ID → one-line note for the email body. Only for "
                    "listings worth specific commentary; can be empty.")

## Examples

<input>
listings: [
  { id: 142, score: 0.93, address: "18830 Blythe Way", city: "Cottonwood",
    rent: 2950, beds: 3, baths: 2.5, sqft: 1960,
    matched: ["RV parking", "fenced yard", "acreage"],
    missed: ["quiet street"] },
  { id: 143, score: 0.71, address: "847 Congaree Ln", city: "Redding",
    rent: 2350, beds: 4, baths: 2.5, sqft: 1615,
    matched: ["yard"], missed: ["RV parking"] },
  { id: 144, score: 0.62, address: "12 Oak St", city: "Redding",
    rent: 2200, beds: 3, baths: 2, sqft: 1400,
    matched: [], missed: ["yard", "RV parking"] },
]
preferences: { ... }
name: "Josh"
</input>

<o>
{
  "intro": "Morning, Josh. Three new this morning, and the Cottonwood place is the clear standout — 18830 Blythe Way, 3bd/2.5ba on acreage with RV parking and a fenced yard, $2,950. That hits everything you flagged as priorities. Worth reaching out today; acreage rentals in that price range usually move fast. The Congaree place in Redding is a solid backup if Cottonwood doesn't work out.",
  "standout_listing_id": 142,
  "per_listing_notes": {
    "142": "Best price-per-sqft this week. Owner only just listed.",
    "143": "Good fallback. Smaller lot but bigger house."
  }
}
</o>

<input>
listings: []
preferences: { ... }
name: "Josh"
</input>

<o>
{
  "intro": "Morning, Josh. Nothing new today worth your time. Quiet market this week.",
  "standout_listing_id": null,
  "per_listing_notes": {}
}
</o>

## Eval queries

```yaml
- name: clear_standout
  fixture: tests/fixtures/scoring/digest-with-standout.json
  expect:
    standout_listing_id_set: true
    intro_contains_address: true

- name: no_listings
  fixture: tests/fixtures/scoring/digest-empty.json
  expect:
    standout_listing_id: null
    intro_contains_phrase: ["nothing new", "quiet"]

- name: no_padding
  fixture: tests/fixtures/scoring/digest-empty.json
  expect:
    intro_length_at_most: 200
```

## Notes

The intro is the only LLM-generated text the user sees in the email.
It carries the entire "AI-assisted rental hunting" experience. Spend
the tokens here.

Per-listing notes are optional — many digests will have empty
per_listing_notes. That's fine; the email template just shows the
listing card without commentary.
```

### 8.8 `prompts/discovery/city-search.md`

Brief — used in the discovery agent step 1.

```markdown
---
name: city-search
version: 1.0.0
schema: doormat.schemas.CitySearchResult
recommended_model: openrouter/perplexity-sonar-pro
fallback_models: [openai/gpt-5]
prompt_cache: false
expected_input_tokens: 200
expected_output_tokens: 600
estimated_cost_usd: 0.005
---

# City search — discovery step 1

Generates 10–20 candidate URLs for property managers in a target city
via web search.

## System

You find local rental property managers in a US city using web search.

Search for property managers and rental listing sites specific to the
city. Filter out:
- National aggregators (Zillow, Apartments.com, Trulia, Realtor.com,
  HotPads, Rent.com) — we already cover these.
- Real estate sales sites with no rental component.
- Roommate matching services (Roomi, SpareRoom, etc.).
- Furniture rental, vacation rental, storage rental.

Include:
- Local property management companies that list rentals on their
  sites.
- Independent landlords with rental listing pages.
- Local rental aggregators specific to the metro area (sometimes a
  university or city has its own listings portal).

For each candidate, return the listings-index URL (where the rental
listings actually are), not the company's homepage.

## User template

City: `{{city}}, {{state}}`

Find local property management companies and rental listing sites for
this city. Return up to 20 candidate listings-index URLs.

## Output schema

class Candidate(BaseModel):
    url: str
    name: str
    type: Literal["pm_company", "local_aggregator", "independent_lister"]
    confidence: Literal["high", "medium", "low"]

class CitySearchResult(BaseModel):
    candidates: list[Candidate]

## Examples

[Inline shorter for brevity — full file in repo.]

## Eval queries

```yaml
- name: redding_search
  city: "Redding"
  state: "CA"
  expect:
    candidates_length_at_least: 5
    candidates_at_least_one_type: pm_company

- name: small_market_no_results
  city: "Tonopah"
  state: "NV"
  expect:
    candidates_can_be_empty: true   # don't hallucinate sources
```

## Notes

Use a web-search-enabled model. OpenRouter's perplexity-sonar-pro is
the default; it has built-in web search and is cheap. For users
without web-search access, fall back to Tavily or Exa via tool use.

Hallucinated URLs are the worst failure mode here. The classifier
step (next prompt in the pipeline) catches them, but each
hallucination wastes a classifier call. Set the temperature to 0
and lean on the model's grounding.
```

### 8.9 `prompts/discovery/pm-website-classifier.md`

```markdown
---
name: pm-website-classifier
version: 1.0.0
schema: doormat.schemas.PMClassification
recommended_model: claude-haiku-4-5
fallback_models: [google/gemini-2.5-flash, deepseek/deepseek-v3]
prompt_cache: true
expected_input_tokens: 2000
expected_output_tokens: 100
estimated_cost_usd: 0.0004
---

# PM website classifier

Decides whether a candidate URL is a property manager rental site
worth generating an adapter for.

## System

You classify candidate URLs found by the discovery search step.

Possible classifications:
- `property_manager` — a local PM company's rental listings page.
  Has actual listings, not just contact form. Independent of the big
  national aggregators. Worth generating an adapter for.
- `aggregator` — Zillow/Apartments.com/Trulia/Realtor.com/HotPads/
  Rent.com or any other site we already cover via Apify. Skip.
- `parked_or_dead` — domain parked, returns 404, no listings, or
  redirects somewhere unrelated.
- `not_rental` — site exists but isn't about rentals (sales-only
  realtor, roommate matcher, vacation rentals).
- `unsuitable` — site exists with rentals but has barriers we can't
  work around (login wall, captcha on every page, payment required).

Be honest. False positives waste an adapter-generation call (~$0.035).
False negatives miss real sources but don't cost anything beyond the
classifier call itself.

## User template

Candidate URL: `{{url}}`

Page preview (first 3000 chars of cleaned text):

{{preview}}

Classify.

## Output schema

class PMClassification(BaseModel):
    label: Literal[
        "property_manager", "aggregator", "parked_or_dead",
        "not_rental", "unsuitable"
    ]
    reason: str = Field(max_length=200)
    listings_index_url: str | None = Field(
        default=None,
        description="If 'property_manager', the URL where rental listings live. "
                    "May differ from the candidate URL (which might be the homepage)."
    )

## Examples

<input>
url: https://acmepm.example.com
preview: "Acme Property Management — Serving Asheville since 2002. We manage over 200 single-family homes and apartment units in the Asheville area. Click here to see our current vacancies."
</input>

<o>
{
  "label": "property_manager",
  "reason": "Local PM company explicitly serving Asheville with current vacancies link.",
  "listings_index_url": "https://acmepm.example.com/vacancies"
}
</o>

<input>
url: https://www.zillow.com/asheville-nc/rentals/
preview: "Zillow Rentals: 1,234 listings in Asheville, NC..."
</input>

<o>
{
  "label": "aggregator",
  "reason": "Zillow — already covered via Apify."
}
</o>

## Eval queries

```yaml
- name: identifies_pm_site
  fixture: tests/fixtures/discovery/local-pm-preview.json
  expect:
    label: property_manager
    listings_index_url_set: true

- name: rejects_zillow
  fixture: tests/fixtures/discovery/zillow-preview.json
  expect:
    label: aggregator

- name: rejects_parked_domain
  fixture: tests/fixtures/discovery/parked-domain.json
  expect:
    label: parked_or_dead
```

## Notes

This runs Haiku because volume is high (10–20 calls per city
discovery). Cost per call is ~$0.0004; total per discovery is ~$0.008.
```

### 8.10 `prompts/refinement/sidebar-chat.md`

```markdown
---
name: sidebar-chat
version: 1.0.0
schema: doormat.schemas.ChatTurn
recommended_model: claude-haiku-4-5
fallback_models: [openai/gpt-5-mini]
prompt_cache: true
expected_input_tokens: 1500
expected_output_tokens: 300
estimated_cost_usd: 0.0008
---

# Sidebar chat

The conversational refinement assistant. Answers questions about
listings, refines filters via tool use, compares listings.

## System

You're doormat's sidebar assistant. The user is browsing rentals;
you help them refine their filter, understand listings, and compare
options.

Tools available:
- `update_filter(field, operation, value)` — modify the user's active
  filter. Use when the user wants to change what they're seeing.
- `get_listing(listing_id)` — fetch a listing by ID.
- `similarity_search(listing_id, top_k)` — find listings similar to
  a given one.
- `explain_score(listing_id)` — get the saved fit score and
  explanation for a listing.

Constraints:
- Maximum 8 tool calls per user turn.
- Don't editorialize listings. The user has already seen the score
  and explanation; don't re-pitch listings to them.
- When updating filters, confirm the change in plain English ("Got
  it — only showing listings with garages now"). Then stop. Don't
  preemptively fetch the new results; the frontend invalidates the
  query automatically.
- When comparing listings, use the structured data the user can
  already see. Don't re-state things visible on screen.

You're a sidebar, not a chatbot. Brief is better. The user can ask
a follow-up if they want more.

## User template

Current filter:
```json
{{current_filter_json}}
```

Listings currently visible (truncated):
{{visible_listings_summary}}

User: {{user_message}}

## Output schema

The runtime treats this as a normal tool-use loop until the model
emits a final text response. Schema captures the final response only:

class ChatTurn(BaseModel):
    response: str = Field(max_length=600)
    suggested_followups: list[str] = Field(default_factory=list, max_length=3)

## Examples

[Inline shorter; see repo.]

## Eval queries

[Inline shorter; see repo.]

## Notes

This is the only conversational prompt in doormat. It's intentionally
narrow — it can refine filters and answer questions about listings,
but it can't (e.g.) negotiate with landlords, draft emails, or do
moving logistics. Scope creep here will balloon LLM cost; resist.
```

---

## 9. Skills bundle — full inline

Drop this entire `skills/` directory into the repo as-is.

### 9.1 `skills/README.md`

```markdown
# `skills/` — doormat as portable Anthropic Agent Skills

doormat ships as a full app, but its core logic is also packaged as a
suite of Anthropic Agent Skills (the open standard at
agentskills.io). Each skill works in:

- Claude Code
- Claude.ai (via the Skills API)
- Cursor (via AGENTS.md fallback)
- OpenCode (reads `.claude/skills/` natively)
- GitHub Copilot in VS Code
- Zo Computer (the platform doormat was originally prototyped on)

Three skills are shipped:

- **`doormat-mvp/`** — the original Zo Computer MVP, refactored as a
  portable skill. Run doormat as a skill without Docker, without an
  API server, without a frontend. Just chat with your AI tool and
  ask it to find rentals.
- **`add-rental-source/`** — walks a contributor through adding a
  new rental source to doormat. Validates robots.txt, generates an
  adapter, runs evals, opens a PR.
- **`debug-failing-source/`** — diagnostic skill for when a source
  starts returning bad data. Diffs the cached strategy against
  current page structure, suggests fixes.

To install a skill in your AI tool, see `docs/use-with-ai-tools.md`.
```

### 9.2 `skills/doormat-mvp/SKILL.md`

[Full content is in the existing `SKILL.md` file accompanying this
guide. The summary form for inclusion here:]

```markdown
---
name: doormat-mvp
description: Find rental listings in any US city by scraping local property managers, Craigslist, Zillow, and Facebook Marketplace, scoring them against the user's preferences, and emailing a daily digest. Use this skill whenever the user mentions apartment hunting, rental search, finding a place to live, looking for a house to rent, monitoring new listings, tracking price drops, or any phrase like "find me a rental in [city]" — even if they don't explicitly mention property managers, scraping, or aggregation.
license: Apache-2.0
metadata:
  author: doormat
  version: 1.0.0
  homepage: https://github.com/yourusername/doormat
---

[Full body content in companion SKILL.md file, including:
- Quick start (60 seconds)
- Five-phase workflow (source identification, listing extraction,
  filtering, scoring, digest)
- Three concrete examples (first-time use, repeat invocation with
  refinement, asking why a listing scored low)
- Guidelines (cost discipline, privacy, boundaries, refusal conditions)
- Failure modes
- Output format expectations
- Bundled resources (references/, scripts/)
]
```

### 9.3 `skills/add-rental-source/SKILL.md`

```markdown
---
name: add-rental-source
description: Walk a contributor through adding a new rental property manager source to doormat — including validating robots.txt, generating the extraction adapter using Browser-Use, capturing a scrubbed test fixture, running the eval set, registering the source via entry-point, and opening a PR. Use this skill whenever the user mentions adding a property manager, adding a new source, contributing a scraper, or asks "how do I add my city's rental site to doormat?".
license: Apache-2.0
metadata:
  author: doormat
  version: 1.0.0
---

# Add a rental source

This skill walks a contributor through adding a new rental property
manager site to doormat. It runs the full pre-flight (robots.txt,
ToS check, captcha presence), drives the adapter generator, captures
a scrubbed fixture, and prepares the PR.

## When to use this skill

The user said "add a property manager", "add a source", "contribute
a scraper", or asked any variant of "how do I add my city's rental
site to doormat?". Also use when the user pastes a URL and asks
something like "can doormat scrape this?".

## Workflow

### Step 1: Pre-flight checks

Run `scripts/preflight.py URL` which:
1. Fetches `URL/robots.txt` and checks whether listings are
   disallowed for `*` or for `doormatBot`. If disallowed, REFUSE
   to proceed; tell the user the site has opted out.
2. Checks the page for known captcha challenge fingerprints
   (Cloudflare, reCAPTCHA, hCaptcha, DataDome). If detected, warn
   the user that this source will need to be routed through Apify
   instead of direct scraping.
3. Checks the page for login-wall indicators. If detected, refuse
   — doormat does not handle authenticated scrapes.
4. Checks for non-rental signals (sales-only, vacation-only). If
   found, warn the user this isn't a rental site.

### Step 2: Generate the adapter

If pre-flight passes, run the discovery agent against the URL using
`scripts/generate_adapter.py URL --output strategies/<source>.json`.
This drives Browser-Use to navigate the site, sample 5 listings,
and emit an `ExtractionStrategy`.

### Step 3: Capture a fixture

Run `scripts/capture_fixture.py URL/listings/N` to save a scrubbed
HTML fixture under `tests/fixtures/html/<source>/`. The scrubber
replaces real addresses, phone numbers, and personal names with
synthetic equivalents. Confirm with the user that the scrubbed
fixture looks correct before committing.

### Step 4: Run evals

Run `uv run pytest tests/sources/<source>/`. The standard eval set
asserts that the generated strategy plus the fixture produce a
typed Listing with all required fields.

### Step 5: Register the source

Add the source to `pyproject.toml`'s entry-point group:

[project.entry-points."doormat.sources"]
<source-name> = "doormat.sources.pm.<source>:Adapter"

### Step 6: Document

Add an entry to `docs/sources.md`. The format:

#### <Source Name>
- URL: `<index-url>`
- Method: direct scraping / Apify (`<actor-slug>`)
- Coverage: <city/region>
- Robots.txt: respected
- Notes: <any quirks>

### Step 7: Open the PR

Run `gh pr create --title "feat(sources): add <source>" --body-file
.github/PR_TEMPLATE/new-source.md`. Confirm the PR template's
checklist is complete before submitting.

## Examples

[Concrete examples of running the skill, abbreviated for this guide.]

## Guidelines

### Don't break the existing source list

If your new source has selectors that overlap with an existing
adapter (e.g., both extract from the same AppFolio template), check
whether you should *extend* the existing adapter instead of adding
a new one. The `_registry.py` resolves source name conflicts;
duplicates are silently dropped.

### Respect robots.txt

If pre-flight says no, the answer is no. Don't try to work around
robots disallow rules. The runtime will refuse to scrape disallowed
paths anyway; adding the source is wasted effort.

### Privacy of the fixture

The scrubber is good but not perfect. Manually inspect the
committed fixture for any leaked PII before committing. Names,
phone numbers, real addresses must all be synthetic.

### Cost awareness

Adapter generation costs ~$0.035 in LLM tokens. Don't generate
adapters speculatively for sites you haven't pre-flight-validated.

## Bundled resources

- `references/extraction-strategy-schema.md` — the Pydantic schema
  for `ExtractionStrategy`, with field-by-field guidance.
- `references/example-adapters.md` — three reference adapters
  (clean AppFolio, custom site with click-to-expand, JSON-API
  source) annotated with what makes each strategy good.
- `scripts/preflight.py`
- `scripts/generate_adapter.py`
- `scripts/capture_fixture.py`
- `scripts/run_evals.py`
```

### 9.4 `skills/debug-failing-source/SKILL.md`

```markdown
---
name: debug-failing-source
description: Diagnose and fix a doormat rental source that has started returning bad data. Use when the user says a specific source is broken, listings have garbage data, the cost dashboard shows Mode B fallback rate spiking, or the source-health page shows a strategy with health below 0.5.
license: Apache-2.0
---

# Debug a failing source

Diagnostic workflow for when a doormat source's extraction strategy
has drifted out of sync with the live site.

## When to use this skill

Triggers:
- User reports "the X listings have wrong data"
- Cost dashboard shows Mode B rate spiking for source X
- Source-health page shows strategy health < 0.5
- Daily digest contains a listing with `confidence: low` or
  obviously corrupt fields

## Workflow

1. Pull the failing source's last 10 Mode A extractions from the
   `llm_calls` table. Look for patterns in the `confidence` field
   and the `reasoning` of escalated Mode B calls.
2. Run `scripts/diff_strategy.py <source>` which fetches the live
   site and diffs the cached strategy's selectors against current
   DOM presence. Selectors that no longer match anything on the page
   are the culprits.
3. If selectors have drifted, re-run the discovery agent with
   `scripts/regenerate_strategy.py <source>` and review the new
   strategy.
4. Validate the new strategy against the most recent 5 listings via
   `scripts/validate_strategy.py <source> --new-strategy
   strategies/<source>-new.json`.
5. If validation passes, commit the new strategy as
   `strategies/<source>.json` (overwriting the old one). Bump the
   `schema_version` field by 1.
6. The runtime auto-migrates: existing listings remain, but new
   extractions use the new strategy.

## Examples

[Abbreviated.]

## Guidelines

- **Never edit a strategy by hand.** Use the regeneration tooling.
  Hand-edited strategies tend to break in subtle ways and are
  unreviewable in PRs.
- **Don't blindly trust the regenerated strategy.** Always run the
  validation step. A regenerated strategy that fails validation is
  a sign the site has changed in a way the discovery agent doesn't
  yet handle — flag for human review.
- **Bump schema_version even on minor changes.** The runtime caches
  Mode A results by version; bumping invalidates the cache cleanly.

## Bundled resources

- `scripts/diff_strategy.py`
- `scripts/regenerate_strategy.py`
- `scripts/validate_strategy.py`
```

---

## 10. The frontend

### 10.1 Tailwind UI templates to use

Map each screen to a specific Tailwind UI template. Buy the license
at tailwindui.com.

| Screen | Template (Tailwind UI) | Adaptations |
|---|---|---|
| Onboarding | "Application UI > Sign-up forms > Two-column with hero" | Replace right-side hero with the chat pane; left-side becomes the live-updating form preview |
| Dashboard | "Application UI > Lists > Stacked card list" | Cards show photo + score badge + fit explanation; sort dropdown in header; filter sidebar |
| Listing detail | "Application UI > Page examples > Detail screens with tabs" | Photo gallery in hero; sidebar contains the chat panel + score breakdown |
| Preferences | "Application UI > Forms > Stacked layouts > Two-column" | Right column shows live "47 listings would match" preview |
| Discovery progress | Custom (not a template) | Terminal-style log with Framer Motion entry animations |

### 10.2 The Dockerfile

```dockerfile
# syntax=docker/dockerfile:1.7

# ---- Stage 1: build the SPA
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

# ---- Stage 2: install Python deps
FROM python:3.13-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev --no-editable
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-editable

# ---- Stage 3: runtime
FROM python:3.13-slim-bookworm AS runtime
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget gnupg ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd -g 1001 app && useradd -u 1001 -g app -m -d /app -s /bin/bash app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
COPY --from=web --chown=app:app /web/dist /app/src/doormat/static
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["python", "-m", "uvicorn", "doormat.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 10.3 docker-compose.yml

```yaml
services:
  app:
    build: .
    image: ghcr.io/yourusername/doormat:latest
    restart: unless-stopped
    env_file: .env
    environment:
      DATABASE_URL: sqlite:////data/db.sqlite
      DATA_DIR: /data
      CACHE_DIR: /cache
      TZ: ${TZ:-America/Los_Angeles}
    volumes:
      - data:/data
      - cache:/cache
    ports: ["8000:8000"]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s

  playwright:
    profiles: ["playwright"]
    image: mcr.microsoft.com/playwright/python:v1.49.0-noble
    restart: unless-stopped
    command: python -m doormat.fetch.playwright_worker
    environment:
      DATABASE_URL: sqlite:////data/db.sqlite
    volumes: [data:/data]

volumes:
  data:
  cache:
```

### 10.4 .env.example

```bash
# === LLM ===
# Pick ONE LLM_PROVIDER. The default is openrouter (BYOK).
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
# Fallback or alternative providers (uncomment as needed):
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# OLLAMA_BASE_URL=http://localhost:11434

# Model routing (override defaults if you want)
LLM_MODEL_EXTRACTION_MODE_A=anthropic/claude-haiku-4-5
LLM_MODEL_EXTRACTION_MODE_B=anthropic/claude-sonnet-4-7
LLM_MODEL_DISCOVERY=anthropic/claude-sonnet-4-7
LLM_MODEL_SCORING=anthropic/claude-haiku-4-5
LLM_MODEL_REFINEMENT=anthropic/claude-haiku-4-5

# Daily LLM budget per user, in USD. Calls beyond budget fail open.
LLM_DAILY_BUDGET_USD=2.00

# === Apify (BYOK; required for Zillow + FB Marketplace) ===
APIFY_API_TOKEN=apify_api_...

# === Email ===
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_...
EMAIL_FROM=doormat@yourdomain.com
EMAIL_TO=you@yourdomain.com,partner@yourdomain.com

# === Map (optional but recommended) ===
MAPTILER_API_KEY=...

# === App ===
HOST=127.0.0.1
PORT=8000
AUTH_MODE=none
# When AUTH_MODE=bearer, set the token:
# AUTH_BEARER_TOKEN=...

# === Misc ===
TZ=America/Los_Angeles
LOG_LEVEL=INFO
SCRAPE_CRON="0 8,17 * * *"  # 8am + 5pm daily
DIGEST_CRON="0 9 * * *"      # 9am daily
```

---

## 11. Cost engineering

The cost section is what recruiters read carefully. Make it real.

### 11.1 The seven optimizations doormat ships with

1. **Tiered model routing** (§7) — different subsystems use different
   models. ~5–10× cost reduction vs. "Sonnet for everything."

2. **Two-mode extraction** (§7.3) — Mode A deterministic for 99% of
   listings, Mode B agentic for 1%. ~30× reduction vs. fully-agentic.

3. **Strategy update feedback loop** — Mode B's strategy_update
   improves Mode A for future calls. Cost per source amortizes
   downward over time.

4. **Prompt caching** — Anthropic's `cache_control` and OpenAI's
   automatic >1024-token prompt caching. ~10× reduction on
   high-volume calls.

5. **Embedding pre-filter for scoring** — sqlite-vec cosine
   similarity prunes the bottom 50% before LLM scoring fires.
   ~2× reduction.

6. **Hash-based dedup before LLM** — listings already in `seen.db`
   skip extraction entirely. At 5% new listings/day, this is the
   dominant cost reduction (~20× steady state).

7. **Daily-budget cap** — `LLM_DAILY_BUDGET_USD` setting. Calls
   beyond budget fail with a clear "budget exceeded" error. The
   cost dashboard alerts before hard cap.

### 11.2 The cost dashboard

A page at `/cost` shows:
- Today's spend, broken down by subsystem and model.
- 7-day rolling chart.
- Per-source cost (Apify + LLM).
- Predicted month-end at current burn rate.

The data is live from the `llm_calls` table:

```sql
CREATE TABLE llm_calls (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    prompt_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    model TEXT NOT NULL,
    mode TEXT,                    -- A or B for extraction
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cached_tokens INTEGER,
    cost_usd REAL,
    latency_ms INTEGER,
    success BOOLEAN
);
```

The middleware that populates this is the LLMClient wrapper. Every
call goes through it; nothing escapes accounting.

### 11.3 Realistic cost ceiling

For a fully active user (one new city per month, 300 listings/day,
all paid models):

| Item | Cost/mo |
|---|---|
| Apify (Zillow + FB) | $5 |
| Discovery (1 new city) | $0.50–2 |
| Listing extraction (steady state) | $0.10 |
| Scoring | $0.30 |
| Sidebar chat (modest use) | $0.10 |
| Daily summaries | $0.30 |
| **Total** | **~$6–8/mo** |

For a free-tier user (DeepSeek V3 etc. via OpenRouter):

| Item | Cost/mo |
|---|---|
| Apify (Zillow + FB) | $5 (or $0 with monthly free credit) |
| Everything LLM | $0 |
| **Total** | **$0–5/mo** |

These numbers go in the README, with the breakdown linked.

---

## 12. Testing strategy

### 12.1 Test pyramid

```
         /\
        /  \  Eval queries (slow; nightly + on prompt PR)
       /────\
      /      \  Integration tests (medium; per PR)
     /────────\
    /          \  Unit tests (fast; per commit)
   /────────────\
  /              \  Type check + lint (fastest; per save)
 /────────────────\
```

### 12.2 Layered test responsibilities

**Layer 1: pure parser tests.** Given a scrubbed HTML fixture, the
extraction code returns an expected `Listing`. Snapshot via syrupy.

**Layer 2: HTTP-layer tests.** Mock httpx via respx. Assert retry
behavior, semaphore behavior, 429 handling.

**Layer 3: VCR cassettes.** Record real HTTP once with vcrpy, replay
deterministically in CI. Cassettes scrubbed of PII via `before_record_response`.

**Layer 4: Property tests.** Hypothesis on the address regex, price
parsing, hash function, three-state pet-policy detection.

**Layer 5: Eval queries.** Per-prompt YAML queries. Run against the
prompt's `recommended_model`. Failed eval = failed CI.

### 12.3 Privacy of fixtures

Three-layer scrubbing before committing fixtures:

1. **Capture-time scrubber** — `tests/fixtures/scrub.py` runs
   automatically when you do `make capture-fixture SOURCE=hignell URL=...`.
   Replaces real addresses, phone numbers, emails, names with
   synthetic placeholders.
2. **VCR `before_record_response` hook** — strips sensitive headers
   and applies the same scrubber to response bodies.
3. **Pre-commit hook** — regex grep over `tests/fixtures/**` that
   fails if it finds anything matching strict address/phone/email
   patterns. Belt and suspenders.

### 12.4 Coverage target

80% lines, with explicit waivers for adapter outermost-error paths.
Don't fake high coverage by stubbing Apify itself — be honest about
what's testable.

---

## 13. CI/CD

### 13.1 GitHub Actions workflows

`.github/workflows/ci.yml` — runs on every push and PR:

```yaml
name: CI
on:
  push: { branches: [main] }
  pull_request:
permissions: { contents: read, packages: write, id-token: write }
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with: { enable-cache: true }
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run ruff format --check .
  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --frozen
      - run: uv run mypy src
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix: { python: ["3.12", "3.13"] }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with: { enable-cache: true }
      - run: uv python install ${{ matrix.python }}
      - run: uv sync --frozen --python ${{ matrix.python }}
      - run: uv run pytest --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v4
        with: { files: coverage.xml }
  prompts-eval:
    runs-on: ubuntu-latest
    if: contains(github.event.pull_request.changed_files, 'prompts/')
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --frozen
      - run: uv run doormat prompt eval --all --strict
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
  docker:
    needs: [lint, typecheck, test]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:latest
            ghcr.io/${{ github.repository }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

`.github/workflows/release-please.yml` — opens release PR, publishes
on merge:

```yaml
name: release-please
on:
  push:
    branches: [main]
permissions:
  contents: write
  pull-requests: write
  id-token: write
jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@v4
        id: release
        with:
          release-type: python
          package-name: doormat
      - if: ${{ steps.release.outputs.release_created }}
        uses: actions/checkout@v4
      - if: ${{ steps.release.outputs.release_created }}
        uses: astral-sh/setup-uv@v4
      - if: ${{ steps.release.outputs.release_created }}
        run: uv build
      - if: ${{ steps.release.outputs.release_created }}
        uses: pypa/gh-action-pypi-publish@release/v1
```

### 13.2 Branch protection

On `main`:
- Require PR with 1 approval.
- Require status checks: lint, typecheck, test (matrix).
- Require linear history.
- Require signed commits.
- Restrict who can push to releases.

### 13.3 Conventional Commits + commitlint

Enforce via a commit-msg hook in `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/compilerla/conventional-pre-commit
  rev: v3.4.0
  hooks:
    - id: conventional-pre-commit
      stages: [commit-msg]
      args: []
```

---

## 14. Launch playbook

### 14.1 Tag and release

```bash
# Confirm release-please PR is up to date and has the version you want
gh pr view "release-please--branches--main"
# Merge it
gh pr merge "release-please--branches--main" --squash
# Watch the release workflow:
gh run watch
```

### 14.2 Public demo

Deploy to Hetzner (€4.59/mo) with synthetic data:

```bash
# On the Hetzner box:
git clone https://github.com/yourusername/doormat
cd doormat
cp .env.example .env
# Edit .env — set USE_SYNTHETIC_DATA=true, fill API keys for demo flow
docker compose up -d
# Set up Caddy as TLS reverse proxy:
sudo apt install caddy
sudo bash -c 'cat > /etc/caddy/Caddyfile <<EOF
demo.doormat.dev {
  reverse_proxy localhost:8000
}
EOF'
sudo systemctl reload caddy
```

### 14.3 Hero GIF via vhs

`hero.tape`:

```
Output hero.gif

Set FontSize 14
Set Width 1200
Set Height 700

Type "doormat discover 'Sacramento, CA'"
Enter

Sleep 2s

# Wait for the discovery agent's events to stream
Sleep 30s

# Show the resulting listings
Type "doormat listings --top 5"
Enter
Sleep 5s
```

`vhs hero.tape` produces `hero.gif`. Drop into the README's hero
slot.

### 14.4 Show HN post template

```
Show HN: doormat — AI agent that finds rentals in any city

I built doormat, an AI-first rental finder where you describe your
dream place in natural language and an agent autonomously discovers
local property managers, generates web scrapers for them, and
surfaces personalized matches with explanations.

It started as a Zo Computer skill I built to find an apartment in
Redding, CA. After three weeks of iteration it was working — emailing
me twice a day with new listings. Friends in other cities asked for
it; the Zo skill didn't generalize. So I rebuilt it as this open
source app.

Architecture highlights:
- Two-mode extraction: deterministic Mode A for ~99% of listings
  (~$0.0008 each), agentic Mode B via Browser-Use for the 1% where
  Mode A's strategy fails. Mode B emits a strategy_update that
  improves Mode A for future calls.
- Tiered model routing across OpenRouter, Anthropic, OpenAI, Ollama.
  Free models work fine for everything except discovery.
- Prompt caching, embedding pre-filter, hash-dedup-before-LLM. Live
  cost dashboard.
- FastMCP server so you can ask Claude or any MCP client to query
  your listings.
- Apache 2.0, self-hosted, BYOK, single-user.

Repo: https://github.com/yourusername/doormat
Demo: https://demo.doormat.dev
Docs: https://yourusername.github.io/doormat
```

### 14.5 Subreddit/awesome-list submissions

Submit to:
- r/Python "Showcase Saturday" (Saturday only)
- r/selfhosted (any day)
- r/MachineLearning [Project] flair
- awesome-python (PR)
- awesome-mcp-servers (PR)
- awesome-claude-code (PR)
- awesome-selfhosted (PR)

Don't submit to all on the same day. Stagger across 5–7 days for
sustained discovery.

### 14.6 Blog post

The strongest hook is the **origin story**: from Zo Computer skill to
AI-native open source app. Title:

> "From Zo Computer skill to AI-first open source: how I built
> `doormat` to find my apartment"

Outline:

1. The problem (apartment hunting in Redding, 13 PM sites)
2. The MVP on Zo Computer (single skill, 3 weeks)
3. What didn't generalize (city-specific PM list)
4. The rebuild as open source (this is where you talk about
   architecture)
5. The flagship feature (Browser-Use discovery agent)
6. Cost engineering (the $1/mo claim)
7. Try it yourself

Cross-post on dev.to, Medium, Hashnode. Pin tweet linking the post.

---

## 15. The interview pitch

When a recruiter or hiring manager asks "tell me about a recent
project," this is the answer.

### 15.1 The 30-second version

> *I built doormat, an AI-first rental finder. It's open source on
> GitHub. The headline feature is an agent that, given any US city
> name, autonomously discovers local property managers, generates
> working scrapers for them via Browser-Use, and starts pulling
> listings — usually in under five minutes. It runs on under a dollar
> a month of LLM costs because of cost-optimization choices I made
> throughout: two-mode extraction, prompt caching, embedding
> pre-filter, hash-based dedup. Self-hosted, BYOK, no auth, no
> business model. I built it because I needed it to find my own
> apartment.*

### 15.2 The 2-minute version

Add to the above:

- **Origin story.** Started as a Zo Computer skill to find an apartment
  in Redding, CA. After three weeks of iteration it was working.
  Friends in other cities asked for it; the Zo skill didn't
  generalize. So I rebuilt it.
- **The two-mode extraction architecture.** Mode A is deterministic-
  first using cached extraction strategies — 99% of listings, ~$0.0008
  each. Mode B is agentic recovery via Browser-Use — fires for the 1%
  where Mode A's strategy has drifted, ~$0.025 each, and emits a
  strategy_update that improves Mode A for future calls. The system
  gets cheaper over time as Mode B teaches Mode A how to handle each
  source's quirks.
- **The discovery agent.** Browser-Use orchestrates web search →
  classification → adapter generation → validation → cache. Generates
  reusable extraction strategies for any city in under five minutes.
  Caps at $5 of LLM spend per discovery; typical run is $0.50–$2.
- **The cost dashboard.** Every LLM call is recorded; the dashboard
  shows live spend by subsystem and model. One of the things I'm
  proudest of in the project — it's the visible artifact of the cost
  engineering.
- **MCP integration.** Ships with a FastMCP server so you can ask
  Claude Desktop or any MCP client to query your listings. *"Show me
  places under $2500 with a yard"* and it just works.

### 15.3 What the recruiter will look at

When they go to the GitHub repo, in priority order:

1. The README's hero GIF and pitch.
2. The `docs/ai-engineers-guide.md` page — your most-read page.
3. The `prompts/` directory.
4. The cost dashboard demo.
5. CI status (green badges, coverage % on the readme).
6. The architecture doc (Mermaid diagram).
7. Recent commits and CHANGELOG.

Make sure all seven are polished before launch.

---

## 16. Appendix: troubleshooting & FAQ

### "I get HTTP 402 from Apify mid-month"

Apify's free tier ($5/mo credit) ran out. Either:
- Wait for next month
- Top up with $5–10 of credit
- Disable Apify-routed sources until next month
  (`APIFY_ENABLED=false` in `.env`)

The runtime treats 402s as graceful degradation; you'll see fewer
listings until either of the above resolves.

### "OpenRouter returns 'no endpoints available'"

The model you configured may have been temporarily delisted. Check
status at status.openrouter.ai. Fall back to a different model in
your `.env`:

```bash
LLM_MODEL_EXTRACTION_MODE_A=anthropic/claude-haiku-4-5  # if Haiku is up
# Or:
LLM_MODEL_EXTRACTION_MODE_A=deepseek/deepseek-v3        # free tier always-on
```

### "The discovery agent keeps timing out"

Browser-Use's agent timeout defaults to 5 minutes. For sites with
heavy anti-bot, even Browser-Use struggles. Workarounds:

- Skip the source: `doormat sources disable <source-id>`
- Increase the timeout: `DISCOVERY_TIMEOUT_SECONDS=900`
- Use Apify for the source instead, if an actor exists

### "I'm getting low-quality listings from a specific source"

Run the `debug-failing-source` skill (§9.4). Most likely the cached
strategy has drifted; regenerate it.

### "Mode B costs are spiking"

Look at the cost dashboard's "Mode B rate by source" panel. If a
specific source is at >5% Mode B, its strategy needs regeneration.
Run the `debug-failing-source` skill for that source.

### "Cron isn't firing inside Docker"

APScheduler runs in-process; if the API container is restarting, the
scheduler restarts too. Check `docker logs doormat-app` for crash
loops. If you want process isolation between the API and the
scheduler, see the `--profile separate-scheduler` documentation in
`docs/deployment/`.

### "The frontend can't reach the FastAPI server"

In dev: ensure both are running on `localhost`, FastAPI on 8000,
Next.js on 3000. The `next.config.ts` proxies `/api` to FastAPI.

In prod (single-container): the SPA is served from the same FastAPI
process. Check that `src/doormat/static/` was populated during the
Docker build. If empty, the SPA build step failed silently.

### "I want to remove a source after discovery added it"

`doormat sources disable <source-id>`. The strategy stays in the
DB (in case you want to re-enable later) but no scraping runs.

To fully remove: `doormat sources remove <source-id> --confirm`.

### "Can I run doormat behind a VPN/Tailscale?"

Yes. Set `HOST=0.0.0.0` and bind only to your tailnet's interface.
Set `AUTH_MODE=bearer` and a token if you're paranoid. The startup
guard refuses to start with `AUTH_MODE=none` AND a non-localhost
HOST AND `ALLOW_INSECURE != "yes"`, by design.

### FAQ: Is it legal to scrape rental sites?

Public, non-authenticated rental listings are generally fair to
collect for personal use. The `responsible-use.md` doc has the full
position. doormat respects robots.txt by default, doesn't bypass
auth or captchas, doesn't redistribute scraped data, and is provided
AS-IS. Users are responsible for compliance with each source's ToS.

### FAQ: Can doormat scrape my city's local apartment forum?

If it's publicly accessible (no login required), the discovery agent
can probably generate an adapter for it. Add the URL via the
`add-rental-source` skill and let the agent try.

### FAQ: Can I use this for commercial purposes?

Apache 2.0 license allows commercial use. But: each underlying source
has its own terms. Apify's API usage rules apply if you use Apify
sources. Aggregator ToS varies. doormat doesn't make any guarantees
about commercial fitness.

### FAQ: Does doormat work outside the US?

Mostly no, in v0.1. Craigslist works internationally where it has
regional subdomains. Apify has actors for some non-US sites but
they aren't wired up. The discovery agent's prompts are US-English
tuned. International support is a v0.3+ goal.

### FAQ: Can I disable a specific AI feature?

Yes. Each subsystem has a feature flag in `config.yaml`:

```yaml
features:
  discovery_agent: true
  conversational_refinement: true
  daily_summary: true
  embedding_prefilter: true
  mode_b_recovery: true
```

Disable any to skip that subsystem entirely. The cost dashboard
will reflect the reduced spend.

---

## You're ready to build

This is everything. Hand this guide to Claude Code, or sit down and
work through it section by section. The first commit is week 1, step
1: `uv init doormat`.

Welcome to building doormat.
