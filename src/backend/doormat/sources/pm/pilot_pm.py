"""Adapter for pilot PM — demonstrates the contribution workflow."""

from doormat.sources.pm._strategy_adapter import StrategyAdapter

Adapter = StrategyAdapter.from_json("strategies/pilot-pm.json")
