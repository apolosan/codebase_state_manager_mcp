"""Unit tests for MCP tools module."""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from src.mcp_server.models.state_model import State, Transition
from src.mcp_server.tools.mcp_tools import (
    _handle_rate_limit,
    arbitrary_state_transition,
    genesis,
    get_current_state_info,
    get_current_state_number,
    get_state_info,
    get_state_transitions,
    get_transition_info,
    new_state_transition,
    search_states,
    total_states,
    track_transitions,
)
from src.mcp_server.utils.security import RateLimitExceeded


class TestHandleRateLimit:
    """Tests for _handle_rate_limit function."""

    def test_rate_limit_passed(self):
        """Test when rate limit is not exceeded."""
        with patch("src.mcp_server.tools.mcp_tools.get_rate_limiter") as mock_get_rl:
            mock_rate_limiter = Mock()
            mock_rate_limiter.check_rate_limit.return_value = None
            mock_get_rl.return_value = mock_rate_limiter

            result = _handle_rate_limit("client1", "test_endpoint")
            assert result == {}
            mock_rate_limiter.check_rate_limit.assert_called_once_with("client1", "test_endpoint")

    def test_rate_limit_exceeded(self):
        """Test when rate limit is exceeded."""
        with patch("src.mcp_server.tools.mcp_tools.get_rate_limiter") as mock_get_rl:
            mock_rate_limiter = Mock()
            mock_rate_limiter.check_rate_limit.side_effect = RateLimitExceeded(
                retry_after=60, limit=10, window=60
            )
            mock_get_rl.return_value = mock_rate_limiter

            with patch("src.mcp_server.tools.mcp_tools.get_audit_logger") as mock_get_al:
                mock_audit_logger = Mock()
                mock_get_al.return_value = mock_audit_logger

                result = _handle_rate_limit("client1", "test_endpoint")
                assert result["success"] is False
                assert result["error"] == "rate_limit_exceeded"
                assert result["retry_after"] == 60
                mock_audit_logger.log_rate_limit_exceeded.assert_called_once()


class TestGenesis:
    """Tests for genesis function."""

    def test_genesis_success(self):
        """Test successful genesis operation."""
        mock_state_service = Mock()
        mock_state_service.genesis.return_value = (True, Mock(state_number=0), "Success")

        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            with patch("src.mcp_server.tools.mcp_tools.get_audit_logger") as mock_get_al:
                with patch("src.mcp_server.tools.mcp_tools.get_logger"):
                    mock_rl.return_value = {}
                    mock_audit_logger = Mock()
                    mock_get_al.return_value = mock_audit_logger

                    result = genesis(
                        state_service=mock_state_service,
                        project_path="/tmp/project",
                        volume_path="/tmp/volume",
                        client_id="client1",
                    )

                    assert result["success"] is True
                    assert result["message"] == "Success"
                    mock_audit_logger.log_genesis.assert_called_once()

    def test_genesis_rate_limited(self):
        """Test genesis when rate limited."""
        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            mock_rl.return_value = {"success": False, "error": "rate_limit"}

            mock_state_service = Mock()

            result = genesis(
                state_service=mock_state_service,
                project_path="/tmp/project",
                volume_path="/tmp/volume",
                client_id="client1",
            )

            assert result["success"] is False
            mock_state_service.genesis.assert_not_called()


class TestNewStateTransition:
    """Tests for new_state_transition function."""

    def test_new_state_transition_success(self):
        """Test successful state transition."""
        mock_state = Mock()
        mock_state.state_number = 1
        mock_state.to_dict.return_value = {"state_number": 1}

        mock_state_service = Mock()
        mock_state_service.state_repo.get_current.return_value = Mock(state_number=0)
        mock_state_service.new_state_transition.return_value = (True, mock_state, "Success")

        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            with patch("src.mcp_server.tools.mcp_tools.get_audit_logger") as mock_get_al:
                with patch("src.mcp_server.tools.mcp_tools.get_logger"):
                    mock_rl.return_value = {}
                    mock_audit_logger = Mock()
                    mock_get_al.return_value = mock_audit_logger

                    result = new_state_transition(
                        state_service=mock_state_service,
                        user_prompt="Test prompt",
                        client_id="client1",
                    )

                    assert result["success"] is True
                    assert result["message"] == "Success"
                    mock_audit_logger.log_state_transition.assert_called_once()

    def test_new_state_transition_rate_limited(self):
        """Test state transition when rate limited."""
        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            mock_rl.return_value = {"success": False, "error": "rate_limit"}

            mock_state_service = Mock()

            result = new_state_transition(
                state_service=mock_state_service, user_prompt="Test prompt", client_id="client1"
            )

            assert result["success"] is False
            mock_state_service.new_state_transition.assert_not_called()


class TestArbitraryStateTransition:
    """Tests for arbitrary_state_transition function."""

    def test_arbitrary_transition_success(self):
        """Test successful arbitrary state transition."""
        mock_state = Mock()
        mock_state.state_number = 5
        mock_state.to_dict.return_value = {"state_number": 5}

        mock_state_service = Mock()
        mock_state_service.state_repo.get_current.return_value = Mock(state_number=0)
        mock_state_service.arbitrary_state_transition.return_value = (True, mock_state, "Success")

        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            with patch("src.mcp_server.tools.mcp_tools.get_audit_logger") as mock_get_al:
                with patch("src.mcp_server.tools.mcp_tools.get_logger"):
                    mock_rl.return_value = {}
                    mock_audit_logger = Mock()
                    mock_get_al.return_value = mock_audit_logger

                    result = arbitrary_state_transition(
                        state_service=mock_state_service, next_state=5, client_id="client1"
                    )

                    assert result["success"] is True
                    mock_audit_logger.log_arbitrary_transition.assert_called_once()

    def test_arbitrary_transition_rate_limited(self):
        """Test arbitrary transition when rate limited."""
        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            mock_rl.return_value = {"success": False, "error": "rate_limit"}

            mock_state_service = Mock()

            result = arbitrary_state_transition(
                state_service=mock_state_service, next_state=5, client_id="client1"
            )

            assert result["success"] is False
            mock_state_service.arbitrary_state_transition.assert_not_called()


class TestGetters:
    """Tests for getter functions."""

    def test_get_current_state_number(self):
        """Test get_current_state_number function."""
        mock_state_service = Mock()
        mock_state_service.get_current_state_number.return_value = (5, "Found")

        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            mock_rl.return_value = {}

            result = get_current_state_number(state_service=mock_state_service, client_id="client1")

            assert result["success"] is True
            assert result["state_number"] == 5

    def test_get_current_state_info(self):
        """Test get_current_state_info function."""
        mock_state = Mock()
        mock_state.to_dict.return_value = {"state_number": 5}

        mock_state_service = Mock()
        mock_state_service.get_current_state.return_value = (mock_state, "Found")

        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            mock_rl.return_value = {}

            result = get_current_state_info(state_service=mock_state_service, client_id="client1")

            assert result["success"] is True
            assert result["state"]["state_number"] == 5

    def test_get_state_info(self):
        """Test get_state_info function."""
        mock_state = Mock()
        mock_state.to_dict.return_value = {"state_number": 3}

        mock_state_service = Mock()
        mock_state_service.get_state_info.return_value = (mock_state, "Found")

        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            mock_rl.return_value = {}

            result = get_state_info(state_service=mock_state_service, state=3, client_id="client1")

            assert result["success"] is True
            assert result["state"]["state_number"] == 3

    def test_total_states(self):
        """Test total_states function."""
        mock_state_service = Mock()
        mock_state_service.total_states.return_value = (10, "Found")

        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            mock_rl.return_value = {}

            result = total_states(state_service=mock_state_service, client_id="client1")

            assert result["success"] is True
            assert result["total_states"] == 10

    def test_search_states(self):
        """Test search_states function."""
        mock_state_service = Mock()
        mock_state_service.search_states.return_value = ([1, 3, 5], "Found")

        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            mock_rl.return_value = {}

            result = search_states(
                state_service=mock_state_service, text="test", client_id="client1"
            )

            assert result["success"] is True
            assert result["states"] == [1, 3, 5]

    def test_get_state_transitions(self):
        """Test get_state_transitions function."""
        mock_state_service = Mock()
        mock_state_service.get_state_transitions.return_value = (
            [str(uuid4()), str(uuid4())],
            "Found",
        )

        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            mock_rl.return_value = {}

            result = get_state_transitions(
                state_service=mock_state_service, state=1, client_id="client1"
            )

            assert result["success"] is True
            assert len(result["transitions"]) == 2

    def test_get_transition_info(self):
        """Test get_transition_info function."""
        transition_id = str(uuid4())
        mock_state_service = Mock()
        mock_state_service.get_transition_info.return_value = (
            {"transition_id": transition_id},
            "Found",
        )

        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            mock_rl.return_value = {}

            result = get_transition_info(
                state_service=mock_state_service, transition_id=transition_id, client_id="client1"
            )

            assert result["success"] is True
            assert result["transition"]["transition_id"] == transition_id

    def test_track_transitions(self):
        """Test track_transitions function."""
        mock_state_service = Mock()
        mock_state_service.track_transitions.return_value = (
            [str(uuid4()), str(uuid4()), str(uuid4())],
            "Found",
        )

        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            mock_rl.return_value = {}

            result = track_transitions(state_service=mock_state_service, client_id="client1")

            assert result["success"] is True
            assert len(result["transitions"]) == 3

    def test_getters_rate_limited(self):
        """Test that getters return rate limit error when limited."""
        rate_limit_error = {"success": False, "error": "rate_limit"}

        getters_with_args = [
            (get_current_state_number, {}),
            (get_current_state_info, {}),
            (get_state_info, {"state": 1}),
            (total_states, {}),
            (search_states, {"text": "test"}),
            (get_state_transitions, {"state": 1}),
            (get_transition_info, {"transition_id": str(uuid4())}),
            (track_transitions, {}),
        ]

        for func, args in getters_with_args:
            with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
                mock_rl.return_value = rate_limit_error

                result = func(state_service=Mock(), client_id="client1", **args)
                assert result["success"] is False
