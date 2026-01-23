"""Unit tests for metrics module."""

import pytest

from src.mcp_server.utils.metrics import (
    MetricsCollector,
    PerformanceMonitor,
    Timer,
    get_metrics,
    timed_operation,
)


class TestTimer:
    """Tests for Timer class."""

    def test_timer_initial_state(self):
        """Test timer initial state."""
        timer = Timer()
        assert timer.elapsed_ms == 0.0

    def test_timer_stop(self):
        """Test timer stop returns elapsed time."""
        timer = Timer()
        timer.stop()
        assert timer.elapsed_ms >= 0

    def test_timer_reset(self):
        """Test timer reset."""
        timer = Timer()
        timer.stop()
        timer.reset()
        assert timer.elapsed_ms == 0.0

    def test_timer_current_ms(self):
        """Test current_ms returns elapsed without stopping."""
        timer = Timer()
        import time

        time.sleep(0.01)
        current = timer.current_ms
        assert current >= 10


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def test_increment_counter(self):
        """Test incrementing a counter."""
        collector = MetricsCollector()
        collector.increment("test_counter")
        assert collector.get_counter("test_counter") == 1

    def test_increment_by_amount(self):
        """Test incrementing by specific amount."""
        collector = MetricsCollector()
        collector.increment("test_counter", 5)
        assert collector.get_counter("test_counter") == 5

    def test_decrement_counter(self):
        """Test decrementing a counter."""
        collector = MetricsCollector()
        collector.increment("test_counter", 10)
        collector.decrement("test_counter", 3)
        assert collector.get_counter("test_counter") == 7

    def test_get_unset_counter(self):
        """Test getting an unset counter returns 0."""
        collector = MetricsCollector()
        assert collector.get_counter("unset_counter") == 0

    def test_timing_single_operation(self):
        """Test recording timing for a single operation."""
        collector = MetricsCollector()
        collector.timing("test_operation", 100.5)
        stats = collector.get_timing_stats("test_operation")

        assert stats is not None
        assert stats["count"] == 1
        assert stats["min_ms"] == 100.5
        assert stats["max_ms"] == 100.5
        assert stats["avg_ms"] == 100.5

    def test_timing_multiple_operations(self):
        """Test recording timing for multiple operations."""
        collector = MetricsCollector()
        collector.timing("test_operation", 100.0)
        collector.timing("test_operation", 200.0)
        collector.timing("test_operation", 150.0)

        stats = collector.get_timing_stats("test_operation")

        assert stats is not None
        assert stats["count"] == 3
        assert stats["min_ms"] == 100.0
        assert stats["max_ms"] == 200.0
        assert stats["avg_ms"] == 150.0

    def test_timer_context_manager(self):
        """Test timer context manager."""
        collector = MetricsCollector()
        with collector.timer("test_timer"):
            pass

        stats = collector.get_timing_stats("test_timer")
        assert stats is not None
        assert stats["count"] == 1

    def test_get_timing_stats_nonexistent(self):
        """Test getting stats for nonexistent operation."""
        collector = MetricsCollector()
        assert collector.get_timing_stats("nonexistent") is None

    def test_get_all_stats(self):
        """Test getting all stats at once."""
        collector = MetricsCollector()
        collector.increment("counter1")
        collector.increment("counter2", 3)
        collector.timing("operation1", 100.0)

        all_stats = collector.get_all_stats()

        assert "counters" in all_stats
        assert "timings" in all_stats
        assert all_stats["counters"]["counter1"] == 1
        assert all_stats["counters"]["counter2"] == 3
        assert "operation1" in all_stats["timings"]

    def test_reset(self):
        """Test resetting all metrics."""
        collector = MetricsCollector()
        collector.increment("test_counter", 10)
        collector.timing("test_operation", 100.0)

        collector.reset()

        assert collector.get_counter("test_counter") == 0
        assert collector.get_timing_stats("test_operation") is None


class TestTimedOperationDecorator:
    """Tests for timed_operation decorator."""

    def test_decorator_times_function(self):
        """Test that decorator times function execution."""

        @timed_operation("test_func")
        def sample_function():
            import time

            time.sleep(0.01)
            return 42

        result = sample_function()
        assert result == 42

        metrics = get_metrics()
        stats = metrics.get_timing_stats("test_func")
        assert stats is not None
        assert stats["count"] == 1


class TestPerformanceMonitor:
    """Tests for PerformanceMonitor class."""

    def test_record_state_transition(self):
        """Test recording state transition timing."""
        monitor = PerformanceMonitor()
        monitor.record_state_transition(50.0)
        monitor._metrics.increment("total_transitions")

        stats = monitor.get_transition_stats()
        assert stats is not None
        assert stats["count"] == 1
        assert monitor._metrics.get_counter("total_transitions") == 2

    def test_record_database_query(self):
        """Test recording database query timing."""
        monitor = PerformanceMonitor()
        monitor.record_database_query("get_state", 25.0)

        query_stats = monitor.get_query_stats()
        assert "get_state" in query_stats

    def test_record_git_operation(self):
        """Test recording git operation timing."""
        monitor = PerformanceMonitor()
        monitor.record_git_operation("clone", 500.0)

        metrics = monitor._metrics
        stats = metrics.get_timing_stats("git_clone")
        assert stats is not None

    def test_check_performance_thresholds_pass(self):
        """Test performance check passes when within thresholds."""
        monitor = PerformanceMonitor()
        monitor.record_state_transition(10.0)

        warnings = monitor.check_performance_thresholds()
        assert len(warnings) == 0

    def test_check_performance_thresholds_warn(self):
        """Test performance check warns when exceeding thresholds."""
        monitor = PerformanceMonitor()
        monitor.record_state_transition(150.0)

        warnings = monitor.check_performance_thresholds()
        assert len(warnings) == 1
        assert "p95" in warnings[0].lower() or "latency" in warnings[0].lower()
