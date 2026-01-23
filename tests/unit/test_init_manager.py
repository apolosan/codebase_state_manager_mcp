import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcp_server.utils.init_manager import is_initialized, set_initialized


class TestInitManager:
    def test_is_initialized_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = is_initialized(tmpdir)
            assert result is False

    def test_set_initialized_true(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = set_initialized(tmpdir, True)
            assert result is True
            assert is_initialized(tmpdir) is True

    def test_set_initialized_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            set_initialized(tmpdir, True)
            result = set_initialized(tmpdir, False)
            assert result is True
            assert is_initialized(tmpdir) is False

    def test_toggle_initialized(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert is_initialized(tmpdir) is False
            set_initialized(tmpdir, True)
            assert is_initialized(tmpdir) is True
            set_initialized(tmpdir, False)
            assert is_initialized(tmpdir) is False
