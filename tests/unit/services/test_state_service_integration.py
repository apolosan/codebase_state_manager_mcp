"""Integration tests for StateService branch detection."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest


class TestStateServiceBranchIntegration:
    """Test StateService integration with branch detection."""

    @pytest.fixture
    def state_service(self, tmp_path):
        """Create StateService with mocked dependencies."""
        from src.mcp_server.services.state_service import StateService

        # Mock settings
        settings = Mock()
        settings.docker_volume_name = str(tmp_path / "volume")

        # Create service with mocked repos
        service = StateService(
            state_repo=Mock(),
            transition_repo=Mock(),
            git_manager=Mock(),
            settings=settings,
        )

        return service

    def test_create_state_uses_current_branch_not_stored(self, state_service, tmp_path):
        """Verify new state uses filesystem branch, not stored branch."""
        from src.mcp_server.models.state_model import State

        # Setup: Estado anterior com branch antiga
        old_state = State(
            state_number=1,
            user_prompt="Old state",
            branch_name="old-branch",
            hash="abc123",
            git_diff_info="",
            file_hashes={},
            file_hash_deltas={},
        )

        # Mock branch detection diretamente na instância
        state_service.branch_detector = Mock()
        state_service.branch_detector.get_current_branch_name.return_value = "new-branch"

        # Mock state_repo.create_next para evitar erro
        def mock_create_next(state):
            state.state_number = 2  # Simular atribuição de número
            return True

        state_service.state_repo.create_next = mock_create_next

        # Mock transition_repo.create_next
        state_service.transition_repo.create_next = Mock(return_value=True)

        # Executar
        success, new_state, message = state_service._create_state_and_transition_atomic(
            user_prompt="New state",
            diff_info="",
            current_state=old_state,
            file_hashes=None,
            file_hash_deltas={},
            project_path=tmp_path,
        )

        # Verificar: novo estado deve ter branch atual, não a antiga
        assert success is True
        assert new_state is not None
        assert new_state.branch_name == "new-branch"
        assert new_state.branch_name != old_state.branch_name

    def test_atomic_create_rolls_back_transition_when_set_current_fails(self, state_service, tmp_path):
        """Verify rollback removes both transition and state when current pointer update fails."""
        from src.mcp_server.models.state_model import State

        old_state = State(
            state_number=1,
            user_prompt="Old state",
            branch_name="main",
            hash="abc123",
            git_diff_info="",
            file_hashes={},
            file_hash_deltas={},
        )

        state_service.branch_detector = Mock()
        state_service.branch_detector.get_current_branch_name.return_value = "main"

        def mock_create_next(state):
            state.state_number = 2
            return True

        def mock_create_next_transition(transition):
            transition.transition_id = 1
            return True

        state_service.state_repo.create_next = mock_create_next
        state_service.state_repo.set_current = Mock(return_value=False)
        state_service.state_repo.delete = Mock(return_value=True)
        state_service.transition_repo.create_next = Mock(side_effect=mock_create_next_transition)
        state_service.transition_repo.delete = Mock(return_value=True)

        success, new_state, message = state_service._create_state_and_transition_atomic(
            user_prompt="New state",
            diff_info="",
            current_state=old_state,
            file_hashes=None,
            file_hash_deltas={},
            project_path=tmp_path,
        )

        assert success is False
        assert new_state is None
        assert "Failed to update current state pointer" in message
        state_service.transition_repo.delete.assert_called_once_with(1)
        state_service.state_repo.delete.assert_called_once_with(2)
