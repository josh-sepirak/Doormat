"""Retry logic and error handling for external API calls."""

import structlog
from typing import Callable, TypeVar, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

logger = structlog.get_logger(__name__)

T = TypeVar("T")


def retry_on_transient_error(
    func: Callable[..., T],
    max_attempts: int = 3,
    base_delay_seconds: float = 1.0,
) -> Callable[..., T]:
    """Decorator to retry a function with exponential backoff.

    Retries on transient errors (ConnectionError, TimeoutError, etc).

    Args:
        func: Function to retry
        max_attempts: Maximum number of attempts
        base_delay_seconds: Initial delay between retries

    Usage:
        @retry_on_transient_error
        async def call_llm():
            return await llm_client.complete(...)
    """

    @retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=base_delay_seconds, max=60),
        retry=retry_if_exception_type(
            (ConnectionError, TimeoutError, OSError, IOError)
        ),
        reraise=True,
    )
    async def wrapper(*args, **kwargs):
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

    return wrapper


def get_retry_decorator(
    max_attempts: int = 3,
    base_delay_seconds: float = 1.0,
):
    """Get a retry decorator with custom parameters.

    Usage:
        @get_retry_decorator(max_attempts=5, base_delay_seconds=2.0)
        async def risky_operation():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=base_delay_seconds, max=60),
            retry=retry_if_exception_type(
                (ConnectionError, TimeoutError, OSError, IOError)
            ),
            reraise=True,
        )
        async def wrapper(*args, **kwargs):
            attempt = 0
            last_error = None

            while attempt < max_attempts:
                attempt += 1
                try:
                    logger.debug(
                        "retry_attempt",
                        func=func.__name__,
                        attempt=attempt,
                        max_attempts=max_attempts,
                    )
                    return await func(*args, **kwargs)
                except (ConnectionError, TimeoutError, OSError, IOError) as e:
                    last_error = e
                    if attempt < max_attempts:
                        delay = base_delay_seconds * (2 ** (attempt - 1))
                        logger.warning(
                            "retry_backoff",
                            func=func.__name__,
                            attempt=attempt,
                            max_attempts=max_attempts,
                            delay_seconds=delay,
                            error=str(e),
                        )
                        import asyncio

                        await asyncio.sleep(delay)
                    else:
                        break

            if last_error:
                logger.error(
                    "retry_failed",
                    func=func.__name__,
                    attempts=max_attempts,
                    error=str(last_error),
                )
                raise last_error

        return wrapper

    return decorator
