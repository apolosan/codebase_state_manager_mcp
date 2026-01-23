import tempfile
from pathlib import Path

import pytest

from src.mcp_server.utils.validation import (
    ValidationError,
    sanitize_branch_name,
    sanitize_for_json,
    sanitize_prompt,
    validate_diff_info,
    validate_path,
    validate_rate_limit_params,
    validate_search_text,
    validate_state_number,
    validate_state_range,
    validate_transition_id,
    validate_volume_path,
)


class TestSanitizePrompt:
    def test_valid_prompt(self):
        prompt = "Implement user authentication feature"
        result = sanitize_prompt(prompt)
        assert result == prompt

    def test_control_chars_removed(self):
        prompt = "Test\x00prompt\x08with\x07control\x01chars"
        result = sanitize_prompt(prompt)
        assert "\x00" not in result
        assert "\x08" not in result

    def test_injection_chars_rejected(self):
        prompt = "Test; rm -rf /"
        with pytest.raises(ValidationError):
            sanitize_prompt(prompt)

    def test_pipe_char_rejected(self):
        prompt = "Test | cat /etc/passwd"
        with pytest.raises(ValidationError):
            sanitize_prompt(prompt)

    def test_backtick_rejected(self):
        prompt = "Test `whoami` command"
        with pytest.raises(ValidationError):
            sanitize_prompt(prompt)

    def test_max_length_truncation(self):
        long_prompt = "a" * 20000
        result = sanitize_prompt(long_prompt, max_length=10000)
        assert len(result) == 10000

    def test_empty_prompt_rejected(self):
        with pytest.raises(ValidationError):
            sanitize_prompt("")

    def test_whitespace_trimmed(self):
        prompt = "   test prompt   "
        result = sanitize_prompt(prompt)
        assert result == "test prompt"


class TestValidatePath:
    def test_valid_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            subdir = base / "subdir"
            subdir.mkdir()

            result = validate_path("subdir", base)
            assert result == subdir.resolve()

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            with pytest.raises(ValidationError):
                validate_path("../etc/passwd", base)

    def test_dot_dot_slash_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            with pytest.raises(ValidationError):
                validate_path("subdir/../../etc/passwd", base)

    def test_path_outside_base_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            other_dir = Path(tmpdir).parent / "other"

            with pytest.raises(ValidationError):
                validate_path(str(other_dir), base)

    def test_empty_path_rejected(self):
        with pytest.raises(ValidationError):
            validate_path("", Path("/tmp"))

    def test_max_length_exceeded(self):
        long_path = "/" + "a" * 5000
        with pytest.raises(ValidationError):
            validate_path(long_path, Path("/tmp"))


class TestValidateStateNumber:
    def test_valid_state(self):
        result = validate_state_number(5, 100)
        assert result == 5

    def test_zero_state(self):
        result = validate_state_number(0, 100)
        assert result == 0

    def test_negative_state_rejected(self):
        with pytest.raises(ValidationError):
            validate_state_number(-1, 100)

    def test_state_at_max_boundary(self):
        result = validate_state_number(99, 100)
        assert result == 99

    def test_state_exceeds_max_rejected(self):
        with pytest.raises(ValidationError):
            validate_state_number(100, 100)


class TestValidateStateRange:
    def test_valid_range(self):
        from_state, to_state = validate_state_range(0, 5, 100)
        assert from_state == 0
        assert to_state == 5

    def test_same_state_rejected(self):
        with pytest.raises(ValidationError):
            validate_state_range(5, 5, 100)

    def test_negative_states_rejected(self):
        with pytest.raises(ValidationError):
            validate_state_range(-1, 5, 100)

    def test_states_exceed_max_rejected(self):
        with pytest.raises(ValidationError):
            validate_state_range(50, 150, 100)


class TestSanitizeBranchName:
    def test_valid_branch_name(self):
        result = sanitize_branch_name("feature/new-auth")
        assert result == "feature/new-auth"

    def test_special_chars_replaced(self):
        result = sanitize_branch_name("feature/test@#$%")
        assert "feature/test" in result
        assert "@" not in result
        assert "#" not in result
        assert "$" not in result
        assert "%" not in result

    def test_leading_underscores_removed(self):
        result = sanitize_branch_name("___test")
        assert result == "test"

    def test_empty_after_sanitization_rejected(self):
        with pytest.raises(ValidationError):
            sanitize_branch_name("!@#$%")

    def test_too_long_rejected(self):
        long_name = "a" * 300
        with pytest.raises(ValidationError):
            sanitize_branch_name(long_name)


class TestValidateDiffInfo:
    def test_valid_diff(self):
        diff = "diff --git a/file.py b/file.py\n+new line"
        result = validate_diff_info(diff)
        assert result == diff

    def test_large_diff_truncated(self):
        large_diff = "a" * 150000
        result = validate_diff_info(large_diff, max_size=100000)
        assert len(result) < len(large_diff)
        assert result.endswith("[truncated]")


class TestValidateTransitionId:
    """Tests for validate_transition_id function."""

    def test_valid_uuid(self):
        """Test valid UUID v4 format."""
        result = validate_transition_id("550e8400-e29b-41d4-a716-446655440000")
        assert result == "550e8400-e29b-41d4-a716-446655440000"

    def test_valid_uuid_lowercase(self):
        """Test valid UUID v4 format (lowercase)."""
        result = validate_transition_id("550e8400-e29b-41d4-a716-446655440000")
        assert result == "550e8400-e29b-41d4-a716-446655440000"

    def test_invalid_uuid_too_short(self):
        """Test invalid UUID - too short."""
        with pytest.raises(ValidationError):
            validate_transition_id("550e8400-e29b-41d4-a716")

    def test_invalid_uuid_format(self):
        """Test invalid UUID - wrong format."""
        with pytest.raises(ValidationError):
            validate_transition_id("not-a-uuid")

    def test_invalid_type(self):
        """Test invalid type - not a string."""
        with pytest.raises(ValidationError):
            validate_transition_id(str(12345))


class TestValidateRateLimitParams:
    """Tests for validate_rate_limit_params function."""

    def test_valid_params(self):
        """Test valid parameters."""
        client_id, endpoint = validate_rate_limit_params("test_client", "genesis")
        assert client_id == "test_client"
        assert endpoint == "genesis"

    def test_whitespace_trimmed(self):
        """Test that whitespace is trimmed."""
        client_id, endpoint = validate_rate_limit_params("  test_client  ", "  genesis  ")
        assert client_id == "test_client"
        assert endpoint == "genesis"

    def test_empty_client_id_rejected(self):
        """Test empty client ID is rejected."""
        with pytest.raises(ValidationError):
            validate_rate_limit_params("", "genesis")

    def test_empty_endpoint_rejected(self):
        """Test empty endpoint is rejected."""
        with pytest.raises(ValidationError):
            validate_rate_limit_params("test_client", "")

    def test_client_id_too_long(self):
        """Test client ID too long is rejected."""
        with pytest.raises(ValidationError):
            validate_rate_limit_params("a" * 300, "genesis")

    def test_endpoint_too_long(self):
        """Test endpoint too long is rejected."""
        with pytest.raises(ValidationError):
            validate_rate_limit_params("test_client", "a" * 200)

    def test_invalid_client_id_type(self):
        """Test invalid client ID type."""
        with pytest.raises((ValidationError, TypeError)):
            validate_rate_limit_params(123, "genesis")

    def test_invalid_endpoint_type(self):
        """Test invalid endpoint type."""
        with pytest.raises((ValidationError, TypeError)):
            validate_rate_limit_params("test_client", None)


class TestValidateSearchText:
    """Tests for validate_search_text function."""

    def test_valid_search_text(self):
        """Test valid search text."""
        result = validate_search_text("authentication feature")
        assert result == "authentication feature"

    def test_empty_search_text_rejected(self):
        """Test empty search text is rejected."""
        with pytest.raises(ValidationError):
            validate_search_text("")

    def test_whitespace_only_rejected(self):
        """Test whitespace-only text is rejected."""
        with pytest.raises(ValidationError):
            validate_search_text("   ")

    def test_max_length_exceeded(self):
        """Test max length is enforced."""
        with pytest.raises(ValidationError):
            validate_search_text("a" * 1500, max_length=1000)

    def test_control_chars_rejected(self):
        """Test control characters are rejected."""
        with pytest.raises(ValidationError):
            validate_search_text("test\x00value")

    def test_valid_long_text(self):
        """Test valid long text within limit."""
        result = validate_search_text("a" * 500, max_length=1000)
        assert len(result) == 500


class TestSanitizeForJson:
    """Tests for sanitize_for_json function."""

    def test_valid_string(self):
        """Test valid string passes through."""
        result = sanitize_for_json("test string")
        assert result == "test string"

    def test_control_chars_removed(self):
        """Test control characters are removed."""
        result = sanitize_for_json("test\x00string\x07value")
        assert "\x00" not in result
        assert "\x07" not in result

    def test_max_length_enforced(self):
        """Test max length is enforced."""
        result = sanitize_for_json("a" * 15000, max_length=10000)
        assert len(result) == 10000

    def test_invalid_type(self):
        """Test invalid type raises error."""
        with pytest.raises((ValidationError, TypeError)):
            sanitize_for_json(12345)


class TestValidateVolumePath:
    """Tests for validate_volume_path function."""

    def test_valid_relative_path(self):
        """Test valid relative path."""
        result = validate_volume_path("./data/volume")
        assert result.is_absolute()

    def test_valid_absolute_path(self):
        """Test valid absolute path."""
        result = validate_volume_path("/tmp/test_volume")
        assert str(result) == "/tmp/test_volume"

    def test_empty_path_rejected(self):
        """Test empty path is rejected."""
        with pytest.raises(ValidationError):
            validate_volume_path("")

    def test_path_traversal_rejected(self):
        """Test path traversal is rejected."""
        with pytest.raises(ValidationError):
            validate_volume_path("../etc/passwd")

    def test_path_too_long_rejected(self):
        """Test path too long is rejected."""
        with pytest.raises(ValidationError):
            validate_volume_path("/" + "a" * 5000)

    def test_invalid_type(self):
        """Test invalid type raises error."""
        with pytest.raises((ValidationError, TypeError)):
            validate_volume_path(None)
