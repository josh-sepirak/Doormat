# Speckit / `.specify/memory` reconciliation

**Created:** 2026-04-29

## Are there unfinished Speckit phases?

**Yes — in the sense of documentation, not necessarily engineering reality.**

- `.specify/memory/plan.md` lists six phases with **unchecked** checkboxes; nothing in that file records what shipped.
- `.specify/memory/tasks.md` is a **single 82-task master list** (Phases 1–6) with **no per-task completion state**. It reads like a full-project estimate from 2026-04-25, not a live sprint board.

The **codebase has outpaced** that document: FastAPI app, discovery, extraction (Mode A/B), scoring, search runs, frontend pages, costs, MCP script, etc. Treat the old tasks file as **historical planning**, not a source of truth for “what’s left.”

## What to use instead

| Artifact | Purpose |
|----------|---------|
| `CLAUDE.md` | How to run, test, and navigate the repo today |
| `specs/00x-*/` | Feature-level Spec Kit bundles (spec / plan / tasks) for **incremental** work |
| `docs/patches/` | Reference patches for browser-harness follow-ons (API recipe, contributor skill) |

## Suggested maintenance (optional)

1. **Archive** or rename `.specify/memory/tasks.md` to `tasks-legacy-2026-04-25.md` if it causes confusion.
2. **Refresh** `.specify/memory/plan.md` with a short “As-built” section, or replace with links to `specs/`.
3. Run **`/speckit.analyze`** (if your agent integration supports it) after adding new `specs/` features to check consistency.

New work for the HTTP recipe and contributor skill lives under **`specs/007-api-recipe-mode-a0/`** and **`specs/008-contribute-rental-source/`**.
