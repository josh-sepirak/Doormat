# Interactive agent runs — quickstart

## Prerequisites

- Backend running (`uv run uvicorn doormat.main:app --reload --host 0.0.0.0 --port 8000`).
- Frontend dev server (`npm run dev` in `src/frontend`) with `NEXT_PUBLIC_API_URL` pointing at the API if not localhost:8000.
- At least one preference with city and OpenRouter key (Dashboard prerequisites unchanged).

## Flow

1. **Start a run** — From the Dashboard, use **Run discovery**. This calls `POST /api/search-runs` (durable parent run + discovery) and opens the run report for that id.
2. **Navigate away** — Open Costs, Preferences, or Listings. Within a few seconds the **active run strip** at the top should show stage, counters, elapsed time, cost, **Open report**, and **Stop run**.
3. **Reload** — Hard reload any page; the strip should repopulate from `GET /api/search-runs/active` once a run is still non-terminal.
4. **Stop** — Click **Stop run** on the strip or the report. The run moves to cancel-requested, then `cancelled` when the backend finishes the current unit (see `POST /api/search-runs/{id}/stop`).
5. **Review** — The report page polls `GET /api/search-runs/{id}` and `/events` for live activity, warnings, suggestions, filter controls, and expandable technical details. Use **Browse listings by category** to open Listings with `?run=` and category tabs.

## Manual success criteria (SC-001–SC-008)

| ID   | Check |
|------|--------|
| SC-001 | Start run → strip appears ≤ ~5s on other routes. |
| SC-002 | Report shows stage, counters, and recent user-visible events. |
| SC-003 | Stop → status shows stopping, then terminal cancelled with partial counters preserved. |
| SC-004 | Listings by run show category tabs and structured filter reasons when present. |
| SC-005 | Suggestions block shows early vs final copy without implying extra LLM spend. |
| SC-006 | PATCH filters on an active run bumps revision and updates counters when reclassification runs. |
| SC-007 | Developer payloads stay behind the technical disclosure; no raw secrets in UI. |
| SC-008 | Keyboard focus visible on links/buttons; dark mode readable; layout usable at ~375px width. |

**Gaps:** None recorded in this pass beyond “requires real discovery data” for full classification volume.

## Regenerating the OpenAPI client

From repo root:

```bash
PYTHONPATH=src/backend uv run python -c "import json; from doormat.main import app; json.dump(app.openapi(), open('src/frontend/openapi.json','w'), indent=2)"
cd src/frontend && npx openapi-ts -i openapi.json -o ./src/client -c @hey-api/client-fetch
```

Re-add or verify `src/frontend/src/client/search-runs.ts` (hand-written fetch helpers) still exists after generation; the generator overwrites only its own bundle files but may remove untracked extras if the output dir is wiped—keep `search-runs.ts` in version control.
