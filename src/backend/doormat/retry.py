"""Retry logic and error handling for external API calls."""

from typing import Awaitable, Callable, TypeVar

import structlog
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)

T = TypeVar("T")


def get_retry_decorator(
    max_attempts: int = 3,
    base_delay_seconds: float = 1.0,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Get a retry decorator with custom parameters.

    Retries on transient errors with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        base_delay_seconds: Initial delay between retries

    Usage:
        @get_retry_decorator(max_attempts=5)
        async def risky_operation():
            ...
    """

    def decorator(
        func: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[T]]:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=base_delay_seconds, max=60),
            retry=retry_if_exception_type(
                (ConnectionError, TimeoutError, OSError, IOError)
            ),
            reraise=True,
        )
        async def wrapper(*args, **kwargs) -> T:  # type: ignore[misc]
            try:
                return await func(*args, **kwargs)
            except RetryError as e:
                logger.error(
                    "retry_exhausted",
                    func=func.__name__,
                    attempts=max_attempts,
                    error=str(e.last_attempt.exception()),
                )
                raise

        return wrapper  # type: ignore[return-value]

    return decorator
