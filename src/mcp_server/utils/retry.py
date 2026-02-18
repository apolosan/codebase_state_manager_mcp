"""Retry mechanism with exponential backoff for SQLite operations.

Handles transient failures like database locks with automatic retry.
"""

import functools
import logging
import time
from typing import Any, Callable, Optional, TypeVar

from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_on_lock(
    max_retries: int = 3,
    initial_delay: float = 0.1,
    backoff_factor: float = 2.0,
    max_delay: float = 2.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to retry operations that fail due to SQLite locks.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 0.1)
        backoff_factor: Multiplier for delay after each retry (default: 2.0)
        max_delay: Maximum delay between retries in seconds (default: 2.0)

    Example:
        @retry_on_lock(max_retries=5, initial_delay=0.05)
        def create_state(self, state: State) -> bool:
            # SQLite operation that might lock
            ...

    Returns:
        Decorated function that retries on OperationalError with "database is locked".
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception: Optional[Exception] = None

            for attempt in range(max_retries + 1):  # +1 for initial attempt
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    last_exception = e
                    error_msg = str(e).lower()

                    # Only retry on database lock errors
                    if "database is locked" not in error_msg:
                        raise

                    # Don't sleep after the last attempt
                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__}: SQLite locked on attempt {attempt + 1}/{max_retries + 1}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        logger.error(
                            f"{func.__name__}: SQLite locked after {max_retries + 1} attempts. Giving up."
                        )

            # If we exhausted all retries, raise the last exception
            if last_exception:
                raise last_exception

            # This should never happen, but satisfy type checker
            raise RuntimeError(f"{func.__name__}: Unexpected state in retry logic")

        return wrapper

    return decorator


class RetryConfig:
    """Global retry configuration for SQLite operations."""

    # Default values
    MAX_RETRIES = 3
    INITIAL_DELAY = 0.1
    BACKOFF_FACTOR = 2.0
    MAX_DELAY = 2.0

    @classmethod
    def set_defaults(
        cls,
        max_retries: Optional[int] = None,
        initial_delay: Optional[float] = None,
        backoff_factor: Optional[float] = None,
        max_delay: Optional[float] = None,
    ):
        """Update global retry configuration.

        Args:
            max_retries: Maximum retry attempts
            initial_delay: Initial delay in seconds
            backoff_factor: Delay multiplier for each retry
            max_delay: Maximum delay between retries
        """
        if max_retries is not None:
            cls.MAX_RETRIES = max_retries
        if initial_delay is not None:
            cls.INITIAL_DELAY = initial_delay
        if backoff_factor is not None:
            cls.BACKOFF_FACTOR = backoff_factor
        if max_delay is not None:
            cls.MAX_DELAY = max_delay

    @classmethod
    def get_retry_decorator(cls) -> Callable:
        """Get retry decorator with current global configuration.

        Returns:
            Configured retry_on_lock decorator.
        """
        return retry_on_lock(
            max_retries=cls.MAX_RETRIES,
            initial_delay=cls.INITIAL_DELAY,
            backoff_factor=cls.BACKOFF_FACTOR,
            max_delay=cls.MAX_DELAY,
        )
