from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcp_server.utils.hash import generate_state_hash, validate_state_hash


class TestHashUtils:
    def test_generate_state_hash(self):
        state_hash = generate_state_hash(
            user_prompt="Test prompt",
            branch_name="main",
            git_diff_info="diff content",
            state_number=0,
        )
        assert len(state_hash) == 64
        assert state_hash.isalnum()

    def test_generate_state_hash_different_inputs(self):
        hash1 = generate_state_hash("prompt1", "main", "", 0)
        hash2 = generate_state_hash("prompt2", "main", "", 0)
        assert hash1 != hash2

    def test_validate_state_hash_valid(self):
        state_hash = generate_state_hash("prompt", "main", "diff", 1)
        is_valid = validate_state_hash(state_hash, "prompt", "main", "diff", 1)
        assert is_valid is True

    def test_validate_state_hash_invalid(self):
        state_hash = generate_state_hash("prompt", "main", "diff", 1)
        is_valid = validate_state_hash("wrong_hash", "prompt", "main", "diff", 1)
        assert is_valid is False
