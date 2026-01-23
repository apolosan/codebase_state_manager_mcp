"""Performance metrics module for Codebase State Manager.

Provides timing, counters, and performance tracking for monitoring
and optimization purposes.
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable


@dataclass
class Timer:
    """Simple timer for measuring elapsed time."""

    start_time: float = field(default_factory=time.perf_counter)
    end_time: float = 0.0
    elapsed_ms: float = 0.0

    def stop(self) -> float:
        """Stop the timer and return elapsed time in milliseconds."""
        self.end_time = time.perf_counter()
        self.elapsed_ms = (self.end_time - self.start_time) * 1000
        return self.elapsed_ms

    def reset(self) -> None:
        """Reset the timer."""
        self.start_time = time.perf_counter()
        self.end_time = 0.0
        self.elapsed_ms = 0.0

    @property
    def current_ms(self) -> float:
        """Get current elapsed time without stopping."""
        return (time.perf_counter() - self.start_time) * 1000


class MetricsCollector:
    """Collects and reports performance metrics."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._timings: list[dict] = []
        self._operations: dict[str, list[float]] = {}

    def increment(self, key: str, amount: int = 1) -> None:
        """Increment a counter.

        Args:
            key: Counter name
            amount: Amount to increment (default: 1)
        """
        self._counters[key] = self._counters.get(key, 0) + amount

    def decrement(self, key: str, amount: int = 1) -> None:
        """Decrement a counter.

        Args:
            key: Counter name
            amount: Amount to decrement (default: 1)
        """
        self._counters[key] = self._counters.get(key, 0) - amount

    def timing(self, key: str, duration_ms: float) -> None:
        """Record a timing measurement.

        Args:
            key: Operation name
            duration_ms: Duration in milliseconds
        """
        if key not in self._operations:
            self._operations[key] = []
        self._operations[key].append(duration_ms)

    @contextmanager
    def timer(self, key: str):
        """Context manager for timing an operation.

        Args:
            key: Operation name

        Yields:
            Timer instance
        """
        timer = Timer()
        try:
            yield timer
        finally:
            self.timing(key, timer.stop())

    def get_counter(self, key: str) -> int:
        """Get counter value.

        Args:
            key: Counter name

        Returns:
            Counter value or 0 if not set
        """
        return self._counters.get(key, 0)

    def get_timing_stats(self, key: str) -> dict | None:
        """Get statistics for an operation timing.

        Args:
            key: Operation name

        Returns:
            Dict with count, min, max, avg, p50, p95, p99 or None if no data
        """
        if key not in self._operations or not self._operations[key]:
            return None

        timings = sorted(self._operations[key])
        count = len(timings)

        return {
            "count": count,
            "min_ms": timings[0],
            "max_ms": timings[-1],
            "avg_ms": sum(timings) / count,
            "p50_ms": timings[count // 2],
            "p95_ms": timings[int(count * 0.95)],
            "p99_ms": timings[int(count * 0.99)] if count >= 100 else timings[-1],
        }

    def get_all_stats(self) -> dict[str, Any]:
        """Get all collected metrics.

        Returns:
            Dict with counters and timing stats
        """
        result: dict[str, Any] = {
            "counters": dict(self._counters),
            "timings": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for key in self._operations:
            stats = self.get_timing_stats(key)
            if stats:
                timings_dict = result["timings"]
                timings_dict[key] = stats

        return result

    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._timings.clear()
        self._operations.clear()


_metrics_collector = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector."""
    return _metrics_collector


def timed_operation(operation_name: str) -> Callable:
    """Decorator to time a function execution.

    Args:
        operation_name: Name for the timing metric

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            with get_metrics().timer(operation_name):
                return func(*args, **kwargs)

        return wrapper

    return decorator


class PerformanceMonitor:
    """High-level performance monitoring for the state manager."""

    def __init__(self, metrics: MetricsCollector | None = None) -> None:
        self._metrics = metrics or get_metrics()

    def record_state_transition(self, duration_ms: float) -> None:
        """Record a state transition timing.

        Args:
            duration_ms: Duration in milliseconds
        """
        self._metrics.timing("state_transition", duration_ms)
        self._metrics.increment("total_transitions")

    def record_database_query(self, query_type: str, duration_ms: float) -> None:
        """Record a database query timing.

        Args:
            query_type: Type of query (e.g., "get_state", "search")
            duration_ms: Duration in milliseconds
        """
        self._metrics.timing(f"db_query_{query_type}", duration_ms)

    def record_git_operation(self, operation: str, duration_ms: float) -> None:
        """Record a git operation timing.

        Args:
            operation: Git operation name (e.g., "clone", "diff")
            duration_ms: Duration in milliseconds
        """
        self._metrics.timing(f"git_{operation}", duration_ms)

    def get_transition_stats(self) -> dict | None:
        """Get state transition statistics.

        Returns:
            Timing stats or None if no data
        """
        return self._metrics.get_timing_stats("state_transition")

    def get_query_stats(self) -> dict:
        """Get all database query statistics.

        Returns:
            Dict of query type to stats
        """
        stats = {}
        for key in self._metrics._operations:
            if key.startswith("db_query_"):
                query_type = key.replace("db_query_", "")
                query_stats = self._metrics.get_timing_stats(key)
                if query_stats:
                    stats[query_type] = query_stats
        return stats

    def check_performance_thresholds(self) -> list[str]:
        """Check if performance is within acceptable thresholds.

        Returns:
            List of warnings for operations exceeding thresholds
        """
        warnings = []

        transition_stats = self.get_transition_stats()
        if transition_stats and transition_stats.get("p95_ms", 0) > 100:
            warnings.append(
                f"State transition p95 latency ({transition_stats['p95_ms']:.2f}ms) exceeds 100ms threshold"
            )

        query_stats = self.get_query_stats()
        for query_type, stats in query_stats.items():
            if stats.get("p95_ms", 0) > 50:
                warnings.append(
                    f"Query '{query_type}' p95 latency ({stats['p95_ms']:.2f}ms) exceeds 50ms threshold"
                )

        return warnings


from datetime import timezone
