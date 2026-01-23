"""Rate limiting module for Codebase State Manager.

Provides thread-safe rate limiting to prevent abuse and brute force attacks.
Implements a sliding window algorithm with in-memory storage.
"""

import threading
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Callable


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting on a specific endpoint."""

    requests: int
    seconds: int
    window_name: str = "default"


@dataclass
class RateLimitEntry:
    """Entry for tracking rate limit usage."""

    count: int = 0
    window_start: float = field(default_factory=time.time)


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, retry_after: int, limit: int, window: int) -> None:
        self.retry_after = retry_after
        self.limit = limit
        self.window = window
        super().__init__(
            f"Rate limit exceeded. Limit: {limit} requests per {window}s. "
            f"Retry after {retry_after} seconds."
        )


class RateLimiter:
    """Thread-safe rate limiter using sliding window algorithm."""

    DEFAULT_CONFIGS: dict[str, RateLimitConfig] = {
        "genesis": RateLimitConfig(requests=1, seconds=60, window_name="genesis"),
        "new_state_transition": RateLimitConfig(
            requests=10, seconds=60, window_name="state_transition"
        ),
        "arbitrary_state_transition": RateLimitConfig(
            requests=5, seconds=60, window_name="arbitrary_transition"
        ),
        "search_states": RateLimitConfig(requests=20, seconds=60, window_name="search"),
        "get_current_state_info": RateLimitConfig(requests=30, seconds=60, window_name="read"),
        "get_state_info": RateLimitConfig(requests=30, seconds=60, window_name="read"),
        "get_transition_info": RateLimitConfig(requests=30, seconds=60, window_name="read"),
        "total_states": RateLimitConfig(requests=30, seconds=60, window_name="read"),
        "track_transitions": RateLimitConfig(requests=30, seconds=60, window_name="read"),
        "get_state_transitions": RateLimitConfig(requests=30, seconds=60, window_name="read"),
        "default": RateLimitConfig(requests=100, seconds=60, window_name="default"),
    }

    def __init__(self, default_config: RateLimitConfig | None = None) -> None:
        self._lock = threading.Lock()
        self._clients: dict[str, dict[str, RateLimitEntry]] = {}
        self._configs = self.DEFAULT_CONFIGS.copy()
        if default_config:
            self._configs["default"] = default_config
        self._enabled = True

    def is_allowed(self, client_id: str, endpoint: str) -> tuple[bool, int]:
        """Check if a request is allowed for the given client and endpoint.

        Args:
            client_id: Unique identifier for the client (e.g., session ID)
            endpoint: Name of the endpoint being accessed

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        if not self._enabled:
            return True, 0

        config = self._configs.get(endpoint, self._configs["default"])
        current_time = time.time()

        with self._lock:
            client_entries = self._clients.setdefault(client_id, {})
            entry = client_entries.get(endpoint)

            if entry is None:
                client_entries[endpoint] = RateLimitEntry(
                    count=1,
                    window_start=current_time,
                )
                return True, 0

            if current_time - entry.window_start >= config.seconds:
                entry.count = 1
                entry.window_start = current_time
                return True, 0

            entry.count += 1

            if entry.count > config.requests:
                retry_after = int(config.seconds - (current_time - entry.window_start))
                return False, max(1, retry_after)

            return True, 0

    def check_rate_limit(self, client_id: str, endpoint: str) -> None:
        """Check rate limit and raise if exceeded.

        Args:
            client_id: Unique identifier for the client
            endpoint: Name of the endpoint

        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        config = self._configs.get(endpoint, self._configs["default"])
        is_allowed, retry_after = self.is_allowed(client_id, endpoint)

        if not is_allowed:
            raise RateLimitExceeded(
                retry_after=retry_after,
                limit=config.requests,
                window=config.seconds,
            )

    def get_remaining(self, client_id: str, endpoint: str) -> int:
        """Get remaining requests for a client on an endpoint.

        Args:
            client_id: Unique identifier for the client
            endpoint: Name of the endpoint

        Returns:
            Number of remaining requests in the current window
        """
        config = self._configs.get(endpoint, self._configs["default"])
        current_time = time.time()

        with self._lock:
            client_entries = self._clients.get(client_id, {})
            entry = client_entries.get(endpoint)

            if entry is None:
                return config.requests

            if current_time - entry.window_start >= config.seconds:
                return config.requests

            return max(0, config.requests - entry.count)

    def reset(self, client_id: str | None = None, endpoint: str | None = None) -> None:
        """Reset rate limit tracking for a client or endpoint.

        Args:
            client_id: Specific client to reset, or None for all
            endpoint: Specific endpoint to reset, or None for all
        """
        with self._lock:
            if client_id is None:
                self._clients.clear()
            elif endpoint is None:
                self._clients.pop(client_id, None)
            else:
                if client_id in self._clients:
                    self._clients[client_id].pop(endpoint, None)
                    if not self._clients[client_id]:
                        self._clients.pop(client_id, None)

    def set_config(self, endpoint: str, config: RateLimitConfig) -> None:
        """Set or update rate limit configuration for an endpoint.

        Args:
            endpoint: Name of the endpoint
            config: Rate limit configuration
        """
        with self._lock:
            self._configs[endpoint] = config

    def get_config(self, endpoint: str) -> RateLimitConfig:
        """Get rate limit configuration for an endpoint.

        Args:
            endpoint: Name of the endpoint

        Returns:
            Rate limit configuration
        """
        return self._configs.get(endpoint, self._configs["default"])

    def enable(self) -> None:
        """Enable rate limiting."""
        self._enabled = True

    def disable(self) -> None:
        """Disable rate limiting (for testing)."""
        self._enabled = False

    def is_enabled(self) -> bool:
        """Check if rate limiting is enabled.

        Returns:
            True if rate limiting is enabled
        """
        return self._enabled


def rate_limit(
    endpoint_name: str,
    client_id_param: str = "client_id",
) -> Callable:
    """Decorator to apply rate limiting to a function.

    Args:
        endpoint_name: Name of the endpoint for rate limiting
        client_id_param: Name of the parameter containing client ID

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            from src.mcp_server.utils.security import get_rate_limiter

            rate_limiter = get_rate_limiter()
            client_id = kwargs.get(client_id_param, "default")

            rate_limiter.check_rate_limit(client_id, endpoint_name)

            try:
                result = func(*args, **kwargs)
                return result
            except Exception:
                raise

        return wrapper

    return decorator


_rate_limiter: RateLimiter | None = None
_rate_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance.

    Returns:
        RateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        with _rate_limiter_lock:
            if _rate_limiter is None:
                _rate_limiter = RateLimiter()
    return _rate_limiter


def set_rate_limiter(rate_limiter: RateLimiter) -> None:
    """Set the global rate limiter instance (for testing).

    Args:
        rate_limiter: RateLimiter instance to set
    """
    global _rate_limiter
    _rate_limiter = rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter (for testing)."""
    global _rate_limiter
    _rate_limiter = None
