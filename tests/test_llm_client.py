"""Tests for LLM client accounting behavior."""

from types import SimpleNamespace

import pytest

from doormat.config import settings
from doormat.cost_tracking import get_cost_tracker
from doormat.llm.client import LLMClient


class _FailingCompletions:
    async def create(self, **kwargs):
        raise RuntimeError("provider unavailable")


class _UsageCostCompletions:
    async def create(self, **kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))],
            usage=SimpleNamespace(
                prompt_tokens=100,
                completion_tokens=25,
                cost=0.00042,
            ),
        )


@pytest.mark.asyncio
async def test_llm_client_tracks_failed_calls(monkeypatch):
    """Provider errors should still be visible in cost/latency telemetry."""
    monkeypatch.setattr(settings, "TRACK_COSTS", False)
    get_cost_tracker().clear()
    client = object.__new__(LLMClient)
    client._raw_client = SimpleNamespace(chat=SimpleNamespace(completions=_FailingCompletions()))
    client._instructor_client = None

    with pytest.raises(RuntimeError):
        await client.complete(
            messages=[{"role": "user", "content": "hello"}],
            model="openai/gpt-4o-mini",
            component="test",
            city="Austin",
        )

    records = get_cost_tracker().records
    assert len(records) == 1
    assert records[0].status == "error"
    assert records[0].latency_ms > 0
    assert records[0].component == "test"


@pytest.mark.asyncio
async def test_llm_client_prefers_openrouter_reported_cost(monkeypatch):
    """OpenRouter's usage.cost is the source of truth when it is present."""
    monkeypatch.setattr(settings, "TRACK_COSTS", False)
    get_cost_tracker().clear()
    client = object.__new__(LLMClient)
    client._raw_client = SimpleNamespace(chat=SimpleNamespace(completions=_UsageCostCompletions()))
    client._instructor_client = None

    result = await client.complete(
        messages=[{"role": "user", "content": "hello"}],
        model="openai/gpt-4o-mini",
        component="test",
        city="Austin",
    )

    assert result == "hello"
    records = get_cost_tracker().records
    assert len(records) == 1
    assert records[0].prompt_tokens == 100
    assert records[0].completion_tokens == 25
    assert records[0].cost_usd == pytest.approx(0.00042)
    get_cost_tracker().clear()
