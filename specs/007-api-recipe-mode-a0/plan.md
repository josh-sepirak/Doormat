# Implementation Plan: API recipe + Mode A0

**Branch**: `007-api-recipe-mode-a0`  
**Spec**: [spec.md](./spec.md)  
**Reference patch**: [docs/patches/01-api-recipe-patch.md](../../docs/patches/01-api-recipe-patch.md)

## Architecture

Insert **Mode A0** before current Mode A in `extract_listing` flow:

```
Mode A0 (httpx + ApiRecipe, no LLM) → miss
  → Mode A (HTML + LLM) → low confidence / fail
    → Mode B (Browser-Use + LLM + optional network capture)
      → StrategyUpdate (+ optional ApiRecipe) → merge with validation gate
```

## Doormat-specific decisions

1. **Rent vs price**: `ExtractedListing` uses **`rent`** (`int`). Any `recipe_executor` code must match; ORM listing still uses **`price`** float at persist time in `_save_listing` — follow existing mapping in orchestrator.
2. **Strategy storage**: Today strategies are **`ExtractionStrategy` ORM rows** with `strategy_json` dict shape `field_selectors`, `pre_extraction_actions`, `notes`. Add **`api_recipe`** into that JSON **or** add `api_recipe_json` column — prefer one migration; keep `StrategyCache.merge` as single writer.
3. **Alembic**: Place revision in **`alembic/versions/`** with `render_as_batch=True` patterns used elsewhere.
4. **Prompts**: Repo uses `llm/prompt_registry.py` for defaults; patch mentions `prompts/extraction/listing-extraction.md` — add Mode B network guidance to **registry defaults** and optional file under `prompts/` if the project still mirrors docs.
5. **Tests**: Add `httpx`/`respx` tests; optional `pytest` dev dep if not present. Patch sample uses `respx` — add to dev deps if needed.

## Phased delivery (maps to patch steps)

| Phase | Patch steps | Goal |
|-------|-------------|------|
| **A — Foundations** | 1, 3 (+ executor inline), 10 (partial) | Schemas, pure `recipe_executor`, `recipe_validator`, unit tests; no runtime behavior change |
| **B — Mode A0 + orchestrator** | 5, 7 | `mode_a0.py`, orchestrator tries A0 first; can ship behind flag default **off** |
| **C — Network capture + Mode B** | 2, 4, 8 | CDP/Playwright capture, synthesis helpers, prompt text |
| **D — Merge + DB** | 6, 9 | Recipe validation in `StrategyCache.merge`, Alembic, rejections audit table optional |
| **E — Rollout** | 11 | `config.py` flags, metrics, dashboard hooks |

### Rollout strategy (from patch)

1. Land A + tests.  
2. Land B with `api_recipe_enabled=False`.  
3. Land C + D; enable for one source in dev.  
4. Enable globally after soak; tighten `api_recipe_promotion_requires_held_out` when enough listings exist.

## Risks

- Browser-Use session may not expose CDP hooks — Playwright fallback required.
- Recipe inference (`_infer_field_paths`) is heuristic; tests and fixtures critical.

## Quality gates

- `uv run pytest` passes including new `tests/extraction/test_api_recipe.py`
- `uv run ruff check` / `mypy` clean for touched modules
- No regression in extraction tests when flag off
