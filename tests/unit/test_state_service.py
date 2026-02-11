from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch
from uuid import uuid4

import pytest

from src.mcp_server.config import Settings
from src.mcp_server.models.state_model import State, Transition
from src.mcp_server.services.state_service import StateService


class MockStateRepository:
    def __init__(self):
        self.states = {}
        self._initialized = False
        self._current_state = None

    def create(self, state: State) -> bool:
        self.states[state.state_number] = state
        return True

    def get_by_number(self, state_number: int):
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

    def exists(self, state_number: int) -> bool:
        return state_number in self.states

    def count(self) -> int:
        return len(self.states)

    def search(self, text: str):
        return [s.state_number for s in self.states.values() if text in s.user_prompt]

    def delete(self, state_number: int) -> bool:
        if state_number in self.states:
            del self.states[state_number]
            return True
        return False

    def create_next(self, state: State) -> bool:
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

    def create(self, transition: Transition) -> bool:
        self.transitions[str(transition.transition_id)] = transition
        return True

    def create_next(self, transition: Transition) -> bool:
        # Find next sequential ID
        max_id = max([int(k) for k in self.transitions.keys()]) if self.transitions else 0
        next_id = max_id + 1
        transition.transition_id = next_id
        self.transitions[str(next_id)] = transition
        return True

    def get_by_id(self, transition_id):
        return self.transitions.get(str(transition_id))

    def get_by_state(self, state_number: int):
        return [t for t in self.transitions.values() if t.current_state == state_number]

    def get_last(self, limit: int):
        all_t = list(self.transitions.values())
        return all_t[-limit:] if all_t else []

    def count(self) -> int:
        return len(self.transitions)


class TestStateServiceGenesis:
    @pytest.fixture
    def mock_repos(self):
        return MockStateRepository(), MockTransitionRepository()

    @pytest.fixture
    def git_manager(self):
        manager = MagicMock()
        manager.is_git_repo.return_value = True
        manager.clone_to_volume.return_value = True
        manager.get_current_branch.return_value = "main"
        manager.get_diff.return_value = "diff content"
        return manager

    @pytest.fixture
    def settings(self, tmp_path):
        return Settings(
            db_mode="sqlite",
            sqlite_path=str(tmp_path / "test.db"),
            docker_volume_name=str(tmp_path),
        )

    @pytest.fixture
    def state_service(self, mock_repos, git_manager, settings):
        state_repo, transition_repo = mock_repos
        return StateService(
            state_repo=state_repo,
            transition_repo=transition_repo,
            git_manager=git_manager,
            settings=settings,
        )

    def test_genesis_success(self, state_service, git_manager, settings, tmp_path):
        project_path = str(tmp_path / "project")
        volume_path = str(tmp_path / "volume")
        Path(project_path).mkdir()

        success, state, message = state_service.genesis(project_path, volume_path)

        assert success is True
        assert state is not None

    def test_genesis_volume_path_inside_project_path_fails(self, state_service, settings, tmp_path):
        """Test that genesis fails when volume_path is inside project_path."""
        project_path = str(tmp_path / "project")
        # volume_path INSIDE project_path - this should fail
        volume_path = str(tmp_path / "project" / "volume")
        Path(project_path).mkdir()

        success, state, message = state_service.genesis(project_path, volume_path)

        assert success is False
        assert state is None
        assert "must be outside the project path" in message

    def test_genesis_already_initialized(self, state_service, git_manager, settings, tmp_path):
        project_path = str(tmp_path / "project")
        volume_path = str(tmp_path / "volume")
        Path(project_path).mkdir()

        from src.mcp_server.utils.init_manager import set_initialized

        set_initialized(volume_path, True)

        success, state, message = state_service.genesis(project_path, volume_path)

        assert success is False
        assert state is None
        assert "already initialized" in message

    def test_genesis_non_git_repo(self, state_service, settings, tmp_path):
        manager = MagicMock()
        manager.is_git_repo.return_value = False
        manager.clone_to_volume.return_value = True
        manager.init_repo.return_value = True
        manager.create_branch.return_value = True

        state_service.git_manager = manager

        project_path = str(tmp_path / "project")
        volume_path = str(tmp_path / "volume")
        Path(project_path).mkdir()

        success, state, message = state_service.genesis(project_path, volume_path)

        assert success is True
        assert state.state_number == 0
        manager.init_repo.assert_called_once()
        manager.create_branch.assert_called_once()


class TestStateServiceTransitions:
    @pytest.fixture
    def mock_repos(self):
        return MockStateRepository(), MockTransitionRepository()

    @pytest.fixture
    def git_manager(self):
        manager = MagicMock()
        manager.get_diff.return_value = "new diff content"
        manager.compute_changes_since_last_state.return_value = (
            '{"added": [], "modified": [], "deleted": [], "content_diffs": {}}',
            {},
        )
        manager.get_directory_hashes.return_value = {}
        return manager

    @pytest.fixture
    def settings(self, tmp_path):
        return Settings(
            db_mode="sqlite",
            sqlite_path=str(tmp_path / "test.db"),
            docker_volume_name=str(tmp_path),
        )

    @pytest.fixture
    def state_service(self, mock_repos, git_manager, settings):
        state_repo, transition_repo = mock_repos
        return StateService(
            state_repo=state_repo,
            transition_repo=transition_repo,
            git_manager=git_manager,
            settings=settings,
        )

    def test_new_state_transition_requires_initialization(
        self, state_service, git_manager, settings, tmp_path
    ):
        success, state, message = state_service.new_state_transition("test prompt")

        assert success is False
        assert state is None
        assert "not initialized" in message

    def test_new_state_transition_success(
        self, state_service, mock_repos, git_manager, settings, tmp_path
    ):
        from src.mcp_server.utils.init_manager import set_initialized

        state_repo, transition_repo = mock_repos

        genesis_state = State(
            state_number=0,
            user_prompt="Genesis",
            branch_name="main",
            git_diff_info="initial",
            hash="hash0",
        )
        state_repo.create(genesis_state)
        set_initialized(settings.docker_volume_name, True)

        success, state, message = state_service.new_state_transition("Test prompt")

        assert success is True
        assert state is not None
        assert state.state_number == 1
        assert state.user_prompt == "Test prompt"

    def test_arbitrary_state_transition_invalid_state(
        self, state_service, mock_repos, git_manager, settings, tmp_path
    ):
        from src.mcp_server.utils.init_manager import set_initialized

        state_repo, transition_repo = mock_repos

        genesis_state = State(
            state_number=0,
            user_prompt="Genesis",
            branch_name="main",
            git_diff_info="initial",
            hash="hash0",
        )
        state_repo.create(genesis_state)
        set_initialized(settings.docker_volume_name, True)

        success, state, message = state_service.arbitrary_state_transition(99)

        assert success is False
        assert "excede" in message.lower() or "invalid" in message.lower()

    def test_arbitrary_state_transition_success(
        self, state_service, mock_repos, git_manager, settings, tmp_path
    ):
        from src.mcp_server.utils.init_manager import set_initialized

        state_repo, transition_repo = mock_repos

        state0 = State(
            state_number=0,
            user_prompt="Genesis",
            branch_name="main",
            git_diff_info="initial",
            hash="hash0",
        )
        state1 = State(
            state_number=1,
            user_prompt="State 1",
            branch_name="main",
            git_diff_info="diff1",
            hash="hash1",
        )
        state_repo.create(state0)
        state_repo.create(state1)
        set_initialized(settings.docker_volume_name, True)

        success, state, message = state_service.arbitrary_state_transition(0)

        assert success is True, f"Expected success but got: {message}"
        assert state.state_number == 0


class TestStateServiceGetters:
    @pytest.fixture
    def mock_repos(self):
        return MockStateRepository(), MockTransitionRepository()

    @pytest.fixture
    def git_manager(self):
        return MagicMock()

    @pytest.fixture
    def settings(self, tmp_path):
        return Settings(
            db_mode="sqlite",
            sqlite_path=str(tmp_path / "test.db"),
            docker_volume_name=str(tmp_path),
        )

    @pytest.fixture
    def state_service(self, mock_repos, git_manager, settings):
        state_repo, transition_repo = mock_repos
        return StateService(
            state_repo=state_repo,
            transition_repo=transition_repo,
            git_manager=git_manager,
            settings=settings,
        )

    def test_total_states_not_initialized(self, state_service):
        count, message = state_service.total_states()

        assert count == 0
        assert "not initialized" in message

    def test_get_current_state_number_not_initialized(self, state_service):
        result, message = state_service.get_current_state_number()

        assert result is None
        assert "not initialized" in message

    def test_search_states_not_initialized(self, state_service):
        results, message = state_service.search_states("test")

        assert results == []
        assert "not initialized" in message

    def test_track_transitions_not_initialized(self, state_service):
        results, message = state_service.track_transitions()

        assert results == []
        assert "not initialized" in message

    def test_get_state_info_not_found(self, state_service, settings):
        from src.mcp_server.utils.init_manager import set_initialized

        set_initialized(settings.docker_volume_name, True)

        state, message = state_service.get_state_info(999)

        assert state is None
        assert "not found" in message
