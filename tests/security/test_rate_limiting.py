"""Tests for rate limiting module."""

import time

import pytest

from src.mcp_server.utils.security import (
    RateLimitConfig,
    RateLimiter,
    RateLimitExceeded,
    get_rate_limiter,
    reset_rate_limiter,
    set_rate_limiter,
)


class TestRateLimiter:
    """Tests for RateLimiter class."""

    @pytest.fixture
    def rate_limiter(self):
        """Create a fresh rate limiter for each test."""
        reset_rate_limiter()
        limiter = RateLimiter()
        set_rate_limiter(limiter)
        yield limiter
        reset_rate_limiter()

    def test_basic_rate_limiting(self, rate_limiter):
        """Test basic rate limiting functionality."""
        client_id = "test_client"
        endpoint = "test_endpoint"

        rate_limiter.set_config(endpoint, RateLimitConfig(requests=2, seconds=60))

        is_allowed, retry_after = rate_limiter.is_allowed(client_id, endpoint)
        assert is_allowed is True
        assert retry_after == 0

        is_allowed, retry_after = rate_limiter.is_allowed(client_id, endpoint)
        assert is_allowed is True
        assert retry_after == 0

        is_allowed, retry_after = rate_limiter.is_allowed(client_id, endpoint)
        assert is_allowed is False
        assert retry_after > 0

    def test_rate_limit_exceeded_exception(self, rate_limiter):
        """Test that RateLimitExceeded is raised when limit is exceeded."""
        client_id = "test_client"
        endpoint = "test_endpoint"

        rate_limiter.set_config(endpoint, RateLimitConfig(requests=1, seconds=60))

        rate_limiter.check_rate_limit(client_id, endpoint)

        with pytest.raises(RateLimitExceeded) as exc_info:
            rate_limiter.check_rate_limit(client_id, endpoint)

        assert exc_info.value.retry_after > 0
        assert exc_info.value.limit == 1
        assert exc_info.value.window == 60

    def test_window_reset(self, rate_limiter):
        """Test that rate limit window resets after time period."""
        client_id = "test_client"
        endpoint = "test_endpoint"

        rate_limiter.set_config(endpoint, RateLimitConfig(requests=1, seconds=1))

        rate_limiter.check_rate_limit(client_id, endpoint)

        with pytest.raises(RateLimitExceeded):
            rate_limiter.check_rate_limit(client_id, endpoint)

        time.sleep(1.1)

        rate_limiter.check_rate_limit(client_id, endpoint)

    def test_get_remaining(self, rate_limiter):
        """Test getting remaining requests."""
        client_id = "test_client"
        endpoint = "test_endpoint"

        rate_limiter.set_config(endpoint, RateLimitConfig(requests=3, seconds=60))

        remaining = rate_limiter.get_remaining(client_id, endpoint)
        assert remaining == 3

        rate_limiter.is_allowed(client_id, endpoint)

        remaining = rate_limiter.get_remaining(client_id, endpoint)
        assert remaining == 2

    def test_reset_client(self, rate_limiter):
        """Test resetting client-specific limits."""
        client_id = "test_client"
        endpoint = "test_endpoint"

        rate_limiter.set_config(endpoint, RateLimitConfig(requests=1, seconds=60))

        rate_limiter.check_rate_limit(client_id, endpoint)

        rate_limiter.reset(client_id=client_id)

        rate_limiter.check_rate_limit(client_id, endpoint)

    def test_reset_all(self, rate_limiter):
        """Test resetting all rate limits."""
        rate_limiter.set_config("endpoint1", RateLimitConfig(requests=1, seconds=60))
        rate_limiter.set_config("endpoint2", RateLimitConfig(requests=1, seconds=60))

        rate_limiter.check_rate_limit("client1", "endpoint1")
        rate_limiter.check_rate_limit("client2", "endpoint2")

        rate_limiter.reset()

        rate_limiter.check_rate_limit("client1", "endpoint1")
        rate_limiter.check_rate_limit("client2", "endpoint2")

    def test_different_clients_independent(self, rate_limiter):
        """Test that different clients have independent limits."""
        client1 = "client_1"
        client2 = "client_2"
        endpoint = "test_endpoint"

        rate_limiter.set_config(endpoint, RateLimitConfig(requests=1, seconds=60))

        rate_limiter.check_rate_limit(client1, endpoint)

        with pytest.raises(RateLimitExceeded):
            rate_limiter.check_rate_limit(client1, endpoint)

        rate_limiter.check_rate_limit(client2, endpoint)

    def test_different_endpoints_independent(self, rate_limiter):
        """Test that different endpoints have independent limits."""
        client = "test_client"
        endpoint1 = "endpoint_1"
        endpoint2 = "endpoint_2"

        rate_limiter.set_config(endpoint1, RateLimitConfig(requests=1, seconds=60))
        rate_limiter.set_config(endpoint2, RateLimitConfig(requests=1, seconds=60))

        rate_limiter.check_rate_limit(client, endpoint1)

        with pytest.raises(RateLimitExceeded):
            rate_limiter.check_rate_limit(client, endpoint1)

        rate_limiter.check_rate_limit(client, endpoint2)

    def test_default_config(self):
        """Test default rate limit configuration."""
        rate_limiter = RateLimiter()

        config = rate_limiter.get_config("unknown_endpoint")
        assert config.requests == 100
        assert config.seconds == 60

    def test_enable_disable(self):
        """Test enabling and disabling rate limiter."""
        rate_limiter = RateLimiter()
        set_rate_limiter(rate_limiter)

        rate_limiter.set_config("test", RateLimitConfig(requests=1, seconds=60))

        rate_limiter.disable()
        assert rate_limiter.is_allowed("client", "test") == (True, 0)
        assert rate_limiter.is_allowed("client", "test") == (True, 0)
        assert rate_limiter.get_remaining("client", "test") == 1

        rate_limiter.enable()
        remaining_before = rate_limiter.get_remaining("client", "test")
        assert remaining_before == 1

        rate_limiter.check_rate_limit("client", "test")
        remaining_after = rate_limiter.get_remaining("client", "test")
        assert remaining_after == 0

        with pytest.raises(RateLimitExceeded):
            rate_limiter.check_rate_limit("client", "test")

        reset_rate_limiter()


class TestRateLimitDecorator:
    """Tests for rate_limit decorator."""

    @pytest.fixture
    def rate_limiter(self):
        """Create a fresh rate limiter for each test."""
        reset_rate_limiter()
        limiter = RateLimiter()
        set_rate_limiter(limiter)
        yield limiter
        reset_rate_limiter()

    def test_decorator_raises_on_limit_exceeded(self, rate_limiter):
        """Test that decorator raises RateLimitExceeded when limit is exceeded."""
        from src.mcp_server.utils.security import rate_limit

        rate_limiter.set_config("test_endpoint", RateLimitConfig(requests=1, seconds=60))

        @rate_limit("test_endpoint", "client_id")
        def test_function(client_id: str) -> str:
            return "success"

        test_function(client_id="client1")

        with pytest.raises(RateLimitExceeded):
            test_function(client_id="client1")

    def test_decorator_allows_different_clients(self, rate_limiter):
        """Test that decorator allows different clients independently."""
        from src.mcp_server.utils.security import rate_limit

        rate_limiter.set_config("test_endpoint", RateLimitConfig(requests=1, seconds=60))

        @rate_limit("test_endpoint", "client_id")
        def test_function(client_id: str) -> str:
            return "success"

        result1 = test_function(client_id="client1")
        result2 = test_function(client_id="client2")

        assert result1 == "success"
        assert result2 == "success"


class TestGetRateLimiter:
    """Tests for get_rate_limiter function."""

    def test_singleton_pattern(self):
        """Test that get_rate_limiter returns singleton."""
        reset_rate_limiter()

        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2

        reset_rate_limiter()

    def test_set_rate_limiter(self):
        """Test setting a custom rate limiter."""
        reset_rate_limiter()

        custom_limiter = RateLimiter()
        set_rate_limiter(custom_limiter)

        retrieved = get_rate_limiter()

        assert retrieved is custom_limiter

        reset_rate_limiter()
