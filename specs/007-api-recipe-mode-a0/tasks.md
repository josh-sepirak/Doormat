# Tasks: API recipe + Mode A0

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Legend: `[ ]` pending · `[x]` done

---

## Phase A — Foundations (no production behavior change)

- [x] **A1** Add `ApiRecipe` and extend `StrategyUpdate` in `extraction/schemas.py` (and align naming with `ExtractedListing.rent`).
- [x] **A2** Implement `extraction/recipe_executor.py` (JSON walk + `ExtractedListing` output).
- [x] **A3** Implement `extraction/recipe_validator.py` with `RecipeValidationResult`.
- [x] **A4** Add unit tests: executor, validator, listing-id URL helpers (see patch step 10); add `respx` to dev deps if missing.

---

## Phase B — Mode A0 + orchestrator wiring

- [x] **B1** Implement `extraction/mode_a0.py` (`run_mode_a0`, failure/success counters, retire after 3 failures).
- [x] **B2** Update `extraction/orchestrator.py`: call Mode A0 before Mode A; pass `httpx` client; preserve existing persist rules.
- [x] **B3** Wire `api_recipe_enabled` default **False** in `config.py` until Phase E.

---

## Phase C — Network capture + Mode B integration

- [x] **C1** Add `extraction/network_capture.py` (`NetworkCapture`, `CDPCapturer`, header scrubbing).
- [x] **C2** Integrate capture into `extraction/mode_b.py` (CDP `Network.*` handlers on Browser-Use root client; same-host filter; `getResponseBody` on `loadingFinished`; summary logs + reasoning note when listing-like JSON seen). *(Optional auto `api_recipe` synthesis deferred.)*
- [x] **C3** Update Mode B system/user prompts in `prompt_registry` (API-first recovery guidance). *(Mode B system prompt v2: JSON/XHR + `api_recipe` guidance.)*

---

## Phase D — Strategy merge + database

- [x] **D1** Extend `StrategyCache.merge` with recipe validation gate + held-out listing query (implement `_select_held_out_listings` against ORM).
- [x] **D2** Alembic migration: `api_recipe_json` on `extraction_strategies` (and optional `api_recipe_rejections` table per patch).
- [x] **D3** Load/save `api_recipe` in strategy JSON (de)serialization in `strategy.py`.

---

## Phase E — Rollout & observability

- [x] **E1** Feature flags + timeouts in `config.py` (`api_recipe_enabled`, `api_recipe_promotion_requires_held_out`, etc.).
- [x] **E2** Metrics or structured logs: `mode_a0_calls`, successes, fallthrough to A/B (extend `cost_tracking` or component tags). *(Structured logs in orchestrator / `mode_a0`.)*
- [x] **E3** Document flags in `CLAUDE.md` or COST-GUIDE snippet; enable default after validation.

---

## Dependency order

`A → B → (C ∥ partial D schema) → D → E`

**Remaining vertical slice:** **C2 + C3** (wire `network_capture` into Mode B + prompts) before relying on CDP-captured recipes in production.
