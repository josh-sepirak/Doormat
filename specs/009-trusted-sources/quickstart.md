# Quickstart: 009 Trusted sources & Craigslist regions

## Prerequisites

- Backend: `uv sync --extra dev`, `uv run alembic upgrade head`
- Frontend: `cd src/frontend && npm install`

## Manual verification (SC checklist)

1. **Lancaster, CA → Inland Empire**
   - Open **Sources** in the app nav (`/sources`).
   - **Add region**: City `Lancaster`, State `CA`, click **Suggest regions**.
   - Confirm **inland empire** appears in the top suggestions with a plausible distance.
   - Save, then run a search for city `Lancaster, CA` with Craigslist enabled; logs should not show the “Auto-routed Craigslist” warning for the wrong `lancaster.craigslist.org` PA site when this trusted row matches.

2. **Trusted PM URL**
   - Under **Property managers**, add a public listings page URL and city matching your preference.
   - Trigger a scrape run for that city; the PM should be scraped alongside discovery results (validated PM in DB).

3. **Preferences nudge**
   - With Craigslist enabled and **no** trusted Craigslist region for the preference city, Preferences shows an amber notice with **Confirm your Craigslist region** linking to `/sources` with query params.

4. **Regression**
   - With **no** trusted Craigslist rows, legacy auto-subdomain behavior still runs; a warning event may appear in the run feed suggesting `/sources`.

## API smoke (optional)

```bash
curl -s "http://localhost:8000/api/craigslist/regions?city=Lancaster&state=CA" | head
curl -s "http://localhost:8000/api/trusted-sources"
```

(Use `Authorization: Bearer …` if `AUTH_BEARER_TOKEN` is set.)
