# Tasks: Contribute rental source

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

---

## Phase A — Skill skeleton

- [x] **A1** Create `skills/contribute-rental-source/SKILL.md` (frontmatter + workflow; reference browser-harness install). *(Lives under `.claude/skills/contribute-rental-source/`.)*
- [x] **A2** Add `references/strategy-schema.md` documenting **this repo’s** `strategy_json` shape vs ORM.
- [x] **A3** Add `references/extraction-fixture-format.md` and `references/pr-template.md`.

---

## Phase B — Preflight + scrubber

- [x] **B1** Implement `scripts/preflight.py` (robots, HTTP status, login-wall heuristic). *(Skill path: `.claude/skills/contribute-rental-source/scripts/preflight.py`.)*
- [x] **B2** Implement `scripts/scrub_fixture.py` (PII patterns from patch; document manual review).

---

## Phase C — Harness → strategy JSON

- [x] **C1** Add dependencies (`selectolax` or chosen HTML lib) to `pyproject.toml` if not present.
- [x] **C2** Implement `scripts/from_harness.py` per patch; output path `strategies/` or `contrib/strategies/` (decide single convention in PR).
- [x] **C3** If `007` exists: optional `--api-*` flags emitting `api_recipe` compatible with `ApiRecipe` schema.

---

## Phase D — Validation script

- [x] **D1** Implement `scripts/validate_strategy.py` calling **actual** `run_mode_a` / session setup (may require test DB or mocked LLM — document in script header).
- [x] **D2** If `007` merged: optional recipe replay via `RecipeValidator`.

---

## Phase E — Docs + Makefile

- [x] **E1** Add `docs/contributing/adding-a-source.md`.
- [x] **E2** Add `add-source` helper: create root `Makefile` **or** `package.json` / `justfile` script (repo has no Makefile today).
- [x] **E3** Link skill from root `README.md` or `CONTRIBUTING.md` only if one exists (minimal touch).

---

## Phase F — Pilot contribution

- [x] **F1** Contribute one curated strategy + scrubbed fixture (e.g. Redding PM) as proof. *(See `strategies/pilot-pm.json`, `tests/fixtures/html/pilot-pm/`.)*
- [ ] **F2** Open tracking issue or doc note for remaining markets. *(Optional follow-up.)*

---

## Ordering

**A → B → C → D → E** in sequence; **F** after D validates.  
Parallel: **007** can land before **C3/D2** for full ApiRecipe support.
