"""Pytest configuration for SQLite integration tests."""

import pytest
import gc


@pytest.fixture(autouse=True)
def cleanup_sqlite_connections():
    """Ensure all SQLite connections are closed after each test."""
    yield
    gc.collect()
