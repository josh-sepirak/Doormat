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
        model: str = DEFAULT_MODEL,
        response_model: Optional[type[T]] = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str | T:
        """Run a chat completion. Returns a Pydantic model when `response_model` set.

        All token usage is tracked via `track_cost()`.
        """
        logger.info(
            "llm_call_start",
            model=model,
            message_count=len(messages),
            structured=response_model is not None,
        )

        prompt_tokens = _estimate_prompt_tokens(messages)
        completion_tokens = 0

        try:
            if response_model is not None:
                parsed: T = await self._instructor_client.chat.completions.create(
                    model=model,
                    messages=cast(Any, messages),
                    response_model=response_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                completion_tokens = _estimate_completion_tokens(parsed.model_dump_json())
                logger.info(
                    "llm_call_complete",
                    model=model,
                    completion_tokens=completion_tokens,
                    structured=True,
                )
            else:
                response = await self._raw_client.chat.completions.create(
                    model=model,
                    messages=cast(Any, messages),
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                content = response.choices[0].message.content or ""
                completion_tokens = _estimate_completion_tokens(content)
                logger.info(
                    "llm_call_complete",
                    model=model,
                    completion_tokens=completion_tokens,
                    structured=False,
                )
        except Exception as exc:
            logger.error("llm_call_failed", model=model, error=str(exc))
            raise

        # Track cost after we have actual completion tokens
        async with track_cost(
            service="openrouter",
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ):
            pass

        # Return the result (stored above)
        if response_model is not None:
            return parsed
        else:
            return content


_CLIENT_SINGLETON: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Return the process-wide LLMClient singleton."""
    global _CLIENT_SINGLETON
    if _CLIENT_SINGLETON is None:
        _CLIENT_SINGLETON = LLMClient()
    return _CLIENT_SINGLETON


def reset_llm_client() -> None:
    """Reset the singleton (used in tests)."""
    global _CLIENT_SINGLETON
    _CLIENT_SINGLETON = None


def _estimate_prompt_tokens(messages: list[dict[str, str]]) -> int:
    """Roughly estimate prompt tokens (chars / 4)."""
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return max(1, total_chars // 4)


def _estimate_completion_tokens(text: str) -> int:
    """Roughly estimate completion tokens from a text body."""
    return max(1, len(text) // 4)
