"""Unit tests for StateService edge cases and error handling."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from src.mcp_server.models.state_model import State, Transition
from src.mcp_server.services.git_manager import GitOperationError
from src.mcp_server.services.state_service import (
    InvalidStateTransitionError,
    StateNotFoundError,
    StateService,
    StateServiceError,
)
from src.mcp_server.utils.validation import ValidationError


class TestStateServiceGenesisEdgeCases:
    """Tests for genesis edge cases and error handling."""

    def test_genesis_already_initialized(self):
        """Test genesis when already initialized."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            mock_is_init.return_value = True

            success, state, message = service.genesis("/tmp/project", "/tmp/volume")

            assert success is False
            assert state is None
            assert "already initialized" in message

    def test_genesis_git_operation_error(self):
        """Test genesis when git operation fails."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        mock_git_manager.is_git_repo.return_value = True
        mock_git_manager.clone_to_volume.return_value = False

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            mock_is_init.return_value = False

            success, state, message = service.genesis("/tmp/project", "/tmp/volume")

            assert success is False
            assert state is None
            assert "Failed to clone" in message

    def test_genesis_filesystem_error(self):
        """Test genesis when filesystem operation fails."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        mock_git_manager.is_git_repo.return_value = True
        mock_git_manager.clone_to_volume.return_value = True
        mock_git_manager.get_current_branch.return_value = "main"
        mock_git_manager.get_diff.return_value = "diff"
        mock_git_manager.get_directory_hashes.return_value = {"test.py": "hash123"}
        mock_state_repo.create.return_value = True

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            with patch("src.mcp_server.services.state_service.set_initialized") as mock_set_init:
                mock_is_init.return_value = False
                mock_set_init.return_value = False

                success, state, message = service.genesis("/tmp/project", "/tmp/volume")

                assert success is False
                assert "Failed to set initialized" in message

    def test_genesis_non_git_repo_filesystem_error(self):
        """Test genesis for non-git repo when filesystem operation fails."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        mock_git_manager.is_git_repo.return_value = False
        mock_git_manager.clone_to_volume.return_value = False

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            mock_is_init.return_value = False

            success, state, message = service.genesis("/tmp/project", "/tmp/volume")

            assert success is False
            assert "Failed to clone" in message

    def test_genesis_non_git_init_repo_error(self):
        """Test genesis for non-git repo when git init fails."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        mock_git_manager.is_git_repo.return_value = False
        mock_git_manager.clone_to_volume.return_value = True
        mock_git_manager.init_repo.return_value = False

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            mock_is_init.return_value = False

            success, state, message = service.genesis("/tmp/project", "/tmp/volume")

            assert success is False
            assert "Failed to initialize git repository" in message


class TestStateServiceTransitionEdgeCases:
    """Tests for state transition edge cases."""

    def test_new_state_transition_not_initialized(self):
        """Test new_state_transition when not initialized."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            mock_is_init.return_value = False

            success, state, message = service.new_state_transition("Test prompt")

            assert success is False
            assert state is None
            assert "not initialized" in message

    def test_new_state_transition_no_current_state(self):
        """Test new_state_transition when no current state exists."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        mock_state_repo.get_current.return_value = None

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            mock_is_init.return_value = True

            success, state, message = service.new_state_transition("Test prompt")

            assert success is False
            assert state is None
            assert "No current state found" in message

    def test_new_state_transition_create_fails(self):
        """Test new_state_transition when state creation fails."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_transition_repo.count.return_value = 0
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        mock_current_state = Mock()
        mock_current_state.state_number = 0
        mock_current_state.branch_name = "main"
        mock_current_state.git_diff_info = ""
        mock_current_state.file_hashes = {}
        mock_current_state.file_hash_deltas = {}

        mock_genesis_state = Mock()
        mock_genesis_state.file_hashes = {"genesis.py": "genesis_hash"}
        mock_genesis_state.file_hash_deltas = {"genesis.py": "genesis_hash"}

        mock_state_repo.get_current.return_value = mock_current_state
        mock_state_repo.get_by_number.return_value = mock_genesis_state
        mock_state_repo.count.return_value = 1
        mock_state_repo.create.side_effect = [True, True]

        mock_transition_repo.create.return_value = False

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            with patch("src.mcp_server.services.state_service.sanitize_prompt") as mock_sanitize:
                mock_is_init.return_value = True
                mock_sanitize.return_value = "Test prompt"
                mock_git_manager.compute_changes_since_last_state.return_value = ('{"added": [], "modified": [], "deleted": [], "content_diffs": {}}', {})

                success, state, message = service.new_state_transition("Test prompt")

                assert success is False
                assert "rolled back" in message


class TestStateServiceArbitraryTransitionEdgeCases:
    """Tests for arbitrary state transition edge cases."""

    def test_arbitrary_transition_not_initialized(self):
        """Test arbitrary_state_transition when not initialized."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            mock_is_init.return_value = False

            success, state, message = service.arbitrary_state_transition(5)

            assert success is False
            assert state is None
            assert "not initialized" in message

    def test_arbitrary_transition_invalid_state_number(self):
        """Test arbitrary_state_transition with invalid state number."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_transition_repo.count.return_value = 0
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        mock_current_state = Mock()
        mock_current_state.state_number = 0
        mock_state_repo.get_current.return_value = mock_current_state
        mock_state_repo.count.return_value = 3

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            with patch(
                "src.mcp_server.services.state_service.validate_state_number"
            ) as mock_validate:
                mock_is_init.return_value = True
                mock_validate.side_effect = ValidationError("Invalid state number")

                success, state, message = service.arbitrary_state_transition(999)

                assert success is False
                assert "Invalid state number" in message

    def test_arbitrary_transition_state_not_found(self):
        """Test arbitrary_state_transition when target state doesn't exist."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_transition_repo.count.return_value = 0
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        mock_current_state = Mock()
        mock_current_state.state_number = 0
        mock_state_repo.get_current.return_value = mock_current_state
        mock_state_repo.count.return_value = 3
        mock_state_repo.get_by_number.return_value = None

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            with patch("src.mcp_server.services.state_service.validate_state_number"):
                mock_is_init.return_value = True

                success, state, message = service.arbitrary_state_transition(5)

                assert success is False
                assert "not found" in message

    def test_arbitrary_transition_invalid_range(self):
        """Test arbitrary_state_transition with invalid state range."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_transition_repo.count.return_value = 0
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        mock_current_state = Mock()
        mock_current_state.state_number = 0
        mock_current_state.user_prompt = "Initial"

        mock_target_state = Mock()
        mock_target_state.state_number = 5
        mock_target_state.user_prompt = "Arbitrary transition"

        mock_state_repo.get_current.return_value = mock_current_state
        mock_state_repo.count.return_value = 6
        mock_state_repo.get_by_number.return_value = mock_target_state

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            with patch("src.mcp_server.services.state_service.validate_state_number"):
                with patch(
                    "src.mcp_server.services.state_service.validate_state_range"
                ) as mock_range:
                    mock_is_init.return_value = True
                    mock_range.side_effect = ValidationError("Invalid range")

                    success, state, message = service.arbitrary_state_transition(5)

                    assert success is False
                    assert "Invalid transition" in message

    def test_arbitrary_transition_create_fails(self):
        """Test arbitrary_state_transition when transition creation fails."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_transition_repo.count.return_value = 0
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        mock_current_state = Mock()
        mock_current_state.state_number = 0
        mock_current_state.user_prompt = "Initial"

        mock_target_state = Mock()
        mock_target_state.state_number = 5
        mock_target_state.user_prompt = "Arbitrary transition"

        mock_state_repo.get_current.return_value = mock_current_state
        mock_state_repo.count.return_value = 6
        mock_state_repo.get_by_number.return_value = mock_target_state
        mock_transition_repo.create.return_value = False

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            with patch("src.mcp_server.services.state_service.validate_state_number"):
                with patch("src.mcp_server.services.state_service.validate_state_range"):
                    mock_is_init.return_value = True

                    success, state, message = service.arbitrary_state_transition(5)

                    assert success is False
                    assert "Failed to create transition" in message


class TestStateServiceGetterEdgeCases:
    """Tests for getter edge cases."""

    def test_get_current_state_not_initialized(self):
        """Test get_current_state when not initialized."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            mock_is_init.return_value = False

            state, message = service.get_current_state()

            assert state is None
            assert "not initialized" in message

    def test_get_current_state_number_not_initialized(self):
        """Test get_current_state_number when not initialized."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            mock_is_init.return_value = False

            number, message = service.get_current_state_number()

            assert number is None
            assert "not initialized" in message

    def test_get_state_info_not_initialized(self):
        """Test get_state_info when not initialized."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            mock_is_init.return_value = False

            state, message = service.get_state_info(1)

            assert state is None
            assert "not initialized" in message

    def test_total_states_not_initialized(self):
        """Test total_states when not initialized."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            mock_is_init.return_value = False

            count, message = service.total_states()

            assert count == 0
            assert "not initialized" in message

    def test_search_states_not_initialized(self):
        """Test search_states when not initialized."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            mock_is_init.return_value = False

            results, message = service.search_states("test")

            assert results == []
            assert "not initialized" in message

    def test_get_state_transitions_not_initialized(self):
        """Test get_state_transitions when not initialized."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            mock_is_init.return_value = False

            transitions, message = service.get_state_transitions(1)

            assert transitions == []
            assert "not initialized" in message

    def test_get_transition_info_not_initialized(self):
        """Test get_transition_info when not initialized."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            mock_is_init.return_value = False

            transition, message = service.get_transition_info(str(uuid4()))

            assert transition is None
            assert "not initialized" in message

    def test_get_transition_info_invalid_uuid(self):
        """Test get_transition_info with invalid UUID format."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            mock_is_init.return_value = True

            transition, message = service.get_transition_info("invalid-uuid")

            assert transition is None
            assert "Invalid transition ID format" in message

    def test_track_transitions_not_initialized(self):
        """Test track_transitions when not initialized."""
        mock_state_repo = Mock()
        mock_transition_repo = Mock()
        mock_git_manager = Mock()
        mock_settings = Mock()
        mock_settings.docker_volume_name = "/tmp/volume"

        service = StateService(
            mock_state_repo, mock_transition_repo, mock_git_manager, mock_settings
        )

        with patch("src.mcp_server.services.state_service.is_initialized") as mock_is_init:
            mock_is_init.return_value = False

            transitions, message = service.track_transitions()

            assert transitions == []
            assert "not initialized" in message
