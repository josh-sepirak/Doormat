"""LLMClient wrapping the openai SDK pointed at OpenRouter.

All calls flow through `track_cost()` for cost accounting, and use `instructor`
when a `response_model` is supplied so structured Pydantic outputs are typed.
"""

from __future__ import annotations

from typing import Any, Optional, TypeVar, cast

import instructor
import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel

from doormat.config import settings
from doormat.cost_tracking import track_cost

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "openai/gpt-4o-mini"
MODEL_CHEAP = "openai/gpt-4o-mini"
MODEL_REASONING = "anthropic/claude-3.5-sonnet"


def route_model(task: str) -> str:
    """Route a task to the most cost-effective model.

    Tasks:
    - discovery: finding property managers (simple, high volume) -> CHEAP
    - extraction: parsing listing data (medium complexity) -> CHEAP/REASONING
    - scoring: ranking vs preferences (high reasoning) -> REASONING
    """
    if task == "scoring":
        return MODEL_REASONING
    return MODEL_CHEAP


class LLMClient:
    """Async LLM client backed by OpenRouter via the openai SDK.

    Uses `instructor.from_openai` patching when a Pydantic `response_model` is
    requested, so callers receive a typed BaseModel instance.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or settings.OPENROUTER_API_KEY
        self._base_url = base_url or settings.OPENROUTER_BASE_URL
        self._raw_client: AsyncOpenAI = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
        )
        self._instructor_client = instructor.from_openai(self._raw_client)

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        task: str = "unknown",
        response_model: Optional[type[T]] = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        component: str = "unknown",
        city: Optional[str] = None,
        cache_system_prompt: bool = False,
    ) -> str | T:
        """Run a chat completion. Returns a Pydantic model when `response_model` set.

        If model is not provided, it is routed based on the 'task'.
        All token usage is tracked via `track_cost()`.
        """
        model = model or route_model(task)
        effective_messages = _apply_cache_control(messages, model, cache_system_prompt)

        logger.info(
            "llm_call_start",
            model=model,
            task=task,
            message_count=len(messages),
            structured=response_model is not None,
            component=component,
            city=city,
        )

        prompt_tokens = 0
        completion_tokens = 0
        reported_cost_usd: float | None = None
        content: str = ""
        parsed: Optional[T] = None

        async with track_cost(
            service="openrouter",
            model=model,
            completion_tokens=completion_tokens,
            component=component,
            city=city,
        ) as cost:
            try:
                if response_model is not None:
                    # Use instructor with completion to get usage
                    (
                        parsed,
                        completion,
                    ) = await self._instructor_client.chat.completions.create_with_completion(
                        model=model,
                        messages=cast(Any, effective_messages),
                        response_model=response_model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    if completion.usage:
                        prompt_tokens = completion.usage.prompt_tokens
                        completion_tokens = completion.usage.completion_tokens
                        reported_cost_usd = _usage_cost_usd(completion.usage)
                        cache_read = getattr(completion.usage, "cache_read_input_tokens", 0) or 0
                        cache_creation = (
                            getattr(completion.usage, "cache_creation_input_tokens", 0) or 0
                        )
                        cost.cache_hit = cache_read > 0
                        cost.cache_read_tokens = cache_read
                        cost.cache_creation_tokens = cache_creation
                else:
                    response = await self._raw_client.chat.completions.create(
                        model=model,
                        messages=cast(Any, effective_messages),
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    content = response.choices[0].message.content or ""
                    if response.usage:
                        prompt_tokens = response.usage.prompt_tokens
                        completion_tokens = response.usage.completion_tokens
                        reported_cost_usd = _usage_cost_usd(response.usage)
                        cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
                        cache_creation = (
                            getattr(response.usage, "cache_creation_input_tokens", 0) or 0
                        )
                        cost.cache_hit = cache_read > 0
                        cost.cache_read_tokens = cache_read
                        cost.cache_creation_tokens = cache_creation
                cost.prompt_tokens = prompt_tokens
                cost.completion_tokens = completion_tokens
                cost.cost_usd = reported_cost_usd
                logger.info(
                    "llm_call_complete",
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=reported_cost_usd,
                    cache_hit=cost.cache_hit,
                    cache_read_tokens=cost.cache_read_tokens,
                )
            except Exception as exc:
                logger.error("llm_call_failed", model=model, error=str(exc))
                raise

        if response_model is not None:
            if parsed is None:
                raise RuntimeError("Structured LLM response was empty")
            return parsed
        return content


_CLIENT_SINGLETON: Optional[LLMClient] = None


def get_llm_client(api_key: Optional[str] = None) -> LLMClient:
    """Return an LLMClient.

    If *api_key* is provided (e.g. from a user's stored preference), a fresh
    client is created with that key.  Otherwise the process-wide singleton
    backed by the .env OPENROUTER_API_KEY is returned.
    """
    if api_key:
        return LLMClient(api_key=api_key)

    global _CLIENT_SINGLETON
    if _CLIENT_SINGLETON is None:
        _CLIENT_SINGLETON = LLMClient()
    return _CLIENT_SINGLETON


def reset_llm_client() -> None:
    """Reset the singleton (used in tests)."""
    global _CLIENT_SINGLETON
    _CLIENT_SINGLETON = None


def _usage_cost_usd(usage: Any) -> float | None:
    """Extract OpenRouter-reported cost when available on the usage object."""
    value = getattr(usage, "cost", None)
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return max(float(value), 0.0)
    return None


def _estimate_prompt_tokens(messages: list[dict[str, str]]) -> int:
    """Roughly estimate prompt tokens (chars / 4)."""
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return max(1, total_chars // 4)


def _estimate_completion_tokens(text: str) -> int:
    """Roughly estimate completion tokens from a text body."""
    return max(1, len(text) // 4)


def _is_anthropic_model(model: str) -> bool:
    return "anthropic" in model.lower() or "claude" in model.lower()


def _apply_cache_control(
    messages: list[dict[str, str]],
    model: str,
    cache: bool,
) -> list[dict[str, Any]]:
    """Return messages with cache_control on the last system message for Anthropic models."""
    if not cache or not _is_anthropic_model(model):
        return cast(Any, messages)

    result: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") == "system":
            result.append(
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": msg["content"],
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                }
            )
        else:
            result.append(cast(Any, msg))
    return result
