# Implementation Plan: Contribute rental source

**Branch**: `008-contribute-rental-source`  
**Spec**: [spec.md](./spec.md)  
**Reference patch**: [docs/patches/02-contributor-skill.md](../../docs/patches/02-contributor-skill.md)

## Approach

Ship the **skill + scripts + docs** as additive files. **Adapt** patch code that assumes non-existent APIs:

| Patch assumes | Doormat today |
|---------------|----------------|
| `StrategyAdapter.from_json` in `sources/pm/` | May not exist — either implement a thin loader that builds the same JSON `StrategyCache` expects, or document “import JSON into DB via admin/script” for v1. |
| `run_mode_a(html, strategy, llm_client)` | Actual signature uses `PropertyManager`, `Preference`, `get_effective_prompt`, etc. — `validate_strategy.py` must mirror **real** `run_mode_a` imports. |
| `pyproject` entry point per PM | Current codebase uses `sources/craigslist.py`, `sources/apify.py` patterns — prefer **one** generic “bundled strategy” mechanism over N entry points until needed. |
| browser-harness CLI | Optional dev dependency; skill documents install from upstream repo. |

## Phases

| Phase | Deliverable |
|-------|-------------|
| **A** | `skills/contribute-rental-source/SKILL.md` + `references/` (schema notes aligned to `extraction/schemas.py` + ORM) |
| **B** | `scripts/preflight.py`, `scripts/scrub_fixture.py` (minimal deps) |
| **C** | `scripts/from_harness.py` — may require `selectolax`; selector heuristics per patch |
| **D** | `scripts/validate_strategy.py` integrated with **actual** Mode A |
| **E** | `docs/contributing/adding-a-source.md`, Makefile target, optional `docs/sources.md` stub |
| **F** | Pilot: one real or Redding-derived strategy + fixture PR checklist |

## Dependency on 007

- **Soft dependency**: ApiRecipe fields in contributed JSON are useful only after `007` ships. Until then, skill should still output HTML-only strategies.

## Quality gates

- Scripts runnable with `uv run python …` from repo root
- No real PII in committed fixtures (manual review + scrubber)
- Ruff/mypy on new Python modules
