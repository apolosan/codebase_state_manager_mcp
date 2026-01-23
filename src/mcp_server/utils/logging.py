"""Structured logging module for Codebase State Manager.

Provides JSON-formatted logging with contextual information for
better observability and debugging.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        extra = getattr(record, "extra_data", None)
        if extra and isinstance(extra, dict):
            log_data.update(extra)

        return json.dumps(log_data)


class ContextFilter(logging.Filter):
    """Filter that adds contextual information to log records."""

    def __init__(self) -> None:
        super().__init__()
        self.session_id: str | None = None
        self.state_number: int | None = None

    def filter(self, record: logging.LogRecord) -> bool:
        if self.session_id:
            record.session_id = self.session_id
        if self.state_number is not None:
            record.state_number = self.state_number
        return True


_context_filter = ContextFilter()


def setup_logging(
    log_level: str = "INFO",
    log_file: Path | None = None,
    json_format: bool = True,
) -> logging.Logger:
    """Set up structured logging for the application.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        json_format: Whether to use JSON formatting (default: True)

    Returns:
        Configured root logger
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.filters.clear()
    root_logger.addFilter(_context_filter)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)

    if json_format:
        handler_formatter: logging.Formatter = JSONFormatter()
    else:
        handler_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler.setFormatter(handler_formatter)
    root_logger.addHandler(handler)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(handler_formatter)
        root_logger.addHandler(file_handler)

    logging.getLogger("neo4j").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("git").setLevel(logging.WARNING)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def set_session_context(session_id: str) -> None:
    """Set the current session context for logging.

    Args:
        session_id: Unique session identifier
    """
    _context_filter.session_id = session_id


def set_state_context(state_number: int) -> None:
    """Set the current state context for logging.

    Args:
        state_number: Current state number
    """
    _context_filter.state_number = state_number


def clear_context() -> None:
    """Clear logging context."""
    _context_filter.session_id = None
    _context_filter.state_number = None
