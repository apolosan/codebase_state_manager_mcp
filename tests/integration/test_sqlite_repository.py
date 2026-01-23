"""
Integration tests for SQLite Database Repository.

These tests validate SQLite operations without requiring external services.
They can be run with:
  pytest tests/integration/test_sqlite_repository.py -v
"""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from src.mcp_server.config import Settings
from src.mcp_server.models.state_model import State, Transition
from src.mcp_server.repositories.sqlite_repository import (
    SQLiteStateRepository,
    SQLiteTransitionRepository,
    create_sqlite_repositories,
)


class TestSQLiteStateRepository:
    """Integration tests for SQLite State Repository."""

    @pytest.fixture
    def settings(self, tmp_path):
        return Settings(
            neo4j_enabled=False,
            db_mode="sqlite",
            sqlite_path=str(tmp_path / "test.db"),
        )

    @pytest.fixture
    def sqlite_repos(self, settings):
        state_repo, transition_repo = create_sqlite_repositories(
            path=settings.sqlite_path,
            settings=settings,
        )
        yield state_repo, transition_repo

    def test_create_state(self, sqlite_repos):
        """Test creating a state in SQLite."""
        state_repo, _ = sqlite_repos

        state = State(
            state_number=0,
            user_prompt="Genesis state",
            branch_name="main",
            git_diff_info="initial diff",
            hash="abc123def456",
        )

        result = state_repo.create(state)
        assert result is True

        retrieved = state_repo.get_by_number(0)
        assert retrieved is not None
        assert retrieved.state_number == 0
        assert retrieved.user_prompt == "Genesis state"
        assert retrieved.branch_name == "main"

    def test_create_multiple_states(self, sqlite_repos):
        """Test creating multiple states."""
        state_repo, _ = sqlite_repos

        for i in range(5):
            state = State(
                state_number=i,
                user_prompt=f"State {i}",
                branch_name="main",
                git_diff_info=f"diff {i}",
                hash=f"hash{i}",
            )
            state_repo.create(state)

        assert state_repo.count() == 5

        all_states = state_repo.get_all()
        assert len(all_states) == 5

    def test_get_current_state(self, sqlite_repos):
        """Test getting the current (latest) state."""
        state_repo, _ = sqlite_repos

        for i in [0, 1, 2]:
            state = State(
                state_number=i,
                user_prompt=f"State {i}",
                branch_name="main",
                git_diff_info=f"diff {i}",
                hash=f"hash{i}",
            )
            state_repo.create(state)

        current = state_repo.get_current()
        assert current is not None
        assert current.state_number == 2

    def test_state_exists(self, sqlite_repos):
        """Test checking if a state exists."""
        state_repo, _ = sqlite_repos

        state = State(
            state_number=99,
            user_prompt="Test state",
            branch_name="main",
            git_diff_info="",
            hash="hash99",
        )
        state_repo.create(state)

        assert state_repo.exists(99) is True
        assert state_repo.exists(100) is False

    def test_search_states(self, sqlite_repos):
        """Test searching states by prompt content."""
        state_repo, _ = sqlite_repos

        states_data = [
            (0, "Implement login feature with OAuth", "hash0"),
            (1, "Fix bug in dashboard rendering", "hash1"),
            (2, "Add user registration page", "hash2"),
            (3, "Implement login validation", "hash3"),
        ]

        for num, prompt, h in states_data:
            state = State(
                state_number=num,
                user_prompt=prompt,
                branch_name="main",
                git_diff_info="",
                hash=h,
            )
            state_repo.create(state)

        results = state_repo.search("login")
        assert len(results) == 2
        assert 0 in results
        assert 3 in results

        results = state_repo.search("user")
        assert 2 in results

    def test_duplicate_hash_prevention(self, sqlite_repos):
        """Test that duplicate hashes are handled correctly."""
        state_repo, _ = sqlite_repos

        state1 = State(
            state_number=0,
            user_prompt="First state",
            branch_name="main",
            git_diff_info="",
            hash="same_hash",
        )
        state2 = State(
            state_number=1,
            user_prompt="Second state with same hash",
            branch_name="develop",
            git_diff_info="different",
            hash="same_hash",
        )

        result1 = state_repo.create(state1)
        result2 = state_repo.create(state2)

        assert result1 is True
        assert result2 is True


class TestSQLiteTransitionRepository:
    """Integration tests for SQLite Transition Repository."""

    @pytest.fixture
    def settings(self, tmp_path):
        return Settings(
            neo4j_enabled=False,
            db_mode="sqlite",
            sqlite_path=str(tmp_path / "test.db"),
        )

    @pytest.fixture
    def sqlite_repos(self, settings):
        state_repo, transition_repo = create_sqlite_repositories(
            path=settings.sqlite_path,
            settings=settings,
        )
        yield state_repo, transition_repo

    def test_create_transition(self, sqlite_repos):
        """Test creating a transition."""
        _, transition_repo = sqlite_repos

        transition = Transition(
            transition_id=1,
            current_state=0,
            next_state=1,
            user_prompt="First transition",
        )

        result = transition_repo.create(transition)
        assert result is True

        retrieved = transition_repo.get_by_id(transition.transition_id)
        assert retrieved is not None
        assert retrieved.current_state == 0
        assert retrieved.next_state == 1

    def test_get_transitions_for_state(self, sqlite_repos):
        """Test getting transitions for a specific state."""
        state_repo, transition_repo = sqlite_repos

        for i in range(4):
            state = State(
                state_number=i,
                user_prompt=f"State {i}",
                branch_name="main",
                git_diff_info="",
                hash=f"hash{i}",
            )
            state_repo.create(state)

        t1 = Transition(transition_id=1, current_state=0, next_state=1)
        t2 = Transition(transition_id=2, current_state=0, next_state=2)
        t3 = Transition(transition_id=3, current_state=1, next_state=3)

        transition_repo.create(t1)
        transition_repo.create(t2)
        transition_repo.create(t3)

        transitions = transition_repo.get_by_state(0)
        assert len(transitions) == 2

        transitions = transition_repo.get_by_state(1)
        assert len(transitions) == 1

    def test_get_last_transitions(self, sqlite_repos):
        """Test getting the last N transitions."""
        state_repo, transition_repo = sqlite_repos

        for i in range(5):
            state = State(
                state_number=i,
                user_prompt=f"State {i}",
                branch_name="main",
                git_diff_info="",
                hash=f"hash{i}",
            )
            state_repo.create(state)

        for i in range(5):
            t = Transition(
                transition_id=i + 1,
                current_state=i,
                next_state=i + 1 if i < 4 else 4,
                user_prompt=f"Transition {i}",
            )
            transition_repo.create(t)

        last = transition_repo.get_last(3)
        assert len(last) == 3


class TestSQLiteIntegrationWorkflow:
    """Integration tests for complete SQLite workflows."""

    @pytest.fixture
    def settings(self, tmp_path):
        return Settings(
            neo4j_enabled=False,
            db_mode="sqlite",
            sqlite_path=str(tmp_path / "test.db"),
        )

    @pytest.fixture
    def sqlite_repos(self, settings):
        state_repo, transition_repo = create_sqlite_repositories(
            path=settings.sqlite_path,
            settings=settings,
        )
        yield state_repo, transition_repo

    def test_complete_state_machine_workflow(self, sqlite_repos):
        """Test a complete state machine workflow with SQLite."""
        state_repo, transition_repo = sqlite_repos

        genesis = State(
            state_number=0,
            user_prompt="Genesis - Initial state",
            branch_name="main",
            git_diff_info="",
            hash="genesis_hash",
        )
        state_repo.create(genesis)

        for i in range(1, 4):
            state = State(
                state_number=i,
                user_prompt=f"State {i} - Task {i}",
                branch_name="main",
                git_diff_info=f"changes for task {i}",
                hash=f"hash{i}",
            )
            state_repo.create(state)

            transition = Transition(
                transition_id=i,
                current_state=i - 1,
                next_state=i,
                user_prompt=f"Transition to state {i}",
            )
            transition_repo.create(transition)

        assert state_repo.count() == 4
        assert transition_repo.count() == 3

        current = state_repo.get_current()
        assert current.state_number == 3

        results = state_repo.search("Task 2")
        assert 2 in results

        last = transition_repo.get_last(5)
        assert len(last) == 3


class TestSQLiteConstraints:
    """Tests for SQLite constraints and indexes."""

    @pytest.fixture
    def settings(self, tmp_path):
        return Settings(
            neo4j_enabled=False,
            db_mode="sqlite",
            sqlite_path=str(tmp_path / "test.db"),
        )

    @pytest.fixture
    def sqlite_repos(self, settings):
        state_repo, transition_repo = create_sqlite_repositories(
            path=settings.sqlite_path,
            settings=settings,
        )
        yield state_repo, transition_repo

    def test_state_number_uniqueness(self, sqlite_repos):
        """Test that state_number is unique."""
        state_repo, _ = sqlite_repos

        state1 = State(
            state_number=42,
            user_prompt="First state 42",
            branch_name="main",
            git_diff_info="",
            hash="hash_a",
        )
        state2 = State(
            state_number=42,
            user_prompt="Second state 42",
            branch_name="develop",
            git_diff_info="different",
            hash="hash_b",
        )

        state_repo.create(state1)
        state_repo.create(state2)

        count = state_repo.count()
        assert count == 1

    def test_hash_uniqueness(self, sqlite_repos):
        """Test that hash is unique."""
        state_repo, _ = sqlite_repos

        state1 = State(
            state_number=0,
            user_prompt="First state",
            branch_name="main",
            git_diff_info="",
            hash="unique_hash",
        )
        state2 = State(
            state_number=1,
            user_prompt="Second state",
            branch_name="develop",
            git_diff_info="different",
            hash="unique_hash",
        )

        result1 = state_repo.create(state1)
        result2 = state_repo.create(state2)

        assert result1 is True
        assert result2 is True
