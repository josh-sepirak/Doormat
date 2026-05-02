# 🚪 Doormat

**An AI-first rental finder.** Describe your dream place in natural language. An autonomous agent discovers local property managers, generates working scrapers, pulls listings, and surfaces personalized matches with explanations.

**Self-hosted, BYOK, under $1/month.**

---

## What is Doormat?

You're stressed about housing. You describe your ideal rental in plain English ("Modern 2-bed in downtown, under $2000, walkable neighborhood"). Doormat's agent autonomously:

1. **Discovers** property managers in your city (2 min)
2. **Generates scrapers** for each site (analyzing HTML to extract listings)
3. **Extracts listings** efficiently (two-tier: cheap fast pass + smart validation)
4. **Scores matches** against your preferences (with explanations)
5. **Surfaces results** in a beautiful, dark-mode dashboard in real-time

Result: you check Doormat once a day and see personalized matches. No more tabs. No more repetitive clicking. No more exhaustion.

### Key Features

- **Autonomous discovery**: Browser-Use agents find property managers you've never heard of
- **Two-tier extraction**: Fast cheap model + strong validation model = cheap + accurate
- **Natural language preferences**: "Pet-friendly, no noise" → structured search
- **Real-time scoring**: Listings arrive and are scored as they're found
- **Cost dashboard**: Every LLM call visible; < $1/month typical
- **Dark mode**: Intentionally designed for both light and dark
- **Self-hosted + BYOK**: Your data, your machine, your API keys
- **MCP integration**: Wire into Claude Desktop or external agents

---

## Contributing sources

To add a new property-manager listing source (preflight, harness, strategy JSON), see **[docs/contributing/adding-a-source.md](docs/contributing/adding-a-source.md)** and run `make add-source URL=…` after reading that page.

---

## Quick Start

### Prerequisites

- Docker + Docker Compose (easiest)
- Or: Python 3.13 + uv
- OpenRouter API key (free tier works)
- Optional: Apify token (for anti-bot fallback)

### Setup (Docker)

```bash
# Clone repo
git clone https://github.com/josh-sepirak/Doormat.git
cd Doormat

# Copy env template
cp .env.example .env

# Add your API keys to .env
# OPENROUTER_API_KEY=sk-or-...
# APIFY_API_TOKEN=apf_...  (optional)

# Start services
docker compose up

# Open dashboard
open http://localhost:3000
```

Dashboard loads at `localhost:3000`. Backend API at `localhost:8000`.

### Setup (Local Development)

```bash
# Install dependencies
uv sync --extra dev

# Run migrations
uv run alembic upgrade head

# Start backend
uv run uvicorn doormat.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, start frontend
cd frontend
npm install && npm run dev
# Frontend at localhost:3000
```

---

## Usage

### Workflow 1: First Search

1. **Open dashboard** → `http://localhost:3000`
2. **Enter preference** (natural language):
   ```
   Modern 2-bed in downtown, walkable, under $2500/mo, pet-friendly
   ```
3. **Select city** → San Francisco, CA
4. **Click "Find Rentals"**
   - Agent discovers property managers (~2 min)
   - Extraction begins
   - Listings stream in real-time, scored as they arrive
5. **Review matches** → See top-scored listings with explanations
6. **Save favorites** → Click star to save, export to CSV

### Workflow 2: Refine Preferences

1. **Click "Edit Preferences"**
2. **Update description** → e.g., add "no upper floors"
3. **Re-score** → All cached listings rescored instantly
4. **See new rankings** → Preferences refined, matches updated

### Workflow 3: Explore Another City

1. **New search button**
2. **Select different city** → Oakland, CA
3. **Agent checks cache** → If property managers already discovered, reuse them
4. **New listings flow in** → Same scoring, new market

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env`:

```env
# LLM (required for features)
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxx

# Optional: Anti-bot fallback
APIFY_API_TOKEN=apf_xxxxx

# Database (defaults to SQLite)
DATABASE_URL=sqlite+aiosqlite:///./doormat.db
# Or Postgres: postgresql+asyncpg://user:pass@localhost/doormat

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json          # prod: json, dev: console

# Cost limits (optional)
BUDGET_LIMIT_USD=5.0     # Alert if monthly spend exceeds this

# Feature flags
ENABLE_DISCOVERY_AGENT=true
ENABLE_EXTRACTION=true
ENABLE_SCORING=true
ENABLE_MCP_SERVER=false  # Set true if using Claude Desktop
```

### Cost Tuning

Doormat auto-selects cheap models for fast tasks, expensive models only when needed:

| Component | Model | Cost |
|-----------|-------|------|
| Discovery | Claude Haiku / Gemma-free | $0.00-0.03 |
| Extraction (Tier 1) | Claude Haiku | $0.0005-0.001 / listing |
| Validation (Tier 2) | Claude 3.5 Sonnet | $0.002-0.005 / listing |
| Scoring | Claude 3.5 Sonnet | $0.003-0.006 / listing |

**Typical run** (1 city, 30 property managers, 300 listings):
- Discovery: $0.03
- Extraction: $0.30
- Validation: $0.60
- Scoring: $0.60
- **Total: ~$1.50**

But with caching + prompt reuse, cost **converges to <$0.50/month** after first few searches.

---

## Architecture

### Backend (Python)

```
src/backend/doormat/
├── main.py                  # FastAPI app, lifespan, middleware
├── config.py                # Pydantic Settings (reads .env)
├── schemas.py               # Pydantic I/O schemas
├── models/
│   └── orm.py               # SQLAlchemy 2.0 ORM (typed columns)
├── db/
│   └── base.py              # DeclarativeBase
├── agents/
│   ├── discovery.py         # Browser-Use city discovery
│   ├── extraction.py        # Tier 1 + Tier 2 extraction
│   └── scoring.py           # Listing scorer
├── api/
│   ├── preferences.py       # CRUD endpoints
│   ├── listings.py          # Query + scoring endpoints
│   ├── costs.py             # Cost dashboard endpoints
│   └── discovery.py         # Discovery trigger endpoints
├── logging_config.py        # structlog setup
├── metrics.py               # Prometheus metrics
├── cost_tracking.py         # Per-call cost recording
└── retry.py                 # tenacity helpers
```

### Frontend (Next.js)

```
frontend/
├── app/
│   ├── page.tsx             # Dashboard home
│   ├── preferences/         # Preference editor page
│   ├── listings/            # Map + card grid
│   ├── costs/               # Cost dashboard
│   └── api/client.ts        # Auto-generated OpenAPI client
├── components/
│   ├── PreferenceForm.tsx
│   ├── ListingCard.tsx
│   ├── Map.tsx
│   └── ...
└── styles/
    └── globals.css          # Tailwind + custom vars
```

### Database

SQLite (local) or Postgres (swap-in):

```
preferences (user searches)
property_managers (discovery cache)
extraction_strategies (LLM-generated scrapers)
listings (pulled + scored)
costs (LLM calls + API usage)
embeddings (soft-preference pre-filters)
extraction_feedback (validation results)
```

See `alembic/versions/` for schema.

---

## Development

### Commands

```bash
# Setup
uv sync --extra dev

# Run dev server
uv run uvicorn doormat.main:app --reload --host 0.0.0.0 --port 8000

# Tests
uv run pytest                          # All tests
uv run pytest tests/test_main.py       # Single file
uv run pytest -k "test_health"         # Single test

# Lint + format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type check
uv run mypy src/ --strict

# Migrations
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
uv run alembic downgrade -1
```

### Project Structure

- `BUILD-GUIDE.md` — Complete implementation guide + prompts
- `CLAUDE.md` — AI patterns + architecture decisions
- `PROMPTS.md` — Full prompt library (discovery, extraction, scoring)
- `AGENTS.md` — MCP server specification + Claude Desktop integration
- `COST-GUIDE.md` — Cost optimization strategies
- `.specify/memory/` — Specification, plan, tasks, constitution (speckit)

### Code Quality

- **Linting**: Ruff (line-length 100)
- **Type checking**: mypy strict mode
- **Tests**: pytest with asyncio_mode="auto"
- **Commits**: Conventional Commits (feat/fix/docs/refactor)

---

## Integration: Claude Desktop

Wire Doormat into Claude Desktop:

1. **Start Doormat**:
   ```bash
   docker compose up
   ```

2. **Configure Claude Desktop**:

   **macOS**: `~/.config/Claude/claude_desktop_config.json`

   **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

   ```json
   {
     "mcpServers": {
       "doormat": {
         "command": "python",
         "args": ["-m", "doormat.mcp_server"],
         "env": {
           "DOORMAT_API_URL": "http://localhost:8000"
         }
       }
     }
   }
   ```

3. **Restart Claude Desktop**

4. **In Claude**:
   ```
   User: "Find me 2-bed rentals in San Francisco under $3000"

   Claude: I'll search for rentals using Doormat...
   [Calls MCP tool: discover_city, score_listings]

   Here are your top matches:
   1. 123 Main St - $2,800/mo - ✓ Perfect match
   ...
   ```

See `AGENTS.md` for full MCP specification.

---

## Deployment

### Local Machine

```bash
docker compose up
```

Data stored in `doormat.db` (local volume).

### Self-Hosted VPS

```bash
# On $5 DigitalOcean VPS
git clone https://github.com/josh-sepirak/Doormat.git
cd Doormat

# Set env vars
nano .env
# Add OPENROUTER_API_KEY=...

# Run
docker compose -f docker-compose.yml up -d

# Access via
open https://your-vps-ip:3000
```

### Optional: Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
    }

    location /api {
        proxy_pass http://localhost:8000;
    }
}
```

---

## Security

### Default: Localhost Only

By default, Doormat only listens on `127.0.0.1:8000` and `127.0.0.1:3000`. No remote access.

### Optional: Bearer Token Auth

For self-hosters exposing over network:

```env
# .env
AUTH_MODE=bearer
BEARER_TOKEN=sk-doormat-very-long-secret-here
```

Then include header on all requests:
```
Authorization: Bearer sk-doormat-very-long-secret-here
```

### API Keys

OpenRouter key is stored in `.env`. **Never commit `.env`.**

Optional: rotate token weekly via:
```bash
doormat rotate-token
```

### Responsible Scraping

Doormat respects:
- `robots.txt` (no aggressive scraping)
- Per-domain rate limits (backoff on 429)
- No authentication bypass
- No CAPTCHA solving

See `responsible-use.md` for legal context.

---

## Troubleshooting

### "Discovery taking too long"

Normal: discovery runs 1-3 minutes per city. Browser-Use is navigating, taking screenshots, analyzing sites. This is the hardest part; all future runs are cached.

Check logs:
```bash
docker logs doormat-api
```

### "Extractions failing"

1. Check if extraction rate is < 80% (Tier 2 validation)
2. Try forcing strategy refinement:
   ```
   doormat refine-strategy --property-manager "Downtown Properties"
   ```
3. Report to GitHub Issues with logs

### "Dashboard shows no listings"

1. Check if discovery completed:
   ```bash
   curl http://localhost:8000/api/discovery/cities/San%20Francisco/managers
   ```
2. Check if extraction ran:
   ```bash
   curl http://localhost:8000/api/listings?city=San%20Francisco
   ```
3. Check logs for errors

### "Docker won't start"

```bash
# Rebuild
docker compose down -v
docker compose up --build

# Check for port conflicts
lsof -i :8000
lsof -i :3000
```

---

## Cost Transparency

All LLM costs are visible in the **Cost Dashboard** (in-app):

```
Daily Spend:
  Today: $0.32
  This month: $12.50
  YTD: $12.50

By Component:
  Discovery: 3 runs, $0.09
  Extraction: 1500 listings, $0.45
  Scoring: 400 results, $0.80

Model Routing:
  Claude Haiku: $0.04 (extraction)
  Claude 3.5 Sonnet: $1.50 (scoring + validation)
  Gemma-free: $0.00 (discovery)

Cache Hit Rate: 32%
```

No surprises. All costs tracked per LLM call.

---

## FAQ

### Is this free?

Free to run locally + MIT license. You pay OpenRouter for LLM calls (typically <$1/mo).

### Can I use this commercially?

Yes, Apache 2.0 license allows commercial use. Each underlying rental source has its own ToS.

### Can I scrape my city's apartment forum?

Probably. Add the URL, let the discovery agent analyze it, and it'll generate a scraper if the site is public.

### Does this work for international rentals?

Not yet. v0.2 target. Currently: US cities only.

### Can I modify the prompts?

Yes. Edit `src/backend/prompts/*.yaml`, rebuild, deploy.

### How do I report issues?

GitHub Issues: https://github.com/josh-sepirak/Doormat/issues

---

## Learning More

- **`BUILD-GUIDE.md`** — Complete architecture, prompts, and 6-week build plan
- **`PROMPTS.md`** — Full prompt library (discovery, extraction, scoring)
- **`AGENTS.md`** — MCP server spec for Claude Desktop integration
- **`CLAUDE.md`** — For Claude Code: commands, patterns, architecture
- **`COST-GUIDE.md`** — Cost optimization strategies
- **`.specify/memory/`** — Specification, plan, tasks, constitution (speckit)

---

## Contributing

1. Fork repo
2. Create feature branch: `git checkout -b feat/my-feature`
3. Follow conventions: Conventional Commits, Ruff format, mypy strict
4. Write tests for new features
5. Ensure all tests pass: `uv run pytest`
6. Submit PR

See `BUILD-GUIDE.md` for architecture guidance.

---

## License

Apache 2.0 (includes patent grant). See `LICENSE`.

---

## Author

Built by [Josh Sepirak](https://twitter.com/josh_sepirak). Started as a Zo Computer skill to find an apartment in Redding, CA. Now open-source.

---

## What's Next?

- **v0.2** (Q2 2026): Conversational refinement sidebar, international support
- **v0.3** (Q3 2026): Multi-user with per-user preferences, advanced filtering
- **v1.0** (Q4 2026): Production-grade with 100K+ listings/month, <$0.50 cost

Join the conversation: GitHub Discussions or Twitter.

---

**Ready to find your perfect rental?**

```bash
docker compose up
# Open http://localhost:3000
```

Welcome to Doormat. 🚪