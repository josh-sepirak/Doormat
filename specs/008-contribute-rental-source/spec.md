# Feature Specification: Contribute rental source (skill + pipeline)

**Feature Branch**: `008-contribute-rental-source`  
**Created**: 2026-04-29  
**Status**: Draft  
**Input**: Enable contributors to add hand-curated PM strategies via browser-harness + PR-shaped artifacts. Reference: `docs/patches/02-contributor-skill.md`.

## Problem

Runtime discovery and Mode B work for the long tail but cost time and tokens on first run in a new city. Popular markets benefit from **version-controlled, tested strategies** shipped with the repo. Contributors need a **repeatable, low-code path** (skill + scripts) rather than writing Python adapters from scratch.

## User Scenarios & Testing

### User Story 1 — Contribute a PM site (Priority: P1)

As a contributor, I want to follow a documented skill that walks me from a PM URL to a **PR** containing strategy JSON, a scrubbed HTML fixture, and docs, so I can improve Doormat for my region without deep backend knowledge.

**Independent Test**: Run through preflight + fixture + validate script on a sample site (or mocked HTML) and produce artifacts that CI accepts.

**Acceptance Scenarios**:

1. **Given** a public listings site without login wall, **When** phases 1–7 complete, **Then** `strategies/<id>.json` and `tests/fixtures/html/<id>/sample.html` exist and validate.
2. **Given** robots.txt blocks scraping, **When** preflight runs, **Then** the skill stops with a clear message (no silent proceed).

---

### User Story 2 — Align with Doormat runtime (Priority: P1)

As a maintainer, I want contributed strategies to match **actual** `strategy_json` / adapter patterns in this repo, not a hypothetical `StrategyAdapter.from_json` unless we implement it.

**Independent Test**: `validate_strategy.py` calls real `run_mode_a` signature from `extraction/mode_a.py` with correct arguments (session, preference, etc.).

---

### User Story 3 — Optional ApiRecipe (Priority: P2)

As a contributor on a JSON-backed site, I want to attach a validated **ApiRecipe** during contribution **if** patch 007 exists; otherwise document that recipes are runtime-captured only.

**Independent Test**: If 007 is merged, optional `--api-*` flags work; if not, skill documents “defer API recipe to runtime Mode B.”

---

## Functional Requirements

1. **Skill package**: `.claude/skills/contribute-rental-source/` or `skills/contribute-rental-source/` per repo convention (project uses `.claude/skills/` for impeccable — check and align with AGENTS).
2. **Scripts**: `preflight.py`, `from_harness.py`, `scrub_fixture.py`, `validate_strategy.py` — dependencies (`selectolax`, etc.) declared in `pyproject.toml` if used.
3. **Docs**: `docs/contributing/adding-a-source.md` linking to the skill.
4. **Makefile**: `make add-source URL=…` convenience target.

## Non-Goals

- Replacing Apify-backed aggregators.
- Supporting authenticated listing portals in the contribution flow.

## References

- `docs/patches/02-contributor-skill.md`
- `src/backend/doormat/sources/` (existing adapter patterns)
- `specs/007-api-recipe-mode-a0/` (optional integration for ApiRecipe in strategies)
