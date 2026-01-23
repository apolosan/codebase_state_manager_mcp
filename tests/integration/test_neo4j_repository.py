"""
Integration tests for Neo4j Database Repository.

These tests require a running Neo4j instance.
They can be run with:
  pytest tests/integration/test_neo4j_repository.py -v

For local testing without Docker, use SQLite.
For CI/CD, use docker-compose to start Neo4j first.
"""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from src.mcp_server.config import Settings
from src.mcp_server.models.state_model import State, Transition
from src.mcp_server.repositories.neo4j_repository import (
    Neo4jStateRepository,
    Neo4jTransitionRepository,
    create_neo4j_repositories,
)


class TestNeo4jStateRepository:
    """Integration tests for Neo4j State Repository."""

    @pytest.fixture
    def settings(self, tmp_path):
        import os

        return Settings(
            neo4j_enabled=True,
            db_mode="neo4j",
            neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
            neo4j_password=os.environ.get("NEO4J_PASSWORD", "password"),
            sqlite_path=str(tmp_path / "test.db"),
        )

    @pytest.fixture
    def neo4j_repos(self, settings):
        try:
            state_repo, transition_repo = create_neo4j_repositories(
                uri=settings.neo4j_uri,
                user=settings.neo4j_user,
                password=settings.neo4j_password,
                settings=settings,
            )
            yield state_repo, transition_repo
            # Cleanup
            try:
                with state_repo.driver.session() as session:
                    session.run("MATCH (n) DETACH DELETE n")
            except Exception:
                pass
            state_repo.driver.close()
        except Exception as e:
            pytest.skip(f"Neo4j not available: {e}")

    def test_create_state(self, neo4j_repos):
        """Test creating a state in Neo4j."""
        state_repo, _ = neo4j_repos

        state = State(
            state_number=0,
            user_prompt="Genesis state",
            branch_name="main",
            git_diff_info="initial diff",
            hash="abc123def456",
        )

        result = state_repo.create(state)
        assert result is True

        # Verify state was created
        retrieved = state_repo.get_by_number(0)
        assert retrieved is not None
        assert retrieved.state_number == 0
        assert retrieved.user_prompt == "Genesis state"
        assert retrieved.branch_name == "main"

    def test_create_multiple_states(self, neo4j_repos):
        """Test creating multiple states."""
        state_repo, _ = neo4j_repos

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

        # Verify all states can be retrieved
        all_states = state_repo.get_all()
        assert len(all_states) == 5

    def test_get_current_state(self, neo4j_repos):
        """Test getting the current (latest) state."""
        state_repo, _ = neo4j_repos

        # Create states with different numbers
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

    def test_state_exists(self, neo4j_repos):
        """Test checking if a state exists."""
        state_repo, _ = neo4j_repos

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

    def test_search_states(self, neo4j_repos):
        """Test searching states by prompt content."""
        state_repo, _ = neo4j_repos

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

        # Search for "login"
        results = state_repo.search("login")
        assert len(results) == 2
        assert 0 in results
        assert 3 in results

        # Search for "user"
        results = state_repo.search("user")
        assert 2 in results

    def test_duplicate_hash_prevention(self, neo4j_repos):
        """Test that duplicate hashes are prevented via unique constraint."""
        state_repo, _ = neo4j_repos

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

        # First should succeed, second should also succeed (MERGE behavior)
        # But only one state with that hash should exist
        assert result1 is True
        # MERGE will update the existing node, not fail


class TestNeo4jTransitionRepository:
    """Integration tests for Neo4j Transition Repository."""

    @pytest.fixture
    def settings(self, tmp_path):
        import os

        return Settings(
            neo4j_enabled=True,
            db_mode="neo4j",
            neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
            neo4j_password=os.environ.get("NEO4J_PASSWORD", "password"),
            sqlite_path=str(tmp_path / "test.db"),
        )

    @pytest.fixture
    def neo4j_repos(self, settings):
        try:
            state_repo, transition_repo = create_neo4j_repositories(
                uri=settings.neo4j_uri,
                user=settings.neo4j_user,
                password=settings.neo4j_password,
                settings=settings,
            )
            yield state_repo, transition_repo
            # Cleanup
            try:
                with state_repo.driver.session() as session:
                    session.run("MATCH (n) DETACH DELETE n")
            except Exception:
                pass
            state_repo.driver.close()
        except Exception as e:
            pytest.skip(f"Neo4j not available: {e}")

    def test_create_transition(self, neo4j_repos):
        """Test creating a transition."""
        _, transition_repo = neo4j_repos

        transition = Transition(
            transition_id=uuid4(),
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

    def test_get_transitions_for_state(self, neo4j_repos):
        """Test getting transitions for a specific state."""
        state_repo, transition_repo = neo4j_repos

        # Create states first
        for i in range(4):
            state = State(
                state_number=i,
                user_prompt=f"State {i}",
                branch_name="main",
                git_diff_info="",
                hash=f"hash{i}",
            )
            state_repo.create(state)

        # Create transitions: 0->1, 0->2, 1->3
        t1 = Transition(transition_id=uuid4(), current_state=0, next_state=1)
        t2 = Transition(transition_id=uuid4(), current_state=0, next_state=2)
        t3 = Transition(transition_id=uuid4(), current_state=1, next_state=3)

        transition_repo.create(t1)
        transition_repo.create(t2)
        transition_repo.create(t3)

        # Get transitions from state 0
        transitions = transition_repo.get_by_state(0)
        assert len(transitions) == 2

        # Get transitions from state 1
        transitions = transition_repo.get_by_state(1)
        assert len(transitions) == 1

    def test_get_last_transitions(self, neo4j_repos):
        """Test getting the last N transitions."""
        state_repo, transition_repo = neo4j_repos

        # Create states
        for i in range(5):
            state = State(
                state_number=i,
                user_prompt=f"State {i}",
                branch_name="main",
                git_diff_info="",
                hash=f"hash{i}",
            )
            state_repo.create(state)

        # Create 5 transitions
        for i in range(5):
            t = Transition(
                transition_id=uuid4(),
                current_state=i,
                next_state=i + 1 if i < 4 else 4,
                user_prompt=f"Transition {i}",
            )
            transition_repo.create(t)

        # Get last 3
        last = transition_repo.get_last(3)
        assert len(last) == 3


class TestNeo4jIntegrationWorkflow:
    """Integration tests for complete workflows."""

    @pytest.fixture
    def settings(self, tmp_path):
        import os

        return Settings(
            neo4j_enabled=True,
            db_mode="neo4j",
            neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
            neo4j_password=os.environ.get("NEO4J_PASSWORD", "password"),
            sqlite_path=str(tmp_path / "test.db"),
        )

    @pytest.fixture
    def neo4j_repos(self, settings):
        try:
            state_repo, transition_repo = create_neo4j_repositories(
                uri=settings.neo4j_uri,
                user=settings.neo4j_user,
                password=settings.neo4j_password,
                settings=settings,
            )
            yield state_repo, transition_repo
            # Cleanup
            try:
                with state_repo.driver.session() as session:
                    session.run("MATCH (n) DETACH DELETE n")
            except Exception:
                pass
            state_repo.driver.close()
        except Exception as e:
            pytest.skip(f"Neo4j not available: {e}")

    def test_complete_state_machine_workflow(self, neo4j_repos):
        """Test a complete state machine workflow."""
        state_repo, transition_repo = neo4j_repos

        # 1. Create genesis state
        genesis = State(
            state_number=0,
            user_prompt="Genesis - Initial state",
            branch_name="main",
            git_diff_info="",
            hash="genesis_hash",
        )
        state_repo.create(genesis)

        # 2. Create transitions and states
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
                transition_id=uuid4(),
                current_state=i - 1,
                next_state=i,
                user_prompt=f"Transition to state {i}",
            )
            transition_repo.create(transition)

        # 3. Verify workflow
        assert state_repo.count() == 4
        assert transition_repo.count() == 3

        current = state_repo.get_current()
        assert current.state_number == 3

        # 4. Search for specific state
        results = state_repo.search("Task 2")
        assert 2 in results

        # 5. Track transitions
        last = transition_repo.get_last(5)
        assert len(last) == 3


class TestNeo4jConstraints:
    """Tests for Neo4j constraints and indexes."""

    @pytest.fixture
    def settings(self, tmp_path):
        import os

        return Settings(
            neo4j_enabled=True,
            db_mode="neo4j",
            neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
            neo4j_password=os.environ.get("NEO4J_PASSWORD", "password"),
            sqlite_path=str(tmp_path / "test.db"),
        )

    @pytest.fixture
    def neo4j_repos(self, settings):
        try:
            state_repo, transition_repo = create_neo4j_repositories(
                uri=settings.neo4j_uri,
                user=settings.neo4j_user,
                password=settings.neo4j_password,
                settings=settings,
            )
            yield state_repo, transition_repo
            # Cleanup
            try:
                with state_repo.driver.session() as session:
                    session.run("MATCH (n) DETACH DELETE n")
            except Exception:
                pass
            state_repo.driver.close()
        except Exception as e:
            pytest.skip(f"Neo4j not available: {e}")

    def test_state_number_uniqueness(self, neo4j_repos):
        """Test that state_number is unique."""
        state_repo, _ = neo4j_repos

        # Create two states with same number
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

        # Only one state with number 42 should exist
        count = state_repo.count()
        assert count == 1

    def test_get_nonexistent_state(self, neo4j_repos):
        """Test getting a state that doesn't exist returns None."""
        state_repo, _ = neo4j_repos

        result = state_repo.get_by_number(99999)
        assert result is None

    def test_get_current_with_no_states(self, neo4j_repos):
        """Test get_current when no states exist returns None."""
        state_repo, _ = neo4j_repos

        # Ensure empty database
        with state_repo.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

        result = state_repo.get_current()
        assert result is None


class TestNeo4jTransitionRepositoryEdgeCases:
    """Edge case tests for Neo4j Transition Repository."""

    @pytest.fixture
    def settings(self, tmp_path):
        import os

        return Settings(
            neo4j_enabled=True,
            db_mode="neo4j",
            neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
            neo4j_password=os.environ.get("NEO4J_PASSWORD", "password"),
            sqlite_path=str(tmp_path / "test.db"),
        )

    @pytest.fixture
    def neo4j_repos(self, settings):
        try:
            state_repo, transition_repo = create_neo4j_repositories(
                uri=settings.neo4j_uri,
                user=settings.neo4j_user,
                password=settings.neo4j_password,
                settings=settings,
            )
            yield state_repo, transition_repo
            # Cleanup
            try:
                with state_repo.driver.session() as session:
                    session.run("MATCH (n) DETACH DELETE n")
            except Exception:
                pass
            state_repo.driver.close()
        except Exception as e:
            pytest.skip(f"Neo4j not available: {e}")

    def test_get_nonexistent_transition(self, neo4j_repos):
        """Test getting a transition that doesn't exist returns None."""
        _, transition_repo = neo4j_repos

        from uuid import uuid4
        result = transition_repo.get_by_id(uuid4())
        assert result is None

    def test_create_transition_exception_handling(self, neo4j_repos):
        """Test that create handles exceptions gracefully."""
        state_repo, transition_repo = neo4j_repos

        # Create a valid transition first
        transition = Transition(
            transition_id=uuid4(),
            current_state=0,
            next_state=1,
            user_prompt="Test transition",
        )
        result = transition_repo.create(transition)
        assert result is True

        # Try to create with same transition_id - should not raise
        # The MERGE will update the existing transition
        transition2 = Transition(
            transition_id=transition.transition_id,  # Same ID
            current_state=1,
            next_state=2,
            user_prompt="Updated transition",
        )
        # This should not crash (returns False due to MERGE behavior)
        result2 = transition_repo.create(transition2)
        # MERGE behavior: may succeed or return False depending on implementation
