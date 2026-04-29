"""Deterministic suggestions from aggregated per-run filter reasons (no LLM)."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.models.orm import RunListingResult, SearchRun
from doormat.runs import events as run_events
from doormat.runs import state as run_state


def aggregate_suggestions_from_results(rows: list[RunListingResult]) -> list[dict[str, Any]]:
    """Build lightweight suggestion objects from stored filter reasons JSON."""
    codes: Counter[str] = Counter()
    for row in rows:
        if not row.filter_reasons_json:
            continue
        try:
            reasons: list[dict[str, Any]] = json.loads(row.filter_reasons_json)
        except json.JSONDecodeError:
            continue
        for r in reasons:
            code = str(r.get("filter_code", "unknown"))
            codes[code] += 1

    suggestions: list[dict[str, Any]] = []
    if codes["max_rent"] + codes["max_rent_near"] > 0:
        n = codes["max_rent"] + codes["max_rent_near"]
        suggestions.append(
            {
                "kind": "raise_budget",
                "message": f"{n} listings are blocked primarily by max rent. Raising max rent slightly may add options.",
                "count": n,
            }
        )
    if codes["pets_unknown"] > 0:
        n = codes["pets_unknown"]
        suggestions.append(
            {
                "kind": "review_pet_policy",
                "message": f"{n} listings have unknown pet policies — review them instead of assuming failure.",
                "count": n,
            }
        )
    if codes["min_bedrooms"] + codes["min_bedrooms_near"] > 0:
        n = codes["min_bedrooms"] + codes["min_bedrooms_near"]
        suggestions.append(
            {
                "kind": "relax_bedrooms",
                "message": f"{n} listings miss bedroom minimum (some are near misses). Consider one fewer bedroom.",
                "count": n,
            }
        )
    if codes["low_score"] > 0:
        n = codes["low_score"]
        suggestions.append(
            {
                "kind": "soften_preferences",
                "message": f"{n} listings pass hard filters but score below your threshold. Soften scored preferences or lower the threshold.",
                "count": n,
            }
        )
    return suggestions


async def refresh_suggestions(
    session: AsyncSession,
    *,
    run_id: str,
    emitter: run_events.SearchRunEventEmitter | None = None,
) -> list[dict[str, Any]]:
    run = await session.get(SearchRun, run_id)
    if run is None:
        return []
    stmt = select(RunListingResult).where(
        RunListingResult.run_id == run_id,
        RunListingResult.revision == run.active_revision,
    )
    rows = list((await session.execute(stmt)).scalars().all())
    summary = {
        "revision": run.active_revision,
        "great_matches": run.great_matches,
        "worth_a_look": run.worth_a_look,
        "near_misses": run.near_misses,
        "filtered_out": run.filtered_out,
    }
    suggestions = aggregate_suggestions_from_results(rows)
    early = not run_state.terminal_suggestions_final(run.status)
    if emitter:
        await emitter.emit(
            "filter_summary_updated",
            "Filter summary updated",
            payload={"summary": summary, "early_signal": early},
        )
        await emitter.emit(
            "suggestion_updated",
            "Suggestions updated",
            payload={"suggestions": suggestions, "early_signal": early},
        )
    return suggestions
