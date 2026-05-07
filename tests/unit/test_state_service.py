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
        self.metadata = {}

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

    def get_metadata(self, key: str):
        return self.metadata.get(key)

    def set_metadata(self, key: str, value: str) -> bool:
        self.metadata[key] = value
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

    def delete(self, transition_id: int) -> bool:
        key = str(transition_id)
        if key in self.transitions:
            del self.transitions[key]
            return True
        return False

    def get_rewarded(self):
        return [t for t in self.transitions.values() if t.reward is not None]

    def get_by_state_pair(self, current_state: int, next_state: int):
        return [
            t
            for t in self.transitions.values()
            if t.current_state == current_state and t.next_state == next_state
        ]

    def update_reward(self, transition_id: int, reward: float | None) -> bool:
        transition = self.transitions.get(str(transition_id))
        if transition is None:
            return False
        transition.reward = reward
        return True


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
        manager.get_directory_hashes.return_value = {"README.md": "a" * 64}
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

    def test_genesis_relative_volume_path_inside_project_path_fails(
        self, state_service, settings, tmp_path, monkeypatch
    ):
        """Test that relative volume paths inside the project are rejected after resolution."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        monkeypatch.chdir(project_root)

        success, state, message = state_service.genesis(str(project_root), "./data/volume")

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
        manager.get_directory_hashes.return_value = {"README.md": "a" * 64}

        state_service.git_manager = manager

        project_path = str(tmp_path / "project")
        volume_path = str(tmp_path / "volume")
        Path(project_path).mkdir()

        success, state, message = state_service.genesis(project_path, volume_path)

        assert success is True
        assert state.state_number == 0
        manager.init_repo.assert_called_once()
        manager.create_branch.assert_called_once()

    def test_genesis_generates_compact_context(self, state_service, git_manager, settings, tmp_path):
        project_path = str(tmp_path / "project")
        volume_path = str(tmp_path / "volume")
        Path(project_path).mkdir()

        success, state, message = state_service.genesis(project_path, volume_path)

        assert success is True
        assert state is not None
        assert state.llm_context is not None
        assert state.compression_version == "scc-e:v1"
        assert state.compacted_at is not None


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
        git_manager.compute_changes_since_last_state.return_value = (
            '{"added":["src/app.py"],"modified":[],"deleted":[],"content_diffs":{"src/app.py":"print(1)"}}',
            {"src/app.py": "a" * 64},
        )

        genesis_state = State(
            state_number=0,
            user_prompt="Genesis",
            branch_name="main",
            git_diff_info="initial",
            hash="hash0",
            file_hashes={"README.md": "f" * 64},
            file_hash_deltas={"README.md": "f" * 64},
        )
        state_repo.create(genesis_state)
        set_initialized(settings.docker_volume_name, True)

        success, state, message = state_service.new_state_transition("Test prompt")

        assert success is True
        assert state is not None
        assert state.state_number == 1
        assert state.user_prompt == "Test prompt"
        assert state.llm_context is not None
        assert state.compression_version == "scc-e:v1"
        assert state.compacted_at is not None

    def test_new_state_transition_persists_reward_on_transition(
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

        success, state, message = state_service.new_state_transition("Rewarded prompt", reward=7.5)

        assert success is True
        assert state is not None
        latest_transition = transition_repo.get_last(1)[0]
        assert latest_transition.reward == 7.5

    def test_new_state_transition_rejects_invalid_reward(
        self, state_service, mock_repos, git_manager, settings, tmp_path
    ):
        from src.mcp_server.utils.init_manager import set_initialized

        state_repo, _ = mock_repos

        genesis_state = State(
            state_number=0,
            user_prompt="Genesis",
            branch_name="main",
            git_diff_info="initial",
            hash="hash0",
        )
        state_repo.create(genesis_state)
        set_initialized(settings.docker_volume_name, True)

        success, state, message = state_service.new_state_transition("Bad reward", reward=99)

        assert success is False
        assert state is None
        assert "Invalid reward" in message

    def test_get_current_state_compact_context_returns_preview_without_mutation(
        self, state_service, mock_repos, git_manager, settings, tmp_path
    ):
        from src.mcp_server.utils.init_manager import set_initialized

        state_repo, transition_repo = mock_repos
        git_manager.compute_changes_since_last_state.return_value = (
            '{"added":["src/app.py"],"modified":[],"deleted":[],"content_diffs":{"src/app.py":"print(1)"}}',
            {"src/app.py": "a" * 64},
        )

        genesis_state = State(
            state_number=0,
            user_prompt="Genesis",
            branch_name="main",
            git_diff_info="initial",
            hash="hash0",
            file_hashes={"README.md": "f" * 64},
            file_hash_deltas={"README.md": "f" * 64},
        )
        state_repo.create(genesis_state)
        set_initialized(settings.docker_volume_name, True)

        before_states = state_repo.count()
        before_transitions = transition_repo.count()

        preview, message = state_service.get_current_state_compact_context(include_vocabulary=True)

        assert preview is not None
        assert preview["current_state"] == 0
        assert preview["preview"]["persisted"] is False
        assert preview["preview"]["llm_context"] is not None
        assert preview["preview"]["vocabulary"] is not None
        assert state_repo.count() == before_states
        assert transition_repo.count() == before_transitions
        assert state_repo.get_current().state_number == 0

    def test_get_compact_states_returns_generation_rewards_only(
        self, state_service, mock_repos, git_manager, settings, tmp_path
    ):
        from src.mcp_server.utils.init_manager import set_initialized

        state_repo, transition_repo = mock_repos
        git_manager.compute_changes_since_last_state.return_value = (
            '{"added":["src/app.py"],"modified":[],"deleted":[],"content_diffs":{"src/app.py":"print(1)"}}',
            {"src/app.py": "a" * 64},
        )

        genesis_state = State(
            state_number=0,
            user_prompt="Genesis",
            branch_name="main",
            git_diff_info="initial",
            hash="hash0",
            file_hashes={"README.md": "f" * 64},
            file_hash_deltas={"README.md": "f" * 64},
        )
        state_repo.create(genesis_state)
        set_initialized(settings.docker_volume_name, True)

        success, _, _ = state_service.new_state_transition("State one")
        assert success is True
        success, _, _ = state_service.new_state_transition("State two", reward=4.5)
        assert success is True

        success, _, _ = state_service.arbitrary_state_transition(1, "Jump back to state one")
        assert success is True
        latest_transition = transition_repo.get_last(1)[0]
        transition_repo.update_reward(latest_transition.transition_id, 9.0)

        success, states, message = state_service.get_compact_states(start_state=0, end_state=2)

        assert success is True
        assert [state["state_number"] for state in states] == [0, 1, 2]
        assert "reward" not in states[0]
        assert "reward" not in states[1]
        assert states[2]["reward"] == 4.5
        assert states[1]["llm_context"] is not None
        assert "0-2" in message

    def test_get_compact_states_rejects_invalid_selector_combination(
        self, state_service, mock_repos, git_manager, settings, tmp_path
    ):
        from src.mcp_server.utils.init_manager import set_initialized

        state_repo, _ = mock_repos
        genesis_state = State(
            state_number=0,
            user_prompt="Genesis",
            branch_name="main",
            git_diff_info="initial",
            hash="hash0",
            file_hashes={"README.md": "f" * 64},
            file_hash_deltas={"README.md": "f" * 64},
        )
        state_repo.create(genesis_state)
        set_initialized(settings.docker_volume_name, True)

        success, states, message = state_service.get_compact_states(
            state=1,
            start_state=0,
            end_state=2,
        )

        assert success is False
        assert states == []
        assert "exactly one selector mode" in message

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

    def test_get_rewarded_transitions_returns_only_rewarded_items(
        self, state_service, mock_repos, settings
    ):
        from src.mcp_server.utils.init_manager import set_initialized

        _, transition_repo = mock_repos
        transition_repo.create(
            Transition(
                transition_id=1,
                current_state=0,
                next_state=1,
                user_prompt="rewarded",
                reward=8.5,
            )
        )
        transition_repo.create(
            Transition(
                transition_id=2,
                current_state=1,
                next_state=2,
                user_prompt="plain",
            )
        )
        set_initialized(settings.docker_volume_name, True)

        transitions, message = state_service.get_rewarded_transitions()

        assert len(transitions) == 1
        assert transitions[0]["transition_id"] == "1"
        assert transitions[0]["reward"] == 8.5
        assert "1 total" in message

    def test_set_transition_reward_updates_by_transition_id(
        self, state_service, mock_repos, settings
    ):
        from src.mcp_server.utils.init_manager import set_initialized

        _, transition_repo = mock_repos
        transition_repo.create(
            Transition(
                transition_id=3,
                current_state=1,
                next_state=2,
                user_prompt="score me",
                reward=1.0,
            )
        )
        set_initialized(settings.docker_volume_name, True)

        success, transition, message = state_service.set_transition_reward(
            reward=4.5,
            transition_id=3,
        )

        assert success is True
        assert transition is not None
        assert transition["transition_id"] == "3"
        assert transition["previous_reward"] == 1.0
        assert transition["reward"] == 4.5
        assert "updated" in message.lower()

    def test_set_transition_reward_rejects_ambiguous_state_pair(
        self, state_service, mock_repos, settings
    ):
        from src.mcp_server.utils.init_manager import set_initialized

        _, transition_repo = mock_repos
        transition_repo.create(
            Transition(transition_id=4, current_state=2, next_state=3, user_prompt="first")
        )
        transition_repo.create(
            Transition(transition_id=5, current_state=2, next_state=3, user_prompt="second")
        )
        set_initialized(settings.docker_volume_name, True)

        success, transition, message = state_service.set_transition_reward(
            reward=3.0,
            current_state=2,
            next_state=3,
        )

        assert success is False
        assert transition is None
        assert "ambiguous" in message.lower()

    def test_set_transition_reward_rejects_invalid_selector(
        self, state_service, settings
    ):
        from src.mcp_server.utils.init_manager import set_initialized

        set_initialized(settings.docker_volume_name, True)

        success, transition, message = state_service.set_transition_reward(reward=1.0)

        assert success is False
        assert transition is None
        assert "selector" in message.lower() or "transition_id" in message.lower()

    def test_get_state_info_enriches_legacy_state_with_compact_context(
        self, state_service, mock_repos, settings
    ):
        from src.mcp_server.utils.init_manager import set_initialized

        state_repo, _ = mock_repos
        state_repo.create(
            State(
                state_number=0,
                user_prompt="Legacy genesis",
                branch_name="main",
                git_diff_info='{"added": ["README.md"], "modified": [], "deleted": [], "content_diffs": {"README.md": "hello"}}',
                hash="hash0",
                file_hashes={"README.md": "a" * 64},
                file_hash_deltas={"README.md": "a" * 64},
            )
        )
        set_initialized(settings.docker_volume_name, True)

        state, message = state_service.get_state_info(0)

        assert state is not None
        assert state.llm_context is not None
        assert state.compression_version == "scc-e:v1"
        assert state.compacted_at is not None

    def test_get_state_info_not_found(self, state_service, settings):
        from src.mcp_server.utils.init_manager import set_initialized

        set_initialized(settings.docker_volume_name, True)

        state, message = state_service.get_state_info(999)

        assert state is None
        assert "not found" in message


class TestStateServiceFixVolumePath:
    @pytest.fixture
    def mock_repos(self):
        return MockStateRepository(), MockTransitionRepository()

    @pytest.fixture
    def git_manager(self):
        manager = MagicMock()
        manager.clone_to_volume.return_value = True
        manager.get_directory_hashes.return_value = {"tracked.txt": "abc123"}
        return manager

    @pytest.fixture
    def settings(self, tmp_path):
        volume_path = tmp_path / "volume"
        return Settings(
            db_mode="sqlite",
            sqlite_path=str(tmp_path / "test.db"),
            docker_volume_name=str(volume_path),
            volume_path=str(volume_path),
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

    def test_fix_volume_path_rebuilds_missing_volume_without_touching_db(
        self, state_service, mock_repos, git_manager, settings, tmp_path
    ):
        from src.mcp_server.models.state_model import State
        from src.mcp_server.utils.init_manager import is_initialized

        state_repo, _ = mock_repos
        current_state = State(
            state_number=0,
            user_prompt="Genesis",
            branch_name="main",
            git_diff_info="initial",
            hash="hash0",
            file_hashes={"tracked.txt": "abc123"},
        )
        state_repo.create(current_state)
        state_repo.set_current(0)

        project_path = tmp_path / "project"
        project_path.mkdir()
        (project_path / "tracked.txt").write_text("content", encoding="utf-8")

        result_success, result_payload, result_message = state_service.fix_volume_path(
            str(project_path)
        )

        assert result_success is True
        assert result_payload == {
            "volume_path": settings.docker_volume_name,
            "codebase_path": str(Path(settings.docker_volume_name) / "codebase"),
            "current_state": 0,
            "recovery_transition_created": False,
        }
        assert "recovered successfully" in result_message
        assert Path(settings.docker_volume_name).exists()
        assert is_initialized(settings.docker_volume_name) is True
        git_manager.clone_to_volume.assert_called_once()
        assert state_repo.count() == 1
        assert state_repo.get_current().state_number == 0

    def test_fix_volume_path_fails_when_current_state_missing(
        self, state_service, git_manager, settings, tmp_path
    ):
        project_path = tmp_path / "project"
        project_path.mkdir()

        result_success, result_payload, result_message = state_service.fix_volume_path(
            str(project_path)
        )

        assert result_success is False
        assert result_payload is None
        assert "No current state found" in result_message
        git_manager.clone_to_volume.assert_not_called()
        assert Path(settings.docker_volume_name).exists() is False

    def test_fix_volume_path_fails_when_clone_fails(
        self, state_service, mock_repos, git_manager, settings, tmp_path
    ):
        from src.mcp_server.models.state_model import State
        from src.mcp_server.utils.init_manager import is_initialized

        git_manager.clone_to_volume.return_value = False

        state_repo, _ = mock_repos
        state_repo.create(
            State(
                state_number=0,
                user_prompt="Genesis",
                branch_name="main",
                git_diff_info="initial",
                hash="hash0",
                file_hashes={"tracked.txt": "abc123"},
            )
        )
        state_repo.set_current(0)
        state_repo.set_metadata(
            state_service.MANAGED_PROJECT_PATH_METADATA_KEY,
            str(tmp_path / "managed-project"),
        )

        managed_project = tmp_path / "managed-project"
        managed_project.mkdir()

        project_path = tmp_path / "project"
        project_path.mkdir()

        result_success, result_payload, result_message = state_service.fix_volume_path(
            str(project_path)
        )

        assert result_success is False
        assert result_payload is None
        assert "Failed to rebuild codebase snapshot" in result_message
        assert is_initialized(settings.docker_volume_name) is False

    def test_fix_volume_path_fails_when_rebuilt_snapshot_diverges_from_current_state(
        self, state_service, mock_repos, git_manager, settings, tmp_path
    ):
        from src.mcp_server.models.state_model import State
        from src.mcp_server.utils.init_manager import is_initialized

        state_repo, _ = mock_repos
        state_repo.create(
            State(
                state_number=0,
                user_prompt="Genesis",
                branch_name="main",
                git_diff_info="initial",
                hash="hash0",
                file_hashes={"tracked.txt": "expected-hash"},
            )
        )
        state_repo.set_current(0)

        project_path = tmp_path / "project"
        project_path.mkdir()
        (project_path / "tracked.txt").write_text("content", encoding="utf-8")

        with patch.object(
            state_service,
            "_create_recovery_transition_for_project",
            return_value=(False, None, "alignment rejected"),
        ):
            result_success, result_payload, result_message = state_service.fix_volume_path(
                str(project_path)
            )

        assert result_success is False
        assert result_payload is None
        assert "Project snapshot diverges from the current state stored in the database" in result_message
        assert "failed to create recovery transition" in result_message
        assert is_initialized(settings.docker_volume_name) is False

    def test_fix_volume_path_runs_consistency_auto_repair_before_rebuild(
        self, state_service, mock_repos, git_manager, settings, tmp_path
    ):
        state_repo, _ = mock_repos
        state_repo.create(
            State(
                state_number=0,
                user_prompt="Genesis",
                branch_name="main",
                git_diff_info="initial",
                hash="hash0",
                file_hashes={"tracked.txt": "abc123"},
            )
        )
        state_repo.set_current(0)

        project_path = tmp_path / "project"
        project_path.mkdir()
        (project_path / "tracked.txt").write_text("content", encoding="utf-8")

        fixable_issue = MagicMock(
            auto_fixable=True,
            category="filesystem",
            severity="error",
            message="flag missing",
        )
        checker = MagicMock()
        checker.check_all.side_effect = [[fixable_issue], [], []]

        with patch.object(state_service, "_should_run_consistency_check", return_value=True):
            with patch("src.mcp_server.services.state_service.ConsistencyChecker", return_value=checker):
                result_success, result_payload, result_message = state_service.fix_volume_path(
                    str(project_path)
                )

        assert result_success is True
        assert result_payload is not None
        assert "recovered successfully" in result_message
        assert result_payload["recovery_transition_created"] is False
        checker.auto_repair.assert_called_once_with()
        git_manager.clone_to_volume.assert_called_once()

    def test_fix_volume_path_uses_reconstructed_hashes_for_transition_state(
        self, state_service, mock_repos, git_manager, settings, tmp_path
    ):
        state_repo, _ = mock_repos
        state_repo.create(
            State(
                state_number=0,
                user_prompt="Genesis",
                branch_name="main",
                git_diff_info="initial",
                hash="hash0",
                file_hashes={"tracked.txt": "old-hash"},
            )
        )
        state_repo.create(
            State(
                state_number=1,
                user_prompt="Transition",
                branch_name="main",
                git_diff_info="diff",
                hash="hash1",
                file_hash_deltas={"tracked.txt": "abc123"},
            )
        )
        state_repo.set_current(1)

        project_path = tmp_path / "project"
        project_path.mkdir()
        (project_path / "tracked.txt").write_text("content", encoding="utf-8")

        result_success, result_payload, result_message = state_service.fix_volume_path(
            str(project_path)
        )

        assert result_success is True
        assert result_payload is not None
        assert result_payload["current_state"] == 1
        assert result_payload["recovery_transition_created"] is False
        assert "recovered successfully" in result_message

    def test_fix_volume_path_fails_when_non_volume_consistency_issue_remains(
        self, state_service, mock_repos, git_manager, tmp_path
    ):
        state_repo, _ = mock_repos
        state_repo.create(
            State(
                state_number=0,
                user_prompt="Genesis",
                branch_name="main",
                git_diff_info="initial",
                hash="hash0",
                file_hashes={"tracked.txt": "abc123"},
            )
        )
        state_repo.set_current(0)

        project_path = tmp_path / "project"
        project_path.mkdir()

        blocking_issue = MagicMock(
            auto_fixable=False,
            category="db",
            severity="error",
            message="database is not accessible",
        )
        checker = MagicMock()
        checker.check_all.return_value = [blocking_issue]

        with patch.object(state_service, "_should_run_consistency_check", return_value=True):
            with patch("src.mcp_server.services.state_service.ConsistencyChecker", return_value=checker):
                result_success, result_payload, result_message = state_service.fix_volume_path(
                    str(project_path)
                )

        assert result_success is False
        assert result_payload is None
        assert "consistency issues remain" in result_message
        assert "database is not accessible" in result_message
        git_manager.clone_to_volume.assert_not_called()

    def test_fix_volume_path_uses_persisted_managed_project_path_before_provided_path(
        self, state_service, mock_repos, git_manager, settings, tmp_path
    ):
        state_repo, _ = mock_repos
        state_repo.create(
            State(
                state_number=0,
                user_prompt="Genesis",
                branch_name="main",
                git_diff_info="initial",
                hash="hash0",
                file_hashes={"tracked.txt": "abc123"},
            )
        )
        state_repo.set_current(0)
        state_repo.set_metadata(
            state_service.MANAGED_PROJECT_PATH_METADATA_KEY,
            str(tmp_path / "managed-project"),
        )

        managed_project = tmp_path / "managed-project"
        managed_project.mkdir()
        (managed_project / "tracked.txt").write_text("content", encoding="utf-8")

        wrong_project = tmp_path / "wrong-project"
        wrong_project.mkdir()
        (wrong_project / "other.txt").write_text("wrong", encoding="utf-8")

        result_success, result_payload, result_message = state_service.fix_volume_path(
            str(wrong_project)
        )

        assert result_success is True
        assert result_payload is not None
        assert result_payload["recovery_transition_created"] is False
        assert "recovered successfully" in result_message
        clone_source = git_manager.clone_to_volume.call_args.args[0]
        assert clone_source == managed_project.resolve()

    def test_fix_volume_path_reports_mismatch_summary(self, state_service, mock_repos, git_manager, tmp_path):
        state_repo, _ = mock_repos
        state_repo.create(
            State(
                state_number=0,
                user_prompt="Genesis",
                branch_name="main",
                git_diff_info="initial",
                hash="hash0",
                file_hashes={"tracked.txt": "expected", "missing.txt": "missing"},
            )
        )
        state_repo.set_current(0)

        project_path = tmp_path / "project"
        project_path.mkdir()
        (project_path / "tracked.txt").write_text("content", encoding="utf-8")

        git_manager.get_directory_hashes.return_value = {
            "tracked.txt": "abc123",
            "extra.txt": "extra",
        }

        with patch.object(
            state_service,
            "_create_recovery_transition_for_project",
            return_value=(False, None, "alignment rejected"),
        ):
            result_success, result_payload, result_message = state_service.fix_volume_path(
                str(project_path)
            )

        assert result_success is False
        assert result_payload is None
        assert "missing=1" in result_message
        assert "extra=1" in result_message
        assert "changed=1" in result_message

    def test_fix_volume_path_auto_aligns_state_and_retries(self, state_service, mock_repos, git_manager, tmp_path):
        state_repo, _ = mock_repos
        state_repo.create(
            State(
                state_number=0,
                user_prompt="Genesis",
                branch_name="main",
                git_diff_info="initial",
                hash="hash0",
                file_hashes={"tracked.txt": "expected-old"},
            )
        )
        state_repo.set_current(0)

        aligned_state = State(
            state_number=1,
            user_prompt="Aligned",
            branch_name="main",
            git_diff_info="alignment",
            hash="hash1",
            file_hash_deltas={"tracked.txt": "abc123"},
        )
        state_repo.create(aligned_state)

        project_path = tmp_path / "project"
        project_path.mkdir()
        (project_path / "tracked.txt").write_text("content", encoding="utf-8")

        with patch.object(
            state_service,
            "_create_recovery_transition_for_project",
            return_value=(True, aligned_state, "aligned"),
        ) as align_mock:
            result_success, result_payload, result_message = state_service.fix_volume_path(
                str(project_path)
            )

        assert result_success is True
        assert result_payload is not None
        assert result_payload["current_state"] == 1
        assert result_payload["recovery_transition_created"] is True
        assert "recovered successfully" in result_message
        align_mock.assert_called_once()
