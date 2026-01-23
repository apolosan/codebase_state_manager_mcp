"""Unit tests for logging module."""

import json
import logging
from io import StringIO

import pytest

from src.mcp_server.utils.logging import (
    ContextFilter,
    JSONFormatter,
    clear_context,
    get_logger,
    set_session_context,
    set_state_context,
    setup_logging,
)


class TestJSONFormatter:
    """Tests for JSONFormatter class."""

    def test_format_basic_message(self):
        """Test formatting a basic log message."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["message"] == "Test message"
        assert data["level"] == "INFO"
        assert data["name"] == "test"
        assert "timestamp" in data

    def test_format_with_extra_data(self):
        """Test formatting with extra contextual data."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra_data = {"state_number": 5, "session_id": "abc123"}
        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["state_number"] == 5
        assert data["session_id"] == "abc123"

    def test_format_with_exception(self):
        """Test formatting with exception info."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=(ValueError, ValueError("test error"), None),
        )
        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert "exception" in data
        assert "ValueError" in data["exception"]


class TestContextFilter:
    """Tests for ContextFilter class."""

    def test_no_context(self):
        """Test filter with no context set."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        filter_obj = ContextFilter()
        assert filter_obj.filter(record)

    def test_with_session_context(self):
        """Test filter with session context."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        filter_obj = ContextFilter()
        set_session_context("session-123")
        filter_obj.session_id = "session-123"

        result = filter_obj.filter(record)
        assert result
        assert getattr(record, "session_id", None) == "session-123"

    def test_with_state_context(self):
        """Test filter with state context."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        filter_obj = ContextFilter()
        filter_obj.state_number = 5

        result = filter_obj.filter(record)
        assert result
        assert getattr(record, "state_number", None) == 5


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_with_json_format(self):
        """Test setup with JSON format."""
        logger = setup_logging(log_level="DEBUG", json_format=True)
        assert logger.level == logging.DEBUG

    def test_setup_without_json_format(self):
        """Test setup with standard format."""
        logger = setup_logging(log_level="INFO", json_format=False)
        assert logger.level == logging.INFO


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a Logger instance."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_same_name(self):
        """Test that same logger is returned for same name."""
        logger1 = get_logger("same_name")
        logger2 = get_logger("same_name")
        assert logger1 is logger2


class TestContextManagement:
    """Tests for context management functions."""

    def test_set_and_clear_session_context(self):
        """Test setting and clearing session context."""
        set_session_context("test-session")
        clear_context()

    def test_set_and_clear_state_context(self):
        """Test setting and clearing state context."""
        set_state_context(10)
        clear_context()
