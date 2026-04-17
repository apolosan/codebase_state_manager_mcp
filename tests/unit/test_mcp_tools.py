"""Unit tests for MCP tools module."""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from src.mcp_server.models.state_model import State, Transition
from src.mcp_server.tools.mcp_tools import (
    _handle_rate_limit,
    arbitrary_state_transition,
    fix_volume_path,
    get_genesis_result,
    get_genesis_status,
    get_fix_volume_path_result,
    get_fix_volume_path_status,
    genesis,
    get_current_state_info,
    get_current_state_number,
    get_state_info,
    get_state_transitions,
    get_transition_info,
    new_state_transition,
    search_states,
    start_genesis,
    start_fix_volume_path,
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


class TestAsyncGenesis:
    def test_start_genesis_returns_job_metadata(self):
        mock_state_service = Mock()

        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            with patch("src.mcp_server.tools.mcp_tools._volume_operation_jobs") as mock_jobs:
                mock_rl.return_value = {}
                mock_jobs.start_genesis.return_value = {
                    "job_id": "job-genesis-123",
                    "status": "running",
                    "message": "Genesis started",
                    "idempotency_key": "key-genesis",
                    "already_running": False,
                }

                result = start_genesis(
                    state_service=mock_state_service,
                    project_path="/tmp/project",
                    volume_path="/tmp/volume",
                    client_id="client1",
                )

                assert result == {
                    "success": True,
                    "job": {
                        "job_id": "job-genesis-123",
                        "status": "running",
                        "message": "Genesis started",
                        "idempotency_key": "key-genesis",
                        "already_running": False,
                    },
                }
                mock_jobs.start_genesis.assert_called_once_with(
                    mock_state_service,
                    "/tmp/project",
                    "/tmp/volume",
                )

    def test_start_genesis_is_idempotent(self):
        mock_state_service = Mock()

        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            with patch("src.mcp_server.tools.mcp_tools._volume_operation_jobs") as mock_jobs:
                mock_rl.return_value = {}
                mock_jobs.start_genesis.return_value = {
                    "job_id": "job-genesis-123",
                    "status": "completed",
                    "message": "Reusing completed genesis job",
                    "idempotency_key": "key-genesis",
                    "already_running": False,
                }

                result = start_genesis(
                    state_service=mock_state_service,
                    project_path="/tmp/project",
                    volume_path="/tmp/volume",
                    client_id="client1",
                )

                assert result["success"] is True
                assert result["job"]["job_id"] == "job-genesis-123"

    def test_get_genesis_status_returns_current_job_state(self):
        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            with patch("src.mcp_server.tools.mcp_tools._volume_operation_jobs") as mock_jobs:
                mock_rl.return_value = {}
                mock_jobs.get_status.return_value = {
                    "job_id": "job-genesis-123",
                    "status": "completed",
                    "message": "Genesis completed successfully",
                    "idempotency_key": "key-genesis",
                }

                result = get_genesis_status(job_id="job-genesis-123", client_id="client1")

                assert result == {
                    "success": True,
                    "job": {
                        "job_id": "job-genesis-123",
                        "status": "completed",
                        "message": "Genesis completed successfully",
                        "idempotency_key": "key-genesis",
                    },
                }

    def test_get_genesis_result_returns_stable_completed_result(self):
        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            with patch("src.mcp_server.tools.mcp_tools._volume_operation_jobs") as mock_jobs:
                mock_rl.return_value = {}
                mock_jobs.get_result.return_value = {
                    "job_id": "job-genesis-123",
                    "status": "completed",
                    "result": {
                        "success": True,
                        "state": {"state_number": 0},
                        "message": "Genesis state created successfully",
                    },
                }

                result = get_genesis_result(job_id="job-genesis-123", client_id="client1")

                assert result == {
                    "success": True,
                    "job": {
                        "job_id": "job-genesis-123",
                        "status": "completed",
                        "result": {
                            "success": True,
                            "state": {"state_number": 0},
                            "message": "Genesis state created successfully",
                        },
                    },
                }

    def test_get_genesis_result_returns_not_found(self):
        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            with patch("src.mcp_server.tools.mcp_tools._volume_operation_jobs") as mock_jobs:
                mock_rl.return_value = {}
                mock_jobs.get_result.return_value = None

                result = get_genesis_result(job_id="missing-genesis", client_id="client1")

                assert result == {
                    "success": False,
                    "message": "Genesis job not found: missing-genesis",
                }


class TestFixVolumePath:
    """Tests for fix_volume_path function."""

    def test_fix_volume_path_success(self):
        """Test successful volume path reconstruction."""
        mock_state_service = Mock()
        mock_state_service.fix_volume_path.return_value = (
            True,
            {
                "volume_path": "/tmp/volume",
                "codebase_path": "/tmp/volume/codebase",
                "current_state": 3,
            },
            "Volume path reconstructed successfully",
        )

        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            mock_rl.return_value = {}

            result = fix_volume_path(
                state_service=mock_state_service,
                project_path="/tmp/project",
                client_id="client1",
            )

            assert result == {
                "success": True,
                "volume": {
                    "volume_path": "/tmp/volume",
                    "codebase_path": "/tmp/volume/codebase",
                    "current_state": 3,
                },
                "message": "Volume path reconstructed successfully",
            }
            mock_state_service.fix_volume_path.assert_called_once_with("/tmp/project")

    def test_fix_volume_path_rate_limited(self):
        """Test fix_volume_path when rate limited."""
        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            mock_rl.return_value = {"success": False, "error": "rate_limit"}

            mock_state_service = Mock()

            result = fix_volume_path(
                state_service=mock_state_service,
                project_path="/tmp/project",
                client_id="client1",
            )

            assert result["success"] is False
            mock_state_service.fix_volume_path.assert_not_called()


class TestAsyncFixVolumePath:
    """Tests for async/idempotent fix_volume_path flow."""

    def test_start_fix_volume_path_returns_job_metadata(self):
        mock_state_service = Mock()

        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            with patch("src.mcp_server.tools.mcp_tools._volume_operation_jobs") as mock_jobs:
                mock_rl.return_value = {}
                mock_jobs.start.return_value = {
                    "job_id": "job-123",
                    "status": "running",
                    "message": "Volume path repair started",
                    "idempotency_key": "key-1",
                    "already_running": False,
                }

                result = start_fix_volume_path(
                    state_service=mock_state_service,
                    project_path="/tmp/project",
                    client_id="client1",
                )

                assert result == {
                    "success": True,
                    "job": {
                        "job_id": "job-123",
                        "status": "running",
                        "message": "Volume path repair started",
                        "idempotency_key": "key-1",
                        "already_running": False,
                    },
                }
                mock_jobs.start.assert_called_once_with(mock_state_service, "/tmp/project")

    def test_start_fix_volume_path_is_idempotent(self):
        mock_state_service = Mock()

        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            with patch("src.mcp_server.tools.mcp_tools._volume_operation_jobs") as mock_jobs:
                mock_rl.return_value = {}
                mock_jobs.start.return_value = {
                    "job_id": "job-123",
                    "status": "running",
                    "message": "Reusing running volume path repair job",
                    "idempotency_key": "key-1",
                    "already_running": True,
                }

                result = start_fix_volume_path(
                    state_service=mock_state_service,
                    project_path="/tmp/project",
                    client_id="client1",
                )

                assert result["success"] is True
                assert result["job"]["already_running"] is True
                assert result["job"]["job_id"] == "job-123"

    def test_get_fix_volume_path_status_returns_current_job_state(self):
        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            with patch("src.mcp_server.tools.mcp_tools._volume_operation_jobs") as mock_jobs:
                mock_rl.return_value = {}
                mock_jobs.get_status.return_value = {
                    "job_id": "job-123",
                    "status": "completed",
                    "message": "Volume path reconstructed successfully",
                    "idempotency_key": "key-1",
                }

                result = get_fix_volume_path_status(job_id="job-123", client_id="client1")

                assert result == {
                    "success": True,
                    "job": {
                        "job_id": "job-123",
                        "status": "completed",
                        "message": "Volume path reconstructed successfully",
                        "idempotency_key": "key-1",
                    },
                }
                mock_jobs.get_status.assert_called_once_with("job-123")

    def test_get_fix_volume_path_result_returns_stable_completed_result(self):
        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            with patch("src.mcp_server.tools.mcp_tools._volume_operation_jobs") as mock_jobs:
                mock_rl.return_value = {}
                mock_jobs.get_result.return_value = {
                    "job_id": "job-123",
                    "status": "completed",
                    "result": {
                        "success": True,
                        "volume": {
                            "volume_path": "/tmp/volume",
                            "codebase_path": "/tmp/volume/codebase",
                            "current_state": 3,
                        },
                        "message": "Volume path reconstructed successfully",
                    },
                }

                result = get_fix_volume_path_result(job_id="job-123", client_id="client1")

                assert result == {
                    "success": True,
                    "job": {
                        "job_id": "job-123",
                        "status": "completed",
                        "result": {
                            "success": True,
                            "volume": {
                                "volume_path": "/tmp/volume",
                                "codebase_path": "/tmp/volume/codebase",
                                "current_state": 3,
                            },
                            "message": "Volume path reconstructed successfully",
                        },
                    },
                }
                mock_jobs.get_result.assert_called_once_with("job-123")

    def test_get_fix_volume_path_result_returns_not_found(self):
        with patch("src.mcp_server.tools.mcp_tools._handle_rate_limit") as mock_rl:
            with patch("src.mcp_server.tools.mcp_tools._volume_operation_jobs") as mock_jobs:
                mock_rl.return_value = {}
                mock_jobs.get_result.return_value = None

                result = get_fix_volume_path_result(job_id="missing-job", client_id="client1")

                assert result == {
                    "success": False,
                    "message": "Volume path repair job not found: missing-job",
                }


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
