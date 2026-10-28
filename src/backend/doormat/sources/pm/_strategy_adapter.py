"""Adapter loader for static strategy JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class StrategyAdapter:
    """Loads a static strategy JSON file for contributed property manager sources."""

    def __init__(self, data: dict[str, Any], path: Path | str) -> None:
        self.data = data
        self.path = Path(path)

    @classmethod
    def from_json(cls, path: str | Path) -> StrategyAdapter:
        """Load strategy from JSON file path."""
        p = Path(path)
        if not p.is_absolute():
            # Resolve relative to repo root (5 levels up from sources/pm/_strategy_adapter.py)
            repo_root = Path(__file__).resolve().parents[4]
            candidate = repo_root / p
            if candidate.exists():
                p = candidate

        data: dict[str, Any] = {}
        if p.exists():
            with open(p, encoding="utf-8") as f:
                data = json.load(f)

        return cls(data=data, path=p)

    @property
    def strategy_data(self) -> dict[str, Any]:
        """Return the parsed strategy JSON."""
        return self.data
