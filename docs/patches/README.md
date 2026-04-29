# Browser-harness patches (reference)

This directory stores the **authoritative step-by-step patch documents** for two additive features. They are implementation guides, not product marketing.

| File | Feature | Primary win |
|------|---------|-------------|
| [01-api-recipe-patch.md](./01-api-recipe-patch.md) | Mode A0 HTTP recipe fast path + network capture in Mode B | Large extraction cost reduction on JSON-backed PM sites |
| [02-contributor-skill.md](./02-contributor-skill.md) | `contribute-rental-source` skill + contributor pipeline | Faster cold-starts and lower friction for curated strategies |

**Tracked implementation specs (Spec Kit style):** see `specs/007-api-recipe-mode-a0/` and `specs/008-contribute-rental-source/` for phased plans and tasks aligned with this repo.

## Recommended order

1. **Contributor skill (patch 2)** first if you want a working contribution loop and curated strategies before tuning recipes — ~2 days in the original estimate.
2. **API recipe (patch 1)** for the largest ongoing cost lever — ~2 weeks focused.

If you only pick one: **patch 1** (cost). If doing both: **patch 2 then patch 1** matches the patch author’s rollout advice.

## Delta: patches vs current Doormat

These patches **do not replace** what is already shipped. The running app (search runs, listings UI, Mode A / Mode B extraction, strategy merge, etc.) stays the default path. The patches **add**:

- **Patch 1:** a **third tier** (Mode A0) before HTML Mode A, plus CDP/network capture in Mode B and recipe validation on merge.
- **Patch 2:** a **human-in-the-loop** path to commit strategies + fixtures + docs as PRs, independent of runtime discovery.

**End-user impact:** Current Doormat is already “more advanced” for *using* the product (dashboard, runs, scoring). The patches make extraction **cheaper** and **community-extensible**; they are not required for correctness of the core loop.

## Path and schema adaptations (read before implementing)

When following `01-api-recipe-patch.md`, adapt names to this repository:

| Patch assumes | Doormat actually has |
|---------------|----------------------|
| `migrations/versions/` | `alembic/versions/` |
| Optional Pydantic `ExtractionStrategy` with `source_id`, `listing_index_url`, … | ORM `ExtractionStrategy` in `models/orm.py` with `strategy_json` (JSON text). Store `api_recipe` inside that JSON **or** add a column per migration — see spec `007` plan. |
| `ExtractedListing.price` in sample `recipe_executor` | `ExtractedListing.rent` in `extraction/schemas.py` — keep field names consistent with existing Mode A/B. |
| `StrategyCache.merge` signature | Current `merge(property_manager_id, update, …)` — extend; held-out listings need DB queries against real listings. |

Patch 2 references `StrategyAdapter.from_json`, `pyproject` entry points per source, and `selectolax` — none may exist yet; `specs/008` breaks work into phases that **fit** `doormat.sources` as it exists today.

## Related

- Legacy monolithic backlog: `.specify/memory/tasks.md` (not status-tracked; see `.specify/memory/speckit-reconciliation.md`).
- GitHub Spec Kit workflow: constitution → specify → plan → tasks → implement; community [presets](https://github.com/github/spec-kit#-community-presets) and extensions are optional add-ons.
