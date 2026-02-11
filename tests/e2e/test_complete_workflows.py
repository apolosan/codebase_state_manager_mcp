"""
End-to-end tests for Codebase State Manager MCP Server.
Tests complete workflows including genesis, transitions, and queries.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class MockStateRepository:
    def __init__(self):
        self.states = {}
        self._initialized = False
        self._current_state = None

    def create(self, state):
        self.states[state.state_number] = state
        return True

    def get_by_number(self, state_number):
        return self.states.get(state_number)

    def get_current(self):
        if self._current_state is not None:
            return self.states.get(self._current_state)
        if not self.states:
            return None
        max_num = max(self.states.keys())
        return self.states[max_num]

    def get_all(self):
        return [self.states[k] for k in sorted(self.states.keys())]

    def exists(self, state_number):
        return state_number in self.states

    def count(self):
        return len(self.states)

    def search(self, text):
        return [
            s.state_number for s in self.states.values() if text.lower() in s.user_prompt.lower()
        ]

    def delete(self, state_number):
        if state_number in self.states:
            del self.states[state_number]
            return True
        return False

    def create_next(self, state):
        # Find next sequential number
        max_num = max(self.states.keys()) if self.states else -1
        next_num = max_num + 1
        state.state_number = next_num
        # Generate a simple hash for testing
        state.hash = f"hash{next_num}"
        self.states[next_num] = state
        return True

    def set_current(self, state_number: int) -> bool:
        if state_number not in self.states:
            return False
        self._current_state = state_number
        return True


class MockTransitionRepository:
    def __init__(self):
        self.transitions = {}

    def create(self, transition):
        self.transitions[str(transition.transition_id)] = transition
        return True

    def create_next(self, transition):
        # Find next sequential ID
        max_id = max([int(k) for k in self.transitions.keys()]) if self.transitions else 0
        next_id = max_id + 1
        transition.transition_id = next_id
        self.transitions[str(next_id)] = transition
        return True

    def get_by_id(self, transition_id):
        return self.transitions.get(str(transition_id))

    def get_by_state(self, state_number):
        return [t for t in self.transitions.values() if t.current_state == state_number]

    def get_last(self, limit):
        all_t = list(self.transitions.values())
        return all_t[-limit:] if all_t else []

    def count(self):
        return len(self.transitions)


class TestCompleteWorkflows:
    """End-to-end tests for complete MCP workflows."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory with files."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        (project_dir / "main.py").write_text("print('hello')")
        (project_dir / "utils.py").write_text("def helper(): pass")

        return project_dir

    @pytest.fixture
    def mock_state_repo(self):
        return MockStateRepository()

    @pytest.fixture
    def mock_transition_repo(self):
        return MockTransitionRepository()

    @pytest.fixture
    def git_manager(self, temp_project):
        from src.mcp_server.services.git_manager import GitManager

        manager = MagicMock()
        manager.is_git_repo.return_value = True
        manager.clone_to_volume.return_value = True
        manager.get_current_branch.return_value = "main"
        manager.get_diff.return_value = "diff content"
        manager.compute_changes_since_last_state.return_value = (
            '{"added": [], "modified": [], "deleted": [], "content_diffs": {}}',
            {},
        )
        return manager

    @pytest.fixture
    def settings(self, tmp_path):
        from src.mcp_server.config import Settings

        return Settings(
            db_mode="sqlite",
            sqlite_path=str(tmp_path / "test.db"),
            docker_volume_name=str(tmp_path),
        )

    @pytest.fixture
    def state_service(self, mock_state_repo, mock_transition_repo, git_manager, settings):
        from src.mcp_server.services.state_service import StateService

        return StateService(
            state_repo=mock_state_repo,
            transition_repo=mock_transition_repo,
            git_manager=git_manager,
            settings=settings,
        )

    def test_genesis_then_get_current_state(self, state_service, temp_project, settings, tmp_path):
        """Test complete genesis workflow and retrieval."""
        from src.mcp_server.utils.init_manager import is_initialized

        volume_path = str(tmp_path / "volume")

        success, state, message = state_service.genesis(str(temp_project), volume_path)

        assert success is True, f"Genesis failed: {message}"
        assert state is not None
        assert state.state_number == 0

        assert is_initialized(volume_path) is True

    def test_multiple_state_transitions(self, state_service, temp_project, settings, tmp_path):
        """Test creating multiple state transitions."""
        from src.mcp_server.utils.init_manager import is_initialized

        volume_path = str(tmp_path / "volume")

        state_service.genesis(str(temp_project), volume_path)

        success1, state1, msg1 = state_service.new_state_transition("First task")
        assert success1 is True, f"Transition 1 failed: {msg1}"
        assert state1.state_number == 1

        success2, state2, msg2 = state_service.new_state_transition("Second task")
        assert success2 is True, f"Transition 2 failed: {msg2}"
        assert state2.state_number == 2

        total, _ = state_service.total_states()
        assert total == 3  # States 0, 1, 2

    def test_arbitrary_state_jumps(self, state_service, temp_project, settings, tmp_path):
        """Test arbitrary state transitions (jumping between states)."""
        from src.mcp_server.utils.init_manager import is_initialized

        volume_path = str(tmp_path / "volume")

        state_service.genesis(str(temp_project), volume_path)
        state_service.new_state_transition("State 1")
        state_service.new_state_transition("State 2")

        success, state, msg = state_service.arbitrary_state_transition(0)
        assert success is True
        assert state.state_number == 0

        success, state, msg = state_service.arbitrary_state_transition(2)
        assert success is True
        assert state.state_number == 2

    def test_state_search_functionality(self, state_service, temp_project, settings, tmp_path):
        """Test searching states by prompt content."""
        from src.mcp_server.utils.init_manager import is_initialized

        volume_path = str(tmp_path / "volume")

        state_service.genesis(str(temp_project), volume_path)
        state_service.new_state_transition("Implement login feature")
        state_service.new_state_transition("Fix bug in dashboard")
        state_service.new_state_transition("Add user registration")

        results, msg = state_service.search_states("login")
        assert len(results) == 1
        assert 1 in results

        results, msg = state_service.search_states("user")
        assert len(results) == 1
        assert 3 in results  # State 3 was created for "Add user registration"

    def test_transition_tracking(self, state_service, temp_project, settings, tmp_path):
        """Test tracking last transitions."""
        from src.mcp_server.utils.init_manager import is_initialized

        volume_path = str(tmp_path / "volume")

        state_service.genesis(str(temp_project), volume_path)
        state_service.new_state_transition("Task 1")
        state_service.new_state_transition("Task 2")
        state_service.new_state_transition("Task 3")

        transitions, msg = state_service.track_transitions()

        assert len(transitions) == 3
        assert all(isinstance(t, str) for t in transitions)


class TestMCPToolsIntegration:
    """Integration tests for MCP tools with StateService."""

    @pytest.fixture
    def mock_state_repo(self):
        return MockStateRepository()

    @pytest.fixture
    def mock_transition_repo(self):
        return MockTransitionRepository()

    @pytest.fixture
    def git_manager(self):
        manager = MagicMock()
        manager.is_git_repo.return_value = True
        manager.clone_to_volume.return_value = True
        manager.get_current_branch.return_value = "feature/test"
        manager.get_diff.return_value = "diff content"
        manager.compute_changes_since_last_state.return_value = (
            '{"added": [], "modified": [], "deleted": [], "content_diffs": {}}',
            {},
        )
        return manager

    @pytest.fixture
    def settings(self, tmp_path):
        from src.mcp_server.config import Settings

        return Settings(
            db_mode="sqlite",
            sqlite_path=str(tmp_path / "test.db"),
            docker_volume_name=str(tmp_path),
        )

    @pytest.fixture
    def state_service(self, mock_state_repo, mock_transition_repo, git_manager, settings):
        from src.mcp_server.services.state_service import StateService

        return StateService(
            state_repo=mock_state_repo,
            transition_repo=mock_transition_repo,
            git_manager=git_manager,
            settings=settings,
        )

    def test_genesis_tool_output_format(self, state_service, settings, tmp_path):
        """Test that genesis tool returns correct output format."""
        from src.mcp_server.tools import genesis

        project_path = str(tmp_path / "project")
        volume_path = str(tmp_path / "volume")
        Path(project_path).mkdir()

        result = genesis(state_service, project_path, volume_path)

        assert "success" in result
        assert result["success"] is True
        assert "state" in result
        assert "message" in result
        assert result["state"]["state_number"] == 0

    def test_new_state_transition_tool_output_format(self, state_service, settings, tmp_path):
        """Test that new_state_transition tool returns correct output format."""
        from src.mcp_server.tools import new_state_transition
        from src.mcp_server.utils.init_manager import set_initialized

        project_path = str(tmp_path / "project")
        volume_path = str(tmp_path / "volume")
        Path(project_path).mkdir()

        state_service.genesis(project_path, volume_path)

        result = new_state_transition(state_service, "Test prompt")

        assert "success" in result
        assert "state" in result
        assert "message" in result
        assert result["state"]["user_prompt"] == "Test prompt"

    def test_get_current_state_info_tool(self, state_service, settings, tmp_path):
        """Test get_current_state_info tool."""
        from src.mcp_server.tools import get_current_state_info
        from src.mcp_server.utils.init_manager import set_initialized

        project_path = str(tmp_path / "project")
        volume_path = str(tmp_path / "volume")
        Path(project_path).mkdir()

        state_service.genesis(project_path, volume_path)

        result = get_current_state_info(state_service)

        assert "success" in result
        assert result["success"] is True
        assert "state" in result

    def test_total_states_tool(self, state_service, settings, tmp_path):
        """Test total_states tool."""
        from src.mcp_server.tools import total_states
        from src.mcp_server.utils.init_manager import set_initialized

        project_path = str(tmp_path / "project")
        volume_path = str(tmp_path / "volume")
        Path(project_path).mkdir()

        state_service.genesis(project_path, volume_path)

        result = total_states(state_service)

        assert "success" in result
        assert "total_states" in result
        assert result["total_states"] == 1  # After genesis, state 0 exists

    def test_search_states_tool(self, state_service, settings, tmp_path):
        """Test search_states tool."""
        from src.mcp_server.tools import search_states
        from src.mcp_server.utils.init_manager import set_initialized

        project_path = str(tmp_path / "project")
        volume_path = str(tmp_path / "volume")
        Path(project_path).mkdir()

        state_service.genesis(project_path, volume_path)
        state_service.new_state_transition("Find the bug")

        result = search_states(state_service, "bug")

        assert "success" in result
        assert "states" in result
        assert len(result["states"]) >= 1

    def test_track_transitions_tool(self, state_service, settings, tmp_path):
        """Test track_transitions tool."""
        from src.mcp_server.tools import track_transitions
        from src.mcp_server.utils.init_manager import set_initialized

        project_path = str(tmp_path / "project")
        volume_path = str(tmp_path / "volume")
        Path(project_path).mkdir()

        state_service.genesis(project_path, volume_path)
        state_service.new_state_transition("Task 1")

        result = track_transitions(state_service)

        assert "success" in result
        assert "transitions" in result
        assert len(result["transitions"]) == 1


class TestSecurityWorkflows:
    """Security-focused end-to-end tests."""

    @pytest.fixture
    def mock_state_repo(self):
        return MockStateRepository()

    @pytest.fixture
    def mock_transition_repo(self):
        return MockTransitionRepository()

    @pytest.fixture
    def git_manager(self):
        manager = MagicMock()
        manager.is_git_repo.return_value = True
        manager.clone_to_volume.return_value = True
        manager.get_current_branch.return_value = "main"
        manager.get_diff.return_value = "diff"
        manager.compute_changes_since_last_state.return_value = (
            '{"added": [], "modified": [], "deleted": [], "content_diffs": {}}',
            {},
        )
        return manager

    @pytest.fixture
    def settings(self, tmp_path):
        from src.mcp_server.config import Settings

        return Settings(
            db_mode="sqlite",
            sqlite_path=str(tmp_path / "test.db"),
            docker_volume_name=str(tmp_path),
        )

    @pytest.fixture
    def state_service(self, mock_state_repo, mock_transition_repo, git_manager, settings):
        from src.mcp_server.services.state_service import StateService

        return StateService(
            state_repo=mock_state_repo,
            transition_repo=mock_transition_repo,
            git_manager=git_manager,
            settings=settings,
        )

    def test_invalid_transition_id_returns_error(self, state_service, settings, tmp_path):
        """Test that invalid transition ID format returns error."""
        from src.mcp_server.tools import get_transition_info
        from src.mcp_server.utils.init_manager import set_initialized

        project_path = str(tmp_path / "project")
        volume_path = str(tmp_path / "volume")
        Path(project_path).mkdir()

        state_service.genesis(project_path, volume_path)

        result = get_transition_info(state_service, "not-a-uuid")

        assert result["success"] is False
        assert "Invalid" in result["message"]

    def test_arbitrary_transition_to_invalid_state(self, state_service, settings, tmp_path):
        """Test that arbitrary transition to invalid state returns error."""
        from src.mcp_server.utils.init_manager import set_initialized

        project_path = str(tmp_path / "project")
        volume_path = str(tmp_path / "volume")
        Path(project_path).mkdir()

        state_service.genesis(project_path, volume_path)

        success, state, msg = state_service.arbitrary_state_transition(999)

        assert success is False
        assert state is None
        assert "Invalid state number" in msg

    def test_duplicate_transition_prevention(self, state_service, settings, tmp_path):
        """Test that duplicate transitions are prevented at repository level."""
        from src.mcp_server.utils.init_manager import set_initialized

        project_path = str(tmp_path / "project")
        volume_path = str(tmp_path / "volume")
        Path(project_path).mkdir()

        state_service.genesis(project_path, volume_path)

        success1, state1, msg1 = state_service.new_state_transition("Task")
        success2, state2, msg2 = state_service.new_state_transition("Task")

        assert success1 is True
        assert success2 is True

        total, _ = state_service.total_states()
        assert total == 3  # States 0, 1, 2
